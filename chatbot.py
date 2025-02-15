from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error, pooling
import json
from langchain_ollama import OllamaLLM
from langchain.prompts import ChatPromptTemplate

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,  
    'user': 'root',  
    'password': '',  
    'database': 'footwear-store'  
}

# Global connection pool variable
connection_pool = None

# Load Ollama Model
DEFAULT_MODEL_NAME = "llama3.1"
model = OllamaLLM(model=DEFAULT_MODEL_NAME)

# Create a database connection pool
def create_connection_pool():
    global connection_pool
    try:
        connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=5,
            **DB_CONFIG
        )
        print("✅ Connection pool created successfully")
    except Error as e:
        print(f"❌ Error creating connection pool: {e}")
        connection_pool = None

# Fetch product data from MySQL
def fetch_products():
    """Fetch all relevant product details from the database."""
    if connection_pool is None:
        return []

    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT 
            p.ID AS product_id,
            p.post_title AS product_title,
            MAX(CASE WHEN pm.meta_key = '_regular_price' THEN pm.meta_value END) AS regular_price,
            MAX(CASE WHEN pm.meta_key = '_sale_price' THEN pm.meta_value END) AS sale_price,
            MAX(CASE WHEN pm.meta_key = '_price' THEN pm.meta_value END) AS current_price,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_cat' THEN t.name END) AS category,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_brand' THEN t.name END) AS brand
        FROM 
            wpuz_posts p
        LEFT JOIN 
            wpuz_postmeta pm ON p.ID = pm.post_id AND pm.meta_key IN ('_regular_price', '_sale_price', '_price')
        LEFT JOIN 
            wpuz_term_relationships tr ON p.ID = tr.object_id
        LEFT JOIN 
            wpuz_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
        LEFT JOIN 
            wpuz_terms t ON tt.term_id = t.term_id
        WHERE 
            p.post_type = 'product'
            AND p.post_status = 'publish'
        GROUP BY 
            p.ID, p.post_title
        """
        cursor.execute(query)
        products = cursor.fetchall()
        return products
    except Error as e:
        print(f"❌ Database query error: {e}")
        return []
    finally:
        cursor.close()
        connection.close()  # Return connection to the pool

# Chatbot handler
def handle_prompt(query_text, product_data, temperature=0.7, top_p=0.9, max_length=500):
    """Process the user's query using product data."""
    PROMPT_TEMPLATE = """
    You are an e-commerce assistant. Answer user queries based only on the following product data:

    {context}

    ---
    
    User's question: {question}

    Make sure to list **all matching products** and not just one.
    """
    
    # Convert product data to JSON string
    context_text = json.dumps(product_data, indent=2)

    # Create prompt
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)
    
    try:
        response = "".join(model.stream(prompt, temperature=temperature, top_p=top_p, max_length=max_length))
        return response
    except Exception as e:
        print(f"❌ Error during response generation: {e}")
        return "Error generating response."

# API Endpoint to handle chatbot queries
@app.route('/chat', methods=['POST'])
def chat():
    """API endpoint to process user queries."""
    data = request.get_json()
    user_query = data.get("query", "").strip()

    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    # Fetch product data from the database
    product_data = fetch_products()

    if not product_data:
        return jsonify({"error": "No product data found."}), 500

    # Get chatbot response
    response = handle_prompt(user_query, product_data)
    return jsonify({"response": response})

# Start Flask server
if __name__ == '__main__':
    create_connection_pool()
    if connection_pool:
        app.run(debug=True, port=5000)  
    else:
        print("Failed to create connection pool. Server not started.")
