import pandas as pd
import json
import re
from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error, pooling
import json
from langchain_ollama import OllamaLLM
from langchain.prompts import ChatPromptTemplate
from flask_cors import CORS


DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,  
    'user': 'root',  
    'password': '',  
    'database': 'footwear-store'  
}


connection_pool = None


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
        brands = [row["brand"] for row in cursor.fetchall()]  # Extract names into a list
        return brands
    except Error as e:
        print(f"❌ Database query error: {e}")
        return []
    finally:
        cursor.close()
        connection.close()  # Return connection to the pool




# Function to extract brand and category dynamically
def extract_info(text, brands, categories):
    brand = next((b for b in brands if re.search(rf'\b{b}\b', text, re.IGNORECASE)), None)
    category = next((c for c in categories if re.search(rf'\b{c}\b', text, re.IGNORECASE)), None)
    return brand, category

# Function to calculate trend score
def calculate_trend_score(likes, shares, comments, views):
    return (likes * 0.4) + (shares * 0.3) + (comments * 0.2) + (views * 0.1)

# Function to process social media data
def process_social_media_data(file_path):
    with open(file_path, 'r') as file:
        raw_data = json.load(file)
    
    
    known_brands = fetch_brands()  # Expand as needed
    print(known_brands)
    categories = ["Men", "Women", "Kids"]  
    
    processed_data = []
    for item in raw_data:
        text = item.get("caption") or item.get("message") or item.get("text", "")
        brand, category = extract_info(text, known_brands, categories)
        
        if brand and category:
            likes = int(item.get("like_count") or item.get("likes", 0))
            shares = int(item.get("shares", 0))
            comments = int(item.get("comments_count") or item.get("comments", 0))
            views = int(item.get("impressions") or item.get("views", 0))
            
            trend_score = calculate_trend_score(likes, shares, comments, views)
            
            processed_data.append({
                "brand": brand,
                "category": category,
                "likes": likes,
                "shares": shares,
                "comments": comments,
                "views": views,
                "trend_score": trend_score
            })
    
    df = pd.DataFrame(processed_data)
    
    if df.empty:
        print("No matching posts found for the provided keywords.")
        return df, pd.DataFrame()
    
    # Group by brand and category and sum trend scores
    brand_category_scores = (
        df.groupby(['brand', 'category'])['trend_score']
        .sum()
        .reset_index()
        .sort_values(by='trend_score', ascending=False)
    )
    
    df.to_csv('formatted_knowledgebase.csv', index=False)
    brand_category_scores.to_csv('brand_category_scores.csv', index=False)
    
    return df, brand_category_scores

# Example usage
create_connection_pool()
file_path = 'final.json'
df, brand_category_scores = process_social_media_data(file_path)

if not df.empty:
    print(df.head())
    print(brand_category_scores)
else:
    print("No data processed. Please check the input file and keywords.")
