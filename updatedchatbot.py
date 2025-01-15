import os
import shutil
import json
import re
from PyPDF2 import PdfReader, PdfWriter
from pathlib import Path
import boto3

source_directory = "./docs"
target_directory = "./processed_data"

def move_and_categorize_pdfs(source_dir, target_dir):
    """Move and categorize PDFs based on size."""
    categories = {
        'small': [],
        'medium': [],
        'large': []
    }

    os.makedirs(target_dir, exist_ok=True)

    for file in os.listdir(source_dir):
        if file.endswith('.pdf'):
            filepath = os.path.join(source_dir, file)
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # size in MB

            if file_size < 1:
                category = 'small'
            elif file_size < 10:
                category = 'medium'
            else:
                category = 'large'

            category_path = os.path.join(target_dir, category)
            os.makedirs(category_path, exist_ok=True)

            shutil.move(filepath, os.path.join(category_path, file))
            categories[category].append(file)

    return categories

def extract_text_from_pdfs(pdf_dir):
    """Extract text from PDFs and organize it by filename."""
    extracted_data = {}

    for root, _, files in os.walk(pdf_dir):
        for file in files:
            if file.endswith('.pdf'):
                filepath = os.path.join(root, file)
                reader = PdfReader(filepath)
                text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                extracted_data[file] = text

    return extracted_data

def query_llm_bedrock(prompt, aws_region="us-east-1"):
    """Query AWS Bedrock runtime for LLM responses."""
    client = boto3.client('bedrock-runtime', region_name=aws_region)
    
    payload = {
        "inputText": prompt
    }
    
    response = client.invoke_model(
        modelId='amazon.titan-tg1-large',
        contentType='application/json',
        accept='application/json',
        body=json.dumps(payload)
    )

    result = json.loads(response['body'].read().decode('utf-8'))
    return result

def chatbot_response(extracted_data, user_prompt):
    """Generate a chatbot response based on the user prompt."""
    combined_text = "\n".join(extracted_data.values())
    prompt = f"The user asked: {user_prompt}\nUsing the following information: {combined_text[:5000]}\nPlease respond appropriately."

    response = query_llm_bedrock(prompt)
    return response

if __name__ == "__main__":

    # Step 1: Move and categorize PDFs
    categories = move_and_categorize_pdfs(source_directory, target_directory)
    print("PDFs categorized into:", categories)

    # Step 2: Extract text from categorized PDFs
    extracted_text = extract_text_from_pdfs(source_directory)

    # Save extracted text to a JSON file for reference
    with open("extracted_data.json", "w") as json_file:
        json.dump(extracted_text, json_file, indent=4)

    # Step 3: Chatbot interaction
    while True:
        user_input = input("Ask a question (or type 'exit' to quit): ")
        if user_input.lower() == 'exit':
            break

        response = chatbot_response(extracted_text, user_input)
        chatbot_answer = response['results'][0].get('outputText')
        print("Chatbot response:", chatbot_answer)
       
