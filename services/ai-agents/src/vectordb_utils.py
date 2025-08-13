import os
from openai import OpenAI
import chromadb

# OpenAI embeddings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# ChromaDB client setup
# Connect to ChromaDB server running in Docker Compose (service name 'chroma', port 8000)
chroma_client = chromadb.HttpClient(host="chroma", port=8000)

COLLECTION_NAME = "security_events_dual"

def embed_text(text):
    """
    Generate an embedding for the given text using OpenAI.
    :param text: str
    :return: list[float] (dim=1536)
    """
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return resp.data[0].embedding

def get_or_create_collection():
    """
    Get or create a ChromaDB collection.
    """
    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        collection = chroma_client.create_collection(name=COLLECTION_NAME)
    return collection

def search_chroma(query_text, n_results=5):
    """
    Search ChromaDB for the top-N most similar documents to the query_text.
    :param query_text: str, the query to embed and search
    :param n_results: int, number of top results to return
    :return: dict with keys 'documents', 'ids', 'distances', etc.
    """
    collection = get_or_create_collection()
    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "distances"]
    )
    return results
