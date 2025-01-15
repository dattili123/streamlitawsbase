import os
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import boto3
import logging
import pickle

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the SentenceTransformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Directory paths
INPUT_DIR = "./input_pdfs"
OUTPUT_DIR = "./processed_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class BedrockProcessing:
    def __init__(self):
        self.bedrock = boto3.client("bedrock", region_name="us-east-1")

    def clean_text(self, text):
        """Clean and normalize text."""
        text = text.replace('\n', ' ')
        return ' '.join(text.split()).strip()

    def generate_response(self, prompt):
        """Generate a response using AWS Bedrock."""
        try:
            body = json.dumps({"inputText": prompt})
            response = self.bedrock.invoke_model_with_response_stream(
                modelId="amazon.titan-tg1-large",
                body=body,
                contentType="application/json"
            )

            # Process response stream
            response_text = ""
            for event in response["body"]:
                if "bytes" in event:
                    response_text += event["bytes"].decode("utf-8")

            return response_text
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "Error generating response."

# Function to extract and split text based on logical sections

def extract_and_split_text(pdf_path):
    """Extract text from a PDF and split it by logical sections such as headers."""
    logging.info(f"Processing file: {pdf_path}")
    text_chunks = []

    reader = PdfReader(pdf_path)
    current_section = ""
    section_content = ""

    for page in reader.pages:
        lines = page.extract_text().splitlines()
        for line in lines:
            line = line.strip()
            # Detect section headers (e.g., lines in uppercase or specific keywords)
            if line.isupper() or any(keyword in line.lower() for keyword in ["overview", "getting started", "features", "pricing"]):
                if section_content:
                    text_chunks.append((current_section, section_content.strip()))
                    section_content = ""
                current_section = line
            else:
                section_content += " " + line

    # Append the last section
    if section_content:
        text_chunks.append((current_section, section_content.strip()))

    return text_chunks

# Function to generate embeddings for text chunks

def generate_embeddings(text_chunks):
    """Generate embeddings for a list of text chunks."""
    return [(section, model.encode([content])[0]) for section, content in text_chunks]

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
            output_file = os.path.join(
                output_dir, f"{os.path.splitext(file_name)[0]}_embeddings.pkl"
            )
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
        for section, embedding in embeddings:
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = (file_name, section)

    if best_match:
        file_name, section = best_match
        return f"**File:** {file_name}\n**Section:** {section}"
    else:
        return "I'm sorry, I couldn't find relevant information in the PDFs."

# Main chatbot handler
def chatbot_query_handler(user_query, knowledge_base):
    """Handle user queries with knowledge base search and Bedrock response generation."""
    bedrock_processor = BedrockProcessing()
    retrieval_response = query_knowledge_base(user_query, knowledge_base)
    final_response = bedrock_processor.generate_response(f"{retrieval_response}\n\nBased on this information, generate a detailed answer.")
    return final_response

# Process PDFs and build knowledge base
knowledge_base = process_pdfs(INPUT_DIR, OUTPUT_DIR)

# Example Query Handling
if __name__ == "__main__":
    user_query = "What is Amazon EC2?"
    response = chatbot_query_handler(user_query, knowledge_base)
    print(response)
