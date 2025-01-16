import os
import shutil
import json
import re
from PyPDF2 import PdfReader, PdfWriter
from pathlib import Path
import boto3

source_directory = "./docs"
target_directory = "./processed_data"

def split_pdf_by_size(input_pdf_path, output_dir, max_size_in_mb=1):
    """
    Split a single PDF into multiple smaller PDFs based on the specified size.

    :param input_pdf_path: Path to the input PDF file.
    :param output_dir: Directory where the split PDFs will be saved.
    :param max_size_in_mb: Maximum size for each split PDF in MB.
    """
    max_size_in_bytes = max_size_in_mb * 1024 * 1024  # Convert MB to bytes
    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    part_number = 1
    current_size = 0

    for page_number, page in enumerate(reader.pages, start=1):
        writer.add_page(page)

        # Create a temporary file to calculate the current PDF size
        temp_output = os.path.join(output_dir, f"temp_part_{part_number}.pdf")
        with open(temp_output, "wb") as temp_file:
            writer.write(temp_file)
        
        # Check the size of the temporary file
        current_size = os.path.getsize(temp_output)

        if current_size >= max_size_in_bytes:
            # Save the current part and reset the writer
            output_file = os.path.join(output_dir, f"split_part_{part_number}.pdf")
            os.rename(temp_output, output_file)
            print(f"Saved {output_file} with size {current_size / (1024 * 1024):.2f} MB")

            part_number += 1
            writer = PdfWriter()  # Reset writer for the next part
        else:
            # Remove the temporary file since we haven't reached the size limit
            os.remove(temp_output)

    # Save any remaining pages
    if writer.pages:
        output_file = os.path.join(output_dir, f"split_part_{part_number}.pdf")
        with open(output_file, "wb") as final_file:
            writer.write(final_file)
        print(f"Saved {output_file} with size {os.path.getsize(output_file) / (1024 * 1024):.2f} MB")
        
def process_and_split_pdfs(source_dir, target_dir, max_size_in_mb=1):
    """Process all PDFs in the source dir and split them into smaller PDFs."""
    for file in os.listdir(source_dir):
        if file.endswith('.pdf'):
            input_pdf_path = os.path.join(source_dir, file)
            output_pdf_dir = os.path.join(target_dir, file.split('.')[0])
            split_pdf_by_size(input_pdf_path, output_pdf_dir, max_size_in_mb)
        
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
    #categories = move_and_categorize_pdfs(source_directory, target_directory)
    #print("PDFs categorized into:", categories)
    
    process_and_split_pdfs(source_directory, target_directory, max_size_in_mb=1)

    # Step 2: Extract text from categorized PDFs
    extracted_text = extract_text_from_pdfs(target_directory)

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
       
