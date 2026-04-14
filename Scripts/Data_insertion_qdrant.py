import fitz   # PyMuPDF - used for reading PDF files page by page
from sentence_transformers import SentenceTransformer
import os
import uuid # Used to generate unique IDs for each stored page

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qdrant_connection import build_qdrant_client

# ------------------------------------------------------------
# Load the SentenceTransformer model
# This model converts text into a 384-dimensional embedding,
# which is used by Qdrant for semantic search.
# ------------------------------------------------------------
embedder = SentenceTransformer('all-MiniLM-L12-v2')  

qdrant_client = build_qdrant_client()
collection_name = "network_security_knowledge"

# Function to extract text from PDF and store it in Qdrant
def process_pdfs(directory):
    page_texts = []
    
    # List PDF files in the given directory
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
    
    # Process each PDF
    for pdf_file in pdf_files:
        pdf_path = os.path.join(directory, pdf_file)  # Get full path for the PDF
        doc = fitz.open(pdf_path)  # Open the PDF using its full path
        
        # Iterate over the pages and extract text
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            page_texts.append((pdf_file, page_num + 1, text))  # Store (doc_name, page_num, text)
        
    # Insert each page's text into Qdrant (indexed by document name and page number)
    for doc_name, page_num, text in page_texts:
        # Generate embedding for the text of the page
        embedding = embedder.encode([text])[0]  # Text embedding
        
        # Generate a unique UUID for each page
        point_id = str(uuid.uuid4())  # Generate a unique UUID
        
        qdrant_client.upsert(
            collection_name=collection_name,
            points=[{
                "id": point_id,  # Use UUID as the point ID
                "vector": embedding.tolist(),
                "payload": {
                    "document": doc_name,
                    "page_number": page_num,
                    "text": text[:500]  # Store the first 500 characters for reference
                }
            }]
        )
    # Final summary after processing all PDFs
    print(f"Processed {len(page_texts)} pages from {len(pdf_files)} documents")

if __name__ == "__main__":
    # Project root = parent of Scripts/
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(_root, "knowledge_base")
    process_pdfs(pdf_path)
