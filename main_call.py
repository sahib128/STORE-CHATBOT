import os
import sqlite3
import json
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import sys
import time
from db_setup import chunk_text
# ---- STEP 1: PDF PROCESSING ----
from extract_text import extract_text_from_file
from db_setup import extract_and_store_chunks

import hashlib

DATABASE = 'embeddings_metadata.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def generate_document_hash(document_name, content):
    """Generate a unique hash for the document based on name and content."""
    hasher = hashlib.sha256()
    hasher.update(document_name.encode('utf-8'))
    hasher.update(content.encode('utf-8'))
    return hasher.hexdigest()

def process_pdf(pdf_path, db_conn, document_id):
    """Extract text from PDF, chunk it, and store it in the database with document_id."""
    if not os.path.exists(pdf_path):
        print(f"❌ Error: PDF file '{pdf_path}' not found.")
        return
    
    print("📄 Extracting text from PDF...")
    extracted_text = extract_text_from_file(pdf_path)
    
    print("🔄 Chunking text and storing in database...")
    chunks = chunk_text(extracted_text, max_tokens=500, overlap=50)
    
    cursor = db_conn.cursor()
    for chunk in chunks:
        cursor.execute(
            "INSERT INTO chunks (document_id, chunk) VALUES (?, ?)",
            (document_id, chunk)
        )
    db_conn.commit()
    print("✅ PDF processing complete: Text extracted, chunked, and stored in DB.")


# ---- STEP 2: LOAD LANGUAGE MODEL ----
def load_model(model_name: str):
    """Load the language model."""
    print(f"🤖 Loading model: {model_name}")
    return OllamaLLM(model=model_name)


# ---- STEP 3: RETRIEVE AND RANK CHUNKS ----
def fetch_all_chunks(db_conn):
    """Fetch all chunks from the database."""
    c = db_conn.cursor()
    c.execute("SELECT chunk FROM embeddings")
    results = c.fetchall()
    return [row[0] for row in results]


def rank_chunks_by_similarity(query_text, chunks, top_k=5):
    """Rank chunks by textual similarity using TF-IDF and cosine similarity."""
    if not chunks:
        return []

    # Combine the query and chunks into one list
    texts = [query_text] + chunks

    # Convert texts into TF-IDF matrix
    vectorizer = TfidfVectorizer().fit_transform(texts)

    # Compute cosine similarity between the query and all chunks
    cosine_similarities = cosine_similarity(vectorizer[0:1], vectorizer[1:]).flatten()
    
    # Rank chunks by similarity score
    ranked_indices = cosine_similarities.argsort()[-top_k:][::-1]
    ranked_chunks = [chunks[i] for i in ranked_indices]
    
    return ranked_chunks


# ---- STEP 4: HANDLE PROMPT WITH MODEL (Streaming Enabled) ----
def handle_prompt(query_text: str, context_text: str, model, temperature: float, top_p: float, max_length: int):
    """
    Handle the query and generate the full response before returning it. 
    """
    PROMPT_TEMPLATE = """
    Answer the question based only on the following context in a concise manner.**If Query answer is out of context then display "Invalid Question"** .Dont give Extra text such as "According to Context", Just give accurate and necessary response. :

    {context}

    ---

    Answer the question based on the above context: {question}
    - If the answer is explicitly found in the context, provide a concise and well-structured response.  
    - If the context does not mention anything related to the question, respond only with below text andDo not attempt to generate an answer beyond the provided context.:  
    **"Invalid Question"**  
    """
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)
    print("📝 Generating full response...\n")

    # Generate full response at once
    llm_result = model.generate([prompt], temperature=temperature, top_p=top_p, max_length=max_length)

    # Extract text response
    response_text = llm_result.generations[0][0].text  # Extract first response from LLMResult

    return response_text



def handle_general_prompt(query_text: str, model, temperature: float, top_p: float, max_length: int):
    """
    Handle a general chatbot query without relying on context or specific embeddings.
    Generates the full response before returning it.
    """
    PROMPT_TEMPLATE = """
    You are a helpful and knowledgeable assistant. Respond to the following query:

    {question}
    """
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(question=query_text)
    print("📝 Generating full response...\n")

    # Generate response all at once
    response = model.generate(prompt, temperature=temperature, top_p=top_p, max_length=max_length)
    
    print("\n✅ Response complete.")
    print("Handle prompt", response)
    return response


def main():
    # --- Database Connection ---
    db_conn = get_db_connection()
    
    # --- User Option ---
    mode = input("🤖 Choose mode (1: Document Query, 2: General Chatbot): ").strip()
    
    model_name = "llama3.1"
    model = load_model(model_name)
    temperature = 0.7
    top_p = 0.9
    max_length = 300
    
    if mode == '1':
        # --- File Upload ---
        file_path = input("📂 Enter the path to your file (PDF, DOCX): ").strip()
        extracted_text = extract_text_from_file(file_path)
        document_hash = generate_document_hash(os.path.basename(file_path), extracted_text)
        
        cursor = db_conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE document_hash = ?", (document_hash,))
        existing_document = cursor.fetchone()
        
        if existing_document:
            document_id = existing_document['id']
            print("✅ Document already exists. Fetching chunks directly from the database.")
        else:
            print("📄 Processing new document...")
            cursor.execute(
                "INSERT INTO documents (name, document_hash) VALUES (?, ?)",
                (os.path.basename(file_path), document_hash)
            )
            document_id = cursor.lastrowid
            process_pdf(file_path, db_conn, document_id)
            db_conn.commit()
        
        # --- User Query ---
        query_text = input("\n💬 Enter your question: ").strip()
        chunks = fetch_all_chunks(db_conn)
        ranked_chunks = rank_chunks_by_similarity(query_text, chunks, top_k=5)
        
        if not ranked_chunks:
            print("⚠️ No relevant chunks found. Please refine your question.")
            return
        
        context_text = " ".join(ranked_chunks)
        handle_prompt(query_text, context_text, model, temperature, top_p, max_length)
    
    elif mode == '2':
        # --- General Chatbot Query ---
        query_text = input("\n💬 Enter your general question: ").strip()
        handle_general_prompt(query_text, model, temperature, top_p, max_length)
    
    else:
        print("⚠️ Invalid option. Please choose 1 or 2.")
    
    db_conn.close()
    print("\n✅ Workflow complete. Goodbye!")