import streamlit as st
import fitz  # PyMuPDF
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
# Download NLTK data if not already available
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
stop_words = set(stopwords.words("english"))

# Load the sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Define the text extraction and chatbot functions
def extract_and_split_text(pdf_path):
    document_text = ""
    with fitz.open(pdf_path) as doc:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            document_text += page.get_text() + "\n"
    
    # Split text into four sections based on length
    split_length = len(document_text) // 4
    sections = {
        "overview": document_text[:split_length],
        "getting_started": document_text[split_length:split_length*2],
        "advanced_features": document_text[split_length*2:split_length*3],
        "pricing_and_limitations": document_text[split_length*3:]
    }
    
    # Create embeddings for each paragraph within each section
    section_embeddings = {}
    for section_name, section_text in sections.items():
        paragraphs = section_text.split("\n\n")  # Split by double newline to get paragraphs
        embeddings = model.encode(paragraphs)     # Generate embeddings for each paragraph
        section_embeddings[section_name] = list(zip(paragraphs, embeddings))

    return section_embeddings

# Initialize the knowledge base
knowledge_base = {
    "S3": extract_and_split_text("aws-docs/s3.pdf"),
    "EC2": extract_and_split_text("aws-docs/ec2.pdf"),
    "IAM": extract_and_split_text("aws-docs/iam.pdf")
}

def match_query_to_text(service_name, query):
    # Retrieve the content for the specified service
    service_content = knowledge_base.get(service_name, {})
    
    # Determine the relevant section based on keywords in the query
    if any(keyword in query.lower() for keyword in ["overview", "introduction", "basics"]):
        section = "overview"
    elif any(keyword in query.lower() for keyword in ["setup", "get started", "usage"]):
        section = "getting_started"
    elif any(keyword in query.lower() for keyword in ["features", "advanced", "details"]):
        section = "advanced_features"
    elif any(keyword in query.lower() for keyword in ["pricing", "cost", "limitations"]):
        section = "pricing_and_limitations"
    else:
        # If no specific keywords match, search across all sections
        section = None

    # Embed the query
    query_embedding = model.encode([query])[0]

    # Initialize a variable to store the best match
    best_match = None
    highest_similarity = -1

    # Search within the specified section or all sections if no section is specified
    sections_to_search = [section] if section else service_content.keys()

    for sec in sections_to_search:
        for paragraph, embedding in service_content[sec]:
            # Calculate similarity
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = paragraph
    
    return best_match if best_match else "I'm sorry, I couldn't find an answer in the PDF content."

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
