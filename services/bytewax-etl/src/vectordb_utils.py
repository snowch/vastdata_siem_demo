import os
import numpy as np
import uuid
from openai import OpenAI
import chromadb
from chromadb.config import Settings as ChromaSettings

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

def normalize_embedding(embedding):
    """
    L2-normalize the embedding vector.
    :param embedding: list[float] or np.ndarray
    :return: np.ndarray
    """
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return arr
    return arr / norm

def get_or_create_collection():
    """
    Get or create a ChromaDB collection.
    """
    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        collection = chroma_client.create_collection(name=COLLECTION_NAME)
    return collection

def insert_event(text, embedding_raw, embedding_norm):
    """
    Insert a record into ChromaDB.
    :param text: Original event text
    :param embedding_raw: List[float] or np.ndarray, raw embedding (dim=1536)
    :param embedding_norm: List[float] or np.ndarray, normalized embedding (dim=1536)
    """
    collection = get_or_create_collection()
    # ChromaDB expects embeddings as list of floats, documents as list of strings, and ids as list of strings
    doc_id = str(uuid.uuid4())
    collection.add(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding_raw.tolist() if isinstance(embedding_raw, np.ndarray) else embedding_raw]
    )
    # Note: ChromaDB does not support storing multiple embeddings per document natively,
    # so we store only the raw embedding here. If normalized embedding is needed, consider storing as metadata or separate collection.
