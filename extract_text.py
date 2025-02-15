import PyPDF2
import os
from docx import Document

def extract_text_from_file(file_path):
    """Extract text from a PDF or Word document."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Error: File '{file_path}' not found.")
    
    _, file_extension = os.path.splitext(file_path)
    text = ""
    
    if file_extension.lower() == '.pdf':
        # Handle PDF files
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
    elif file_extension.lower() == '.docx':
        # Handle Word files
        doc = Document(file_path)
        for para in doc.paragraphs:
            text += para.text + '\n'
    else:
        raise ValueError("❌ Unsupported file format. Please provide a PDF or DOCX file.")
    
    return text
