

### 1. **Q: How do you call a Bedrock model like Claude or Titan in Python?**

**A:** Use the `boto3` Bedrock runtime client with `invoke_model()`:

```python
import boto3
import json

client = boto3.client("bedrock-runtime")

response = client.invoke_model(
    modelId="anthropic.claude-v2",
    body=json.dumps({
        "prompt": "\n\nHuman: Tell me a joke\n\nAssistant:",
        "max_tokens_to_sample": 100
    }),
    contentType="application/json",
    accept="application/json"
)

result = json.loads(response['body'].read())
print(result["completion"])
```

---

### 2. **Q: What is the difference between `invoke_model` and `invoke_model_with_response_stream`?**

**A:** `invoke_model` returns the full result after generation, while `invoke_model_with_response_stream` lets you stream chunks of the response as they are generated, useful for real-time applications.

---

### 3. **Q: How do you use `invoke_model_with_response_stream` in Python?**

**A:** Here's how you stream Claude output:

```python
response = client.invoke_model_with_response_stream(
    modelId="anthropic.claude-v2",
    body=json.dumps({
        "prompt": "\n\nHuman: Summarize AI\n\nAssistant:",
        "max_tokens_to_sample": 200
    }),
    contentType="application/json",
    accept="application/json"
)

for event in response['body']:
    chunk = json.loads(event['chunk']['bytes'].decode())
    print(chunk.get("completion", ""), end="")
```

---

### 4. **Q: How do you call Titan Embeddings using Bedrock in Python?**

**A:**

```python
embedding_response = client.invoke_model(
    modelId="amazon.titan-embed-text-v1",
    body=json.dumps({"inputText": "Embedding this sentence"}),
    contentType="application/json",
    accept="application/json"
)

embedding = json.loads(embedding_response['body'].read())["embedding"]
print(embedding)
```

---

### 5. **Q: What is an Application Inference Profile in Bedrock?**

**A:** It's a managed configuration that lets you control logging, request validation, and model behavior using a named profile when calling Bedrock APIs.

---

### 6. **Q: How do you use an Application Inference Profile with `invoke_model()`?**

**A:**

```python
response = client.invoke_model(
    modelId="anthropic.claude-v2",
    body=json.dumps({"prompt": "Hello", "max_tokens_to_sample": 50}),
    contentType="application/json",
    accept="application/json",
    applicationInferenceConfig={
        "profileArn": "arn:aws:bedrock:us-east-1:123456789012:inference-profile/my-profile"
    }
)
```

---

### 7. **Q: How do you split large documents into chunks for embedding in Python?**

**A:** Use LangChain’s `RecursiveCharacterTextSplitter`:

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=25)
chunks = splitter.split_text(large_text)
```

---

### 8. **Q: What is a good chunk size and overlap when using Titan embeddings with ChromaDB?**

**A:** A chunk size of **800 tokens** and an overlap of **25 tokens** works well for preserving context and avoiding semantic gaps between chunks.

---

### 9. **Q: How do you store Titan Embeddings into ChromaDB in Python?**

**A:**

```python
import chromadb
from chromadb.config import Settings

chroma_client = chromadb.Client(Settings())
collection = chroma_client.get_or_create_collection(name="docs")

# Assume `text_chunks` is a list of strings and `get_embedding()` uses Titan
for i, chunk in enumerate(text_chunks):
    embedding = get_embedding(chunk)  # Call to Bedrock Titan Embeddings
    collection.add(
        documents=[chunk],
        ids=[f"doc-{i}"],
        embeddings=[embedding]
    )
```

---

### 10. **Q: How do you retrieve the most similar chunk from ChromaDB for a user query?**

**A:**

```python
query_embedding = get_embedding("What is AI?")
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

for doc in results["documents"][0]:
    print("Match:", doc)
```

---
