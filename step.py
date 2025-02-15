import pandas as pd
import json
import re
import mysql.connector
from mysql.connector import Error, pooling

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'footwear-store'
}

connection_pool = None

def create_connection_pool():
    """Create a database connection pool."""
    global connection_pool
    try:
        connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=5,
            **DB_CONFIG
        )
    except Error as e:
        print(f"❌ Error creating connection pool: {e}")
        connection_pool = None

def fetch_brands():
    """Fetch all unique brand names that have at least one published product."""
    if connection_pool is None:
        return []
    
    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT DISTINCT t.name AS brand
        FROM wpuz_terms t
        JOIN wpuz_term_taxonomy tt ON t.term_id = tt.term_id
        JOIN wpuz_term_relationships tr ON tt.term_taxonomy_id = tr.term_taxonomy_id
        JOIN wpuz_posts p ON tr.object_id = p.ID
        WHERE tt.taxonomy = 'product_brand'
            AND p.post_type = 'product'
            AND p.post_status = 'publish';
        """
        cursor.execute(query)
        return [row["brand"] for row in cursor.fetchall()]
    except Error as e:
        print(f"❌ Error fetching brands: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def fetch_products():
    """Fetch product names, brands, and categories from the database."""
    if connection_pool is None:
        return []
    
    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
        SELECT p.post_title AS product_name, 
               brand_terms.name AS brand, 
               category_terms.name AS category
        FROM wpuz_posts p
        JOIN wpuz_term_relationships tr_brand ON p.ID = tr_brand.object_id
        JOIN wpuz_term_taxonomy tt_brand ON tr_brand.term_taxonomy_id = tt_brand.term_taxonomy_id
        JOIN wpuz_terms brand_terms ON tt_brand.term_id = brand_terms.term_id 
        JOIN wpuz_term_relationships tr_category ON p.ID = tr_category.object_id
        JOIN wpuz_term_taxonomy tt_category ON tr_category.term_taxonomy_id = tt_category.term_taxonomy_id
        JOIN wpuz_terms category_terms ON tt_category.term_id = category_terms.term_id 
        WHERE p.post_type = 'product' 
          AND p.post_status = 'publish'
          AND tt_brand.taxonomy = 'product_brand'
          AND tt_category.taxonomy = 'product_cat';
        """
        cursor.execute(query)
        return cursor.fetchall()
    except Error as e:
        print(f"❌ Error fetching products: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def calculate_trend_score(likes, shares, comments, views):
    """Calculate trend score based on engagement metrics."""
    return (likes * 0.4) + (shares * 0.3) + (comments * 0.2) + (views * 0.1)

def fetch_brands_and_process_social_data(raw_data):
    """Fetch brands and process social media data to compute trend scores."""
    known_brands = fetch_brands()
    categories = ["Men", "Women", "Kids"]
    
    processed_data = []
    for item in raw_data:
        text = item.get("caption") or item.get("message") or item.get("text", "")
        brand = next((b for b in known_brands if re.search(rf'\b{b}\b', text, re.IGNORECASE)), None)
        category = next((c for c in categories if re.search(rf'\b{c}\b', text, re.IGNORECASE)), None)
        
        if brand and category:
            likes = int(item.get("like_count") or item.get("likes", 0))
            shares = int(item.get("shares", 0))
            comments = int(item.get("comments_count") or item.get("comments", 0))
            views = int(item.get("impressions") or item.get("views", 0))
            
            trend_score = calculate_trend_score(likes, shares, comments, views)
            
            processed_data.append({
                "brand": brand,
                "category": category,
                "trend_score": trend_score
            })
    
    df = pd.DataFrame(processed_data)
    
    if df.empty:
        return []

    brand_category_scores = (
        df.groupby(['brand', 'category'])['trend_score']
        .sum()
        .reset_index()
        .sort_values(by='trend_score', ascending=False)
    )
    
    return brand_category_scores.to_dict(orient='records')

import json

def normalize_category(category):
    """Convert product categories to match trend category names."""
    category_mapping = {
        "Mens Collection": "Men",
        "Women Collection": "Women",
        "Kids Collection": "Kids"
    }
    return category_mapping.get(category, category)  # Default to original if no match

def match_products_with_scores(product_data, brand_category_scores):
    """Match products with the highest brand-category scores and return top 3 products."""
    matched_products = []

    for score_entry in brand_category_scores:
        brand = score_entry["brand"]
        category = score_entry["category"]
        trend_score = score_entry["trend_score"]
        
        # Normalize categories for comparison
        matching_products = [
            p for p in product_data if p["brand"] == brand and normalize_category(p["category"]) == category
        ]

        # Sort products within this brand-category combination and take top 3
        top_products = matching_products[:3]

        for product in top_products:
            matched_products.append({
                "product_name": product["product_name"],
                "brand": product["brand"],
                "category": product["category"],
                "trend_score": trend_score
            })

    # Sort globally by trend_score and return the top 3
    matched_products = sorted(matched_products, key=lambda x: x["trend_score"], reverse=True)

    return json.dumps(matched_products, indent=4)


def final_func():
        
    json_file = "final.json"

    # Load the JSON data from the file
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            trend_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        trend_data = []
    product_data = fetch_products()
    # Process social data to get brand-category scores
    brand_category_scores = fetch_brands_and_process_social_data(trend_data)
    result = match_products_with_scores(product_data, brand_category_scores)

    return result

# Initialize connection pool
create_connection_pool()




if __name__ == "__main__":
    json_file = "final.json"

    # Load the JSON data from the file
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            trend_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        trend_data = []

    # Fetch product data
    product_data = fetch_products()
    # Process social data to get brand-category scores
    brand_category_scores = fetch_brands_and_process_social_data(trend_data)
    # Match top 3 products
    result = match_products_with_scores(product_data, brand_category_scores)

    # Print final structured JSON output
    print(result)
