import os
import chromadb
from sentence_transformers import SentenceTransformer
from core.config.config_manager import get_config

# Local CPU embedding model - same as bytewax-etl service
# Using 'all-MiniLM-L6-v2' to match the embeddings stored in ChromaDB
model = SentenceTransformer('all-MiniLM-L6-v2')

# ChromaDB client setup
# Connect to ChromaDB server running in Docker Compose (service name 'chroma', port 8000)
config = get_config()
chroma_client = chromadb.HttpClient(host=config.chroma.host, port=config.chroma.port)

def embed_text(text):
    """
    Generate an embedding for the given text using the same model as bytewax-etl.
    :param text: str
    :return: list[float] (dim=384)
    """
    embedding = model.encode(text).tolist()
    return embedding

def get_or_create_collection():
    """
    Get or create a ChromaDB collection.
    """
    config = get_config()
    try:
        collection = chroma_client.get_collection(name=config.chroma.collection_name)
    except Exception:
        collection = chroma_client.create_collection(name=config.chroma.collection_name)
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
        include=["documents", "distances", "embeddings", "metadatas"] # Include embeddings and metadatas
    )
    return results