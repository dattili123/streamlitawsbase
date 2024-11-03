import streamlit as st
import fitz  # PyMuPDF
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download NLTK data if not already available
nltk.download('punkt')
nltk.download('stopwords')
stop_words = set(stopwords.words("english"))

# Define the text extraction and chatbot functions
def extract_and_split_text(pdf_path):
    document_text = ""
    with fitz.open(pdf_path) as doc:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            document_text += page.get_text() + "\n"
    
    # Split text into four parts
    split_length = len(document_text) // 4
    part1 = document_text[:split_length]
    part2 = document_text[split_length:split_length*2]
    part3 = document_text[split_length*2:split_length*3]
    part4 = document_text[split_length*3:]
    
    return {
        "part1": part1,
        "part2": part2,
        "part3": part3,
        "part4": part4
    }

# Initialize the knowledge base
knowledge_base = {
    "S3": extract_and_split_text("aws-docs/s3.pdf"),
    "EC2": extract_and_split_text("aws-docs/ec2.pdf"),
    "IAM": extract_and_split_text("aws-docs/iam.pdf")
}

def match_query_to_text(service_name, query):
    service_content = knowledge_base.get(service_name, {})
    query_tokens = [word for word in word_tokenize(query.lower()) if word.isalnum() and word not in stop_words]
    relevant_text = ""
    for part_name, content in service_content.items():
        sentences = content.split("\n")
        for sentence in sentences:
            sentence_tokens = [word for word in word_tokenize(sentence.lower()) if word.isalnum()]
            if all(word in sentence_tokens for word in query_tokens):
                relevant_text += sentence + "\n"
    return relevant_text if relevant_text else "I'm sorry, I couldn't find an answer in the PDF content."

def aws_chatbot(service_name, user_question):
    if any(keyword in user_question.lower() for keyword in ["overview", "introduction", "basics"]):
        part = "part1"
    elif any(keyword in user_question.lower() for keyword in ["setup", "get started", "usage"]):
        part = "part2"
    elif any(keyword in user_question.lower() for keyword in ["features", "advanced", "details"]):
        part = "part3"
    elif any(keyword in user_question.lower() for keyword in ["pricing", "cost", "limitations"]):
        part = "part4"
    else:
        part = None
    
    if part:
        answer = match_query_to_text(service_name, user_question)
    else:
        answer = match_query_to_text(service_name, user_question)
    return answer

# Streamlit interface
st.title("AWS Knowledge Base Chatbot")
st.write("Ask questions related to AWS services like S3, EC2, and IAM based on the PDF knowledge base.")

# Dropdown for selecting the service
service_name = st.selectbox("Select AWS Service", ["S3", "EC2", "IAM"])

# Text input for user question
user_question = st.text_input("Enter your question")

# Button to submit the question
if st.button("Get Answer"):
    if service_name and user_question:
        response = aws_chatbot(service_name, user_question)
        st.write("**Bot:**", response)
    else:
        st.write("Please select a service and enter a question.")
