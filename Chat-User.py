from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error, pooling
import json
import re
from flask_cors import CORS
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import copy
from flask import Flask, request, jsonify
from main_call import process_pdf, load_model, handle_prompt, rank_chunks_by_similarity, extract_text_from_file, generate_document_hash,handle_general_prompt
import sqlite3
import hashlib
import os
app = Flask(__name__)
CORS(app)

DATABASE = 'embeddings_metadata.db'


# --- Utility Functions ---
def get_db_connection():
    """Establish and return a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def file_hash(file_path):
    """Generate SHA256 hash for a file."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'footwear-store'
}

# Global connection pool
connection_pool = None

# Load LLM Model
model = OllamaLLM(model="llama3.1")

def create_connection_pool():
    """Creates a MySQL connection pool."""
    global connection_pool
    try:
        connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool", pool_size=5, **DB_CONFIG
        )
        print("✅ Connection pool created successfully")
    except Error as e:
        print(f"❌ Error creating connection pool: {e}")
        connection_pool = None

def fetch_products():
    """Fetches product data from the database."""
    if connection_pool is None:
        return []

    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT 
            p.ID AS product_id,
            p.post_title AS name,
            MAX(CASE WHEN pm.meta_key = '_price' THEN CAST(pm.meta_value AS UNSIGNED) END) AS price,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_cat' THEN t.name END) AS category,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_brand' THEN t.name END) AS brand,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'pa_size' THEN t.name END) AS available_sizes
        FROM wpuz_posts p
        LEFT JOIN wpuz_postmeta pm ON p.ID = pm.post_id 
        LEFT JOIN wpuz_term_relationships tr ON p.ID = tr.object_id
        LEFT JOIN wpuz_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
        LEFT JOIN wpuz_terms t ON tt.term_id = t.term_id
        WHERE p.post_type = 'product' AND p.post_status = 'publish'
        GROUP BY p.ID, p.post_title;
        """
        cursor.execute(query)
        return cursor.fetchall()
    
    except Error as e:
        print(f"❌ Database query error: {e}")
        return []
    
    finally:
        cursor.close()
        connection.close()

def extract_filters(query_text):
    """Uses LLM to extract filtering criteria from the user query."""
    filters = {
        "brand": None,
        "min_price": None,
        "max_price": None,
        "category": None
    }
    prompt_template = ChatPromptTemplate.from_template(
        """
        Only Create one single output of JSON STRING. No Code. Only Extract brand, max_price or min_price, and category if present in the query and create a JSON string as specified in the example.

        Query: "{query}"

        **Return ONLY a JSON object** with these keys: `"brand"`, `"min_price"`, `"max_price"`, `"category"`.

        ### Rules:
        - `"brand"`: If a brand name (e.g., **Nike, Adidas, SK, ARF**) is present in the query, extract it. **Do not leave brand null** if a valid brand is mentioned.
        - `"category"`: **MUST** be one of the predefined values:
        - `"Mens Collection"`
        - `"Women Collection"`
        - `"Kids Collection"`
        - **`null` if the query does not explicitly mention a valid category.**
        - **"Shoes" or other generic words should NOT be classified as a category.**
        - **If the user asks for "below X", "less than X", "under X", "cheaper than X"**, set `"max_price": X` (not `min_price`).
        - **If the user asks for "greater than X", "higher than X", "above X", "more than X"**, set `"min_price": X` (not `max_price`).
        - **Do NOT infer a category unless it explicitly matches the valid categories.**
        
        **Example Responses:**
        ```json
        {{"brand": null, "min_price": null, "max_price": null, "category": "null"}}
        ```
        """
    )


    prompt = prompt_template.format(query=query_text)  

    try:
        response = model(prompt)


        clean_response = re.sub(r"```json\n|\n```", "", response.strip())  # Remove Markdown
        json_match = re.search(r"\{.*\}", clean_response, re.DOTALL)  # Extract JSON block
        
        if json_match:
            clean_response = json_match.group(0)

        # ✅ Parse JSON response safely
        filters = json.loads(clean_response)

        if not isinstance(filters, dict):  
            raise ValueError("Response is not a valid JSON object")
        
        return filters

    except Exception as e:
        print(f"❌ Error extracting filters: {e}")
        return {}

def transform_product_data(raw_product_data):
    """Converts raw database product data into structured format."""
    
    transformed_data = {"products": []}

    for product in raw_product_data:
        transformed_product = {
            "product_id": product["product_id"],
            "name": product["name"],
            "price": product["price"],
            "category": [cat.strip() for cat in product["category"].split(",") if cat.strip()],  # Convert category to a list
            "brand": product["brand"],
            "available_sizes": [int(size) for size in product["available_sizes"].split(",") if size.isdigit()]  # Convert sizes to a list of integers
        }
        transformed_data["products"].append(transformed_product)

    return transformed_data



def filter_products(product_data, filters):
    """Filters products based on the given filter criteria."""
    
 
    product_data = copy.deepcopy(product_data)

    brand_filter = filters.get("brand")
    brand_filter = None if brand_filter in [None, "null"] else brand_filter.lower()
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")

    category_filter = filters.get("category")

 
    valid_categories = {"mens collection", "women collection", "kids collection"}


    if category_filter and category_filter.lower() in valid_categories:
        category_filter = category_filter.lower()
    else:
        category_filter = None 


    filtered_list = []
    if brand_filter or  category_filter or  min_price and not max_price:
        print("All filters are empty.")
        response = "Please provide at least one filter to proceed."
        for product in product_data:
            if not isinstance(product, dict):
                print(f"❌ Skipping invalid product entry: {product}")
                continue

            if brand_filter:
                product_brand = product.get("brand", "").lower()
                if product_brand != brand_filter:
                    continue

            if isinstance(min_price, (int, float)) or isinstance(max_price, (int, float)):
                product_price = product.get("price")
                if isinstance(product_price, (int, float)):  # Ensure product has a valid price
                    if min_price is not None and product_price < min_price:
                        continue
                    if max_price is not None and product_price > max_price:
                        continue

            if category_filter:
                product_categories = {cat.lower().strip() for cat in product.get("category", []) if isinstance(cat, str)}
                if category_filter not in product_categories:
                    continue

            filtered_list.append(product)

    return copy.deepcopy(filtered_list)


def generate_response(filtered_products):

    formatted_products = "\n".join(
        f"🛍️ **{p['name']}**\n💰 Price: {p['price']} \n🏷️ Brand: {p['brand']} \n📦 Category: {', '.join(p['category'])} \n👟 Sizes: {', '.join(map(str, p['available_sizes']))}"
        for p in filtered_products
    )
    print(formatted_products)

    try:
        response = formatted_products
        return response.strip()
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        return "Error: Unable to process the request. Please try again."

def UserChat(pdf_path, query):
    if not query:
        return {"error": "Missing 'question' parameter."}, 400
    
    # Extract text for hashing
    extracted_text = extract_text_from_file(pdf_path)
    document_hash = generate_document_hash(os.path.basename(pdf_path), extracted_text)
    
    # Database Connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if the document already exists
    cursor.execute("SELECT id FROM documents WHERE document_hash = ?", (document_hash,))
    existing_document = cursor.fetchone()
    
    if existing_document:
        document_id = existing_document['id']
    else:
        # Insert document metadata
        cursor.execute(
            "INSERT INTO documents (name, document_hash) VALUES (?, ?)",
            (os.path.basename(pdf_path), document_hash)
        )
        document_id = cursor.lastrowid

        # Process and store chunks
        process_pdf(pdf_path, conn, document_id)
        conn.commit()
    
    # Fetch chunks related to this document
    cursor.execute("SELECT chunk FROM chunks WHERE document_id = ?", (document_id,))
    chunks = [row['chunk'] for row in cursor.fetchall()]
    
    if not chunks:
        conn.close()
        return {"error": "No chunks found for this document."}, 404
    
    # Rank chunks and generate a response
    ranked_chunks = rank_chunks_by_similarity(query, chunks, top_k=5)
    context_text = " ".join(ranked_chunks)
    
    model = load_model("llama3.1")
    response = handle_prompt(query, context_text, model, 0.7, 0.9, 300)
    
    conn.close()

    return response

def format_response_for_chat(response):
    """Formats chatbot responses for HTML display in the frontend."""
    if isinstance(response, dict):
        return "<br>".join(f"<strong>{key}:</strong> {value}" for key, value in response.items())
    elif isinstance(response, list):
        return "<ul>" + "".join(f"<li>{item}</li>" for item in response) + "</ul>"
    elif isinstance(response, str):
        return response.replace("**", "<strong>").replace("\n", "<br>").replace("*", "• ")
    return str(response)  # Fallback for unknown types




@app.route('/chat', methods=['POST'])
def chat():
    """API endpoint to process user queries."""
    data = request.get_json()
    user_query = data.get("query", "").strip()


    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    # ✅ Fetch and transform fresh product data
    raw_product_data = fetch_products()
    product_data = transform_product_data(raw_product_data)
    

    if not product_data["products"]:
        return jsonify({"error": "No product data found."}), 500

    filters = extract_filters(user_query)
    if any(value not in [None, "null", ""] for value in filters.values()):
        print("✅ At least one filter value is valid:", filters)
        filtered_products = filter_products(copy.deepcopy(product_data["products"]), filters)  
        

        if not filtered_products:  
            response = "This is not available at the moment."
        else:            
            response = generate_response(filtered_products)


        del raw_product_data, product_data, filtered_products, filters
    else:
        print("⚠️ All filter values are null or empty:", filters)
        response = UserChat("knowledge_base.pdf", user_query)
    return jsonify({"response": response})





if __name__ == '__main__':
    create_connection_pool()
    if connection_pool:
        app.run(debug=True, port=5000)
    else:
        print("Failed to create connection pool. Server not started.")








