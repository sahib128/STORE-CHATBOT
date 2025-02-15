from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error, pooling

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,  # Port mapped in Docker
    'user': 'root',  # Change to 'user' if needed
    'password': '',
    'database': 'footwear-store'  # Your database name
}

# Global connection pool variable
connection_pool = None

# Function to create a database connection pool
def create_connection_pool():
    global connection_pool
    try:
        connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=5,  # Adjust pool size based on expected load
            **DB_CONFIG
        )
        print("Connection pool created successfully")
    except Error as e:
        print(f"Error creating connection pool: {e}")
        connection_pool = None

# API to get product titles, prices, sale prices, sale periods, categories, and brands for published products
@app.route('/api/products', methods=['GET'])
def get_products():
    if connection_pool is None:
        return jsonify({"error": "No active database connection pool."}), 500

    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
        SELECT 
            p.ID AS Product_ID,
            p.post_title AS Product_Title,
            MAX(CASE WHEN pm.meta_key = '_regular_price' THEN pm.meta_value END) AS Regular_Price,
            MAX(CASE WHEN pm.meta_key = '_sale_price' THEN pm.meta_value END) AS Sale_Price,
            MAX(CASE WHEN pm.meta_key = '_price' THEN pm.meta_value END) AS Current_Price,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_cat' THEN t.name END) AS Category,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'product_brand' THEN t.name END) AS Brand,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'pa_size' THEN t.name END) AS Size,
            GROUP_CONCAT(DISTINCT CASE WHEN tt.taxonomy = 'pa_color' THEN t.name END) AS Color
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
        return jsonify(products)
    except Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        connection.close()  # Return connection to the pool

# Run the server only if the database connection pool is created successfully
if __name__ == '__main__':
    create_connection_pool()
    if connection_pool:
        app.run(debug=True, port=5000)  # Run the server on port 5000
    else:
        print("Failed to create connection pool. Server not started.")
