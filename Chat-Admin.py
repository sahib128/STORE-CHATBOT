from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error, pooling
import json
import re
from flask_cors import CORS
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import copy
from step import final_func
from datetime import datetime
from docx import Document
app = Flask(__name__)
CORS(app)

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



def fetch_orders():
    """Fetch orders from the database with billing, shipping, and product details."""
    if connection_pool is None:
        return {"error": "No active database connection pool."}, 500

    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT 
            o.id AS order_id,
            o.date_created_gmt AS order_date,
            o.status AS order_status,

            -- Billing Information
            MAX(CASE WHEN om.meta_key = '_billing_first_name' THEN om.meta_value END) AS billing_first_name,
            MAX(CASE WHEN om.meta_key = '_billing_last_name' THEN om.meta_value END) AS billing_last_name,
            MAX(CASE WHEN om.meta_key = '_billing_address_index' THEN om.meta_value END) AS billing_address,

            -- Shipping Information
            MAX(CASE WHEN om.meta_key = '_shipping_address_index' THEN om.meta_value END) AS shipping_address,

            -- Contact Information
            o.billing_email AS billing_email,
            o.total_amount AS order_total,

            -- Products Ordered
            GROUP_CONCAT(DISTINCT oi.order_item_name) AS products_ordered

        FROM 
            wpuz_wc_orders o
        LEFT JOIN 
            wpuz_wc_orders_meta om ON o.id = om.order_id
        LEFT JOIN 
            wpuz_woocommerce_order_items oi ON o.id = oi.order_id AND oi.order_item_type = 'line_item'

        WHERE 
            o.status IN ('wc-completed', 'wc-processing', 'wc-pending')

        GROUP BY 
            o.id, o.date_created_gmt, o.status, o.billing_email, o.total_amount

        ORDER BY 
            o.date_created_gmt DESC;
        """
        
        cursor.execute(query)
        orders = cursor.fetchall()
        return orders, 200

    except Error as e:
        return {"error": str(e)}, 400

    finally:
        cursor.close()
        connection.close()  # Return connection to the pool


def generate_admin_response(query_text, data, query_context):
    

    # Format the prompt
    prompt_template = ChatPromptTemplate.from_template(query_context)
    prompt = prompt_template.format(context=data, question=query_text)

    try:
        response = model(prompt)
        return response.strip()
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        return "Error: Unable to process the request. Please try again."

def format_order(order):
    # Extract contact number using regex (improved pattern)
    contact_match = re.findall(r'(\+?\d{10,15})', order["billing_address"])
    contact = contact_match[-1] if contact_match else "N/A"  # Pick last match as number usually appears last

    # Format order date safely
    formatted_date = order["order_date"].strftime("%d %b %Y, %I:%M %p") if order.get("order_date") else "Unknown Date"

    return (f"📅 Order Date: {formatted_date}\n"
            f"📦 Order #{order['order_id']}\n"
            f"📍 Shipping Address:\n{order['shipping_address']}\n"
            f"🎁 Product: {order['products_ordered']}\n"
            f"💰 Total: {float(order['order_total']):,.0f} PKR\n"
            f"📧 Email: {order['billing_email']}\n"
            f"📞 Contact: {contact}\n"
            f"🚚 Status: Processing\n")





from docx import Document

def save_orders_to_word(file_path, orders):
    """ Saves the formatted order list to a Word document and overwrites the previous content. """
    
    # Ensure orders is a list of dictionaries
    if isinstance(orders, tuple):
        orders = orders[0]  
    
    # Format the orders into a string
    response = "Order Dispatch List\n\n" + "\n".join(format_order(order) for order in orders)
    
    # Create a new Word document (overwriting existing file)
    doc = Document()
    doc.add_paragraph(response)
    
    # Save the document at the specified path
    doc.save(file_path)
    print(f"Orders successfully saved to {file_path}")

# In the main function:






@app.route('/admin-chat', methods=['POST'])
def admin_chat():
    """API endpoint to process user queries."""
    data = request.get_json()
    user_query = data.get("query", "").strip()
    print("user query ", user_query)
    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400
    
    
    ad_placement_data=final_func()
    orders_labbeling_data = fetch_orders()
    print("labelssssss", orders_labbeling_data)
    
    # Define the ad prompt template
    AD_PROMPT_TEMPLATE = """
    Given the following product data, present it in a clear and user-friendly format with a starting message "Here is our Analysis for your direction".

    {context}

    Instructions:
    - Only give shoes data. No extra explanation
    - Make sure if the user has specified a number e.g 1,2,3,4 then only give that many shoes in descending order.
    - If the user asks for the top X products, sort them by Trend Score in descending order and display only the top X.
    - If no number is specified, display all products in an organized manner.
    - Show product details in an easy-to-read format with clear labels.

    Example format:

    **Top Trending Products**
    1️⃣ **Product Name:** <Product Name>
    - 🏷 **Brand:** <Brand>
    - 📂 **Category:** <Category>
    - 📊 **Trend Score:** <Trend Score>

    Answer the question: {question}
    """


    #keyword filtering
    order_labbeling_keywords = ["orders", "summary", "labelling", "labels", "order", "processing"]
    ad_placement_keywords= ["products", "shoes", "top shoes", "top selling", "ad", "placement", "top"]
    if any(keyword in user_query.lower() for keyword in ad_placement_keywords):
        response = generate_admin_response(user_query, ad_placement_data, AD_PROMPT_TEMPLATE)
    elif any(keyword in user_query.lower() for keyword in order_labbeling_keywords):
        orders = fetch_orders()
        if isinstance(orders, tuple):
            orders = orders[0]  # Ensure it's a list
        print("Order Dispatch List\n")
        
        save_orders_to_word("orders.docx", orders)  # Pass orders directly
        response = "✅ Your Order Labels Have Been Fetched! 🏷️📦\n📄 Check your order document to view the details. 🚀"



    return jsonify({"response": response})




if __name__ == '__main__':
    create_connection_pool()
    if connection_pool:
        app.run(debug=True, port=5000)
    else:
        print("Failed to create connection pool. Server not started.")