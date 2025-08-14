import os
import numpy as np
import uuid
import logging
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings as ChromaSettings

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Local CPU embedding model
# Using 'all-MiniLM-L6-v2' as a good balance of performance and size for CPU
model = SentenceTransformer('all-MiniLM-L6-v2')

# ChromaDB client setup
# Connect to ChromaDB server running in Docker Compose (service name 'chroma', port 8000)
chroma_client = chromadb.HttpClient(host="chroma", port=8000)

COLLECTION_NAME = "security_events_dual"

def embed_text(text):
    """
    Generate an embedding for the given text using a local CPU model.
    :param text: str
    :return: list[float] (dim=384 for all-MiniLM-L6-v2)
    """
    logger.debug(f"Generating embedding for text: {text[:50]}...")
    embedding = model.encode(text).tolist()
    logger.debug(f"Embedding (first 5 dims): {embedding[:5]}...")
    return embedding

def get_or_create_collection():
    """
    Get or create a ChromaDB collection.
    """
    logger.info(f"Attempting to get or create ChromaDB collection: {COLLECTION_NAME}")
    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        logger.info(f"Collection '{COLLECTION_NAME}' retrieved successfully.")
    except Exception as e:
        logger.warning(f"Collection '{COLLECTION_NAME}' not found, creating it. Error: {e}")
        collection = chroma_client.create_collection(name=COLLECTION_NAME)
        logger.info(f"Collection '{COLLECTION_NAME}' created successfully.")
    return collection

def insert_event(text):
    """
    Insert a record into ChromaDB.
    :param text: Original event text
    :param embedding_raw: List[float] or np.ndarray, raw embedding (dim=1536)
    :param embedding_norm: List[float] or np.ndarray, normalized embedding (dim=1536)
    """
    logger.info(f"Inserting event into ChromaDB for text: {text[:50]}...")
    collection = get_or_create_collection()
    doc_id = str(uuid.uuid4())

    embedding_raw = embed_text(text)
    logger.debug(f"Embedding type: {type(embedding_raw)}, length: {len(embedding_raw)}")

    try:
        collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=[embedding_raw]
        )
        logger.info(f"Event with ID '{doc_id}' inserted successfully into collection '{COLLECTION_NAME}'.")
        logger.info(f"Current collection count: {collection.count()}")
    except Exception as e:
        logger.error(f"Failed to insert event with ID '{doc_id}'. Error: {e}")
    # Note: ChromaDB does not support storing multiple embeddings per document natively,
    # so we store only the raw embedding here. If normalized embedding is needed, consider storing as metadata or separate collection.
