import os
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import boto3
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the SentenceTransformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Directory paths
INPUT_DIR = "./input_pdfs"
OUTPUT_DIR = "./processed_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Function to extract and split text dynamically

def extract_and_split_text(pdf_path, chunk_size=500):
    """Extract text from a PDF and split it into smaller chunks."""
    logging.info(f"Processing file: {pdf_path}")
    text_chunks = []
    
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text()
            for i in range(0, len(text), chunk_size):
                text_chunks.append(text[i:i + chunk_size])

    return text_chunks

# Function to generate embeddings for text chunks

def generate_embeddings(text_chunks):
    """Generate embeddings for a list of text chunks."""
    return [(chunk, model.encode([chunk])[0]) for chunk in text_chunks]

# Function to process all PDFs and generate embeddings

def process_pdfs(input_dir, output_dir):
    """Process all PDFs in the input directory and save embeddings."""
    knowledge_base = {}

    for file_name in os.listdir(input_dir):
        if file_name.endswith('.pdf'):
            pdf_path = os.path.join(input_dir, file_name)
            text_chunks = extract_and_split_text(pdf_path)
            embeddings = generate_embeddings(text_chunks)
            
            # Save embeddings for later use
            output_file = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_embeddings.pkl")
            with open(output_file, 'wb') as f:
                pickle.dump(embeddings, f)

            knowledge_base[file_name] = embeddings

    return knowledge_base

# Function to query the knowledge base

def query_knowledge_base(query, knowledge_base):
    """Query the knowledge base using a user-provided query."""
    query_embedding = model.encode([query])[0]
    best_match = None
    highest_similarity = -1

    for file_name, embeddings in knowledge_base.items():
        for chunk, embedding in embeddings:
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = (file_name, chunk)

    if best_match:
        file_name, chunk = best_match
        return f"**File:** {file_name}\n**Excerpt:** {chunk}"
    else:
        return "I'm sorry, I couldn't find relevant information in the PDFs."

# Bedrock Integration for LLM Response

def get_bedrock_response(prompt):
    """Get an LLM response from AWS Bedrock."""
    bedrock = boto3.client('bedrock')
    response = bedrock.invoke_model(
        modelId='amazon-bedrock-model-id',  # Replace with your Bedrock model ID
        body={"prompt": prompt},
        contentType="application/json"
    )
    return response['body'].decode('utf-8')

# Main function to handle user queries

def chatbot_query_handler(query, knowledge_base):
    """Handle user queries with combined embedding search and LLM response."""
    retrieval_response = query_knowledge_base(query, knowledge_base)
    bedrock_response = get_bedrock_response(f"{retrieval_response}\n\nBased on this information, generate a detailed answer.")
    return bedrock_response

# Process PDFs and build knowledge base
knowledge_base = process_pdfs(INPUT_DIR, OUTPUT_DIR)

# Example Query Handling
if __name__ == "__main__":
    user_query = "What is Amazon EC2?"
    response = chatbot_query_handler(user_query, knowledge_base)
    print(response)
