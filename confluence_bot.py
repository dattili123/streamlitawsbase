import os
import requests
import chromadb
import streamlit as st
import boto3
import json
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs, INFO for general logs
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("chatbot_debug.log")],
)

# ✅ AWS Bedrock Client Setup
boto3_bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")  # Set your AWS region

# ✅ Confluence API Details
CONFLUENCE_BASE_URL = "https://confluence.organization.com"
PERSONAL_ACCESS_TOKEN = "your_personal_access_token"
HEADERS = {
    "Authorization": f"Bearer {PERSONAL_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# ✅ Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_confluence_db")
collection = chroma_client.get_or_create_collection(name="confluence_embeddings")


def get_page_id_by_title(space_key, page_title):
    """
    Fetches the Page ID for a given title in a Confluence space.
    """
    logging.info(f"Fetching Page ID for space_key='{space_key}' and page_title='{page_title}'.")
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content?title={page_title}&spaceKey={space_key}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            page_id = data["results"][0]["id"]
            logging.info(f"Found Page ID: {page_id}")
            return page_id
        else:
            logging.warning("No results found for the given page title.")
            return None
    else:
        logging.error(f"Failed to fetch Page ID. HTTP Status: {response.status_code}, Response: {response.text}")
        return None


def fetch_confluence_content(page_id):
    """
    Fetches and cleans text content from a Confluence page.
    """
    logging.info(f"Fetching content for Page ID: {page_id}")
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        html_content = data["body"]["storage"]["value"]
        logging.info(f"Successfully fetched content for Page ID: {page_id}")
        return BeautifulSoup(html_content, "html.parser").get_text()
    else:
        logging.error(f"Failed to fetch content for Page ID: {page_id}. HTTP Status: {response.status_code}, Response: {response.text}")
        return None


def process_text(content):
    """
    Splits text into chunks for embedding.
    """
    logging.info("Processing text content into chunks.")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_text(content)
    logging.debug(f"Generated {len(chunks)} text chunks.")
    return chunks


def generate_embedding(text):
    """
    Generates embeddings using AWS Bedrock Titan Embedding v2.
    """
    logging.info("Generating embedding for text chunk.")
    payload = {"inputText": text}
    try:
        response = boto3_bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps(payload)
        )
        response_body = json.loads(response["body"].read())
        logging.debug("Successfully generated embedding.")
        return response_body["embedding"]
    except Exception as e:
        logging.error(f"Failed to generate embedding: {e}")
        raise


def store_in_chroma(text_chunks):
    """
    Stores document embeddings in ChromaDB.
    """
    logging.info("Storing text chunks and embeddings into ChromaDB.")
    for i, chunk in enumerate(text_chunks):
        try:
            embedding = generate_embedding(chunk)
            collection.add(
                ids=[f"doc_{i}"],
                embeddings=[embedding],
                metadatas=[{"source": "confluence"}],
                documents=[chunk]
            )
            logging.debug(f"Successfully stored chunk {i} in ChromaDB.")
        except Exception as e:
            logging.error(f"Failed to store chunk {i} in ChromaDB: {e}")


def generate_answer_with_bedrock(prompt, model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", region="us-east-1"):
    """
    Generate a response using AWS Bedrock with the provided prompt.
    """
    logging.info("Generating response using AWS Bedrock Claude 3.5 Sonnet.")
    client = boto3.client("bedrock-runtime", region_name=region)
    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": {"type": "text", "text": prompt}}],
                "max_tokens": 512,
                "temperature": 0.7,
                "top_p": 0.9,
            }),
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response["body"].read().decode("utf-8"))
        response_text = "".join(item.get("text", "") for item in response_body["content"])
        logging.info("Successfully generated response from Bedrock.")
        return response_text.strip() if response_text.strip() else "No response generated."
    except Exception as ex:
        logging.error(f"Error generating response: {ex}")
        return f"Error generating response: {ex}"


def query_chromadb_rag(user_query, top_k=3):
    """
    Retrieves relevant Confluence content and generates AI response using Claude 3.5 Sonnet.
    """
    logging.info(f"Querying ChromaDB for user query: '{user_query}'")
    query_embedding = generate_embedding(user_query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    retrieved_text = "\n\n".join(results["documents"][0])
    logging.info("Successfully retrieved relevant content from ChromaDB.")
    prompt = f"""
    You are an expert in AWS and Confluence documentation.
    Answer the user's question using the retrieved Confluence documentation.

    **Retrieved Context:**
    {retrieved_text}

    **User Question:**
    {user_query}

    **Answer:**
    """
    return generate_answer_with_bedrock(prompt)


def main():
    """
    Streamlit UI for the chatbot.
    """
    st.set_page_config(page_title="Confluence Chatbot", layout="wide")

    st.sidebar.title("📘 Confluence Chatbot")
    space_key = st.sidebar.text_input("🔹 Confluence Space Key", "DEVOPS")
    page_title = st.sidebar.text_input("🔹 Confluence Page Title", "AWS Deployment Guide")

    if st.sidebar.button("🔄 Load Page & Store Embeddings"):
        page_id = get_page_id_by_title(space_key, page_title)
        if page_id:
            content = fetch_confluence_content(page_id)
            if content:
                text_chunks = process_text(content)
                store_in_chroma(text_chunks)
                st.sidebar.success("✅ Data Loaded into ChromaDB!")
            else:
                st.sidebar.error("❌ Could not fetch content.")
        else:
            st.sidebar.error("❌ Page not found.")

    st.title("💬 Confluence Chatbot")
    user_query = st.text_input("Ask a question about Confluence content:")

    if st.button("🧠 Generate Answer"):
        if user_query:
            response = query_chromadb_rag(user_query)
            st.markdown("### 🔹 AI Response:")
            st.write(response)
        else:
            st.warning("⚠️ Please enter a question.")


if __name__ == "__main__":
    main()
