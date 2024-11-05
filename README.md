# 🎈 AWS Knowledge Chatbot

A simple Streamlit app template for you to modify!

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```


# Code Explanation

Let's break down each part of the Python code and understand its functionality and logic in detail. This code uses Streamlit to create an AWS Knowledge Base Chatbot, which retrieves relevant information from PDF files based on user queries. The chatbot uses natural language processing (NLP) with the SentenceTransformer model for embedding and cosine similarity for finding the closest match.

### 1. **Importing Libraries**

```python
import streamlit as st
import fitz  # PyMuPDF
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
```

- **Streamlit** (`streamlit`): Used to create a web interface for the chatbot.
- **PyMuPDF** (`fitz`): Used to read and extract text from PDF files.
- **NLTK** (`nltk`): The Natural Language Toolkit is used for NLP tasks such as stop words removal and tokenization.
- **SentenceTransformers**: Used to load a pre-trained model to create embeddings (numerical representations) of text.
- **Cosine Similarity** (`cosine_similarity`): Measures the similarity between two vectors (in this case, the query and paragraph embeddings).

### 2. **Downloading NLTK Data**

```python
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
stop_words = set(stopwords.words("english"))
```

- `punkt` and `stopwords` are downloaded from NLTK to tokenize text into words and remove common words that do not add meaning (e.g., "the," "is," etc.).

### 3. **Loading the Sentence Transformer Model**

```python
model = SentenceTransformer('all-MiniLM-L6-v2')
```

- The `SentenceTransformer` model generates embeddings for sentences and paragraphs. The `all-MiniLM-L6-v2` model is used for its lightweight nature and effectiveness in creating embeddings that can capture the context of a sentence.

### 4. **Text Extraction and Splitting Function**

```python
def extract_and_split_text(pdf_path):
    document_text = ""
    with fitz.open(pdf_path) as doc:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            document_text += page.get_text() + "\n"
```

- `extract_and_split_text(pdf_path)`: This function extracts text from a given PDF file path (`pdf_path`).
- It iterates through each page of the PDF, extracting text using `get_text()` from PyMuPDF.
- The entire document's text is stored in the `document_text` variable.

### 5. **Splitting Text into Sections and Generating Embeddings**

```python
    split_length = len(document_text) // 4
    sections = {
        "overview": document_text[:split_length],
        "getting_started": document_text[split_length:split_length*2],
        "advanced_features": document_text[split_length*2:split_length*3],
        "pricing_and_limitations": document_text[split_length*3:]
    }
```

- **Splitting into Sections**: The text is divided into four sections based on length:
  - `overview`
  - `getting_started`
  - `advanced_features`
  - `pricing_and_limitations`
  
  Each section is created by slicing the `document_text` at 25% intervals.

```python
    section_embeddings = {}
    for section_name, section_text in sections.items():
        paragraphs = section_text.split("\n\n")  # Split by double newline to get paragraphs
        embeddings = model.encode(paragraphs)     # Generate embeddings for each paragraph
        section_embeddings[section_name] = list(zip(paragraphs, embeddings))
```

- **Paragraph Splitting and Embedding**: Each section is split into paragraphs (separated by double newlines), and embeddings are generated for each paragraph using `model.encode(paragraphs)`.
- These embeddings and their corresponding paragraphs are stored in a dictionary `section_embeddings`.

### 6. **Initializing the Knowledge Base**

```python
knowledge_base = {
    "S3": extract_and_split_text("aws-docs/s3.pdf"),
    "EC2": extract_and_split_text("aws-docs/ec2.pdf"),
    "IAM": extract_and_split_text("aws-docs/iam.pdf")
}
```

- `knowledge_base`: A dictionary storing embeddings for each AWS service (e.g., S3, EC2, IAM). Each service is mapped to its respective extracted and embedded content from a PDF.

### 7. **Matching the Query to Text**

```python
def match_query_to_text(service_name, query):
    service_content = knowledge_base.get(service_name, {})
    
    if any(keyword in query.lower() for keyword in ["overview", "introduction", "basics"]):
        section = "overview"
    elif any(keyword in query.lower() for keyword in ["setup", "get started", "usage"]):
        section = "getting_started"
    elif any(keyword in query.lower() for keyword in ["features", "advanced", "details"]):
        section = "advanced_features"
    elif any(keyword in query.lower() for keyword in ["pricing", "cost", "limitations"]):
        section = "pricing_and_limitations"
    else:
        section = None
```

- `match_query_to_text(service_name, query)`: This function determines the best-matching paragraph for the user's query.
- **Keyword Matching**: The function first tries to match the query with keywords to select the most relevant section (`overview`, `getting_started`, etc.). If no keywords match, it will search across all sections.

```python
    query_embedding = model.encode([query])[0]

    best_match = None
    highest_similarity = -1
```

- The `query` is embedded using `model.encode([query])[0]`.
- `best_match` and `highest_similarity` variables are initialized to keep track of the paragraph with the highest similarity.

```python
    sections_to_search = [section] if section else service_content.keys()

    for sec in sections_to_search:
        for paragraph, embedding in service_content[sec]:
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = paragraph
```

- The function iterates over paragraphs within the specified section or all sections if no specific section is matched.
- **Cosine Similarity**: It calculates the similarity between the query and each paragraph embedding. The paragraph with the highest similarity is stored as the `best_match`.

```python
    return best_match if best_match else "I'm sorry, I couldn't find an answer in the PDF content."
```

- If a match is found, `best_match` is returned; otherwise, a default message is returned.

### 8. **Chatbot Interface Function**

```python
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
```

- `aws_chatbot` receives a service name and user question. It attempts to classify the question into predefined parts using keywords, then calls `match_query_to_text` to retrieve the best-matching answer.

### 9. **Streamlit Interface Setup**

```python
st.title("AWS Knowledge Base Chatbot")
st.write("Ask questions related to AWS services like S3, EC2, and IAM based on the PDF knowledge base.")
service_name = st.selectbox("Select AWS Service", ["S3", "EC2", "IAM"])
user_question = st.text_input("Enter your question")
```

- **Streamlit Widgets**: This section defines the chatbot interface, including a title, a dropdown to select an AWS service, and a text input for the user to enter questions.

### 10. **Query Submission**

```python
if st.button("Get Answer"):
    if service_name and user_question:
        response = aws_chatbot(service_name, user_question)
        st.write("**Bot:**", response)
    else:
        st.write("Please select a service and enter a question.")
```

- **Button and Response Display**: When the "Get Answer" button is clicked, the chatbot retrieves an answer using `aws_chatbot` and displays it on the interface.
