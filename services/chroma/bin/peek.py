#!/usr/bin/env python3
import chromadb
import random
from rich import print as rprint

chroma_client = chromadb.HttpClient(host='localhost', port=8000)

def count_records_in_collection(collection_name: str):
    """
    Gets the count of records/rows in a specified ChromaDB collection.
    """
    try:
        collection = chroma_client.get_or_create_collection(name=collection_name)
        # Get the count of records in the collection
        record_count = collection.count()
        print(f"Collection '{collection_name}' contains {record_count} records/rows.")
        return record_count
    except Exception as e:
        print(f"An error occurred while counting records in collection '{collection_name}': {e}")
        return None

def get_random_record(collection_name: str):
    """
    Gets a random record from the specified ChromaDB collection.
    """
    try:
        collection = chroma_client.get_or_create_collection(name=collection_name)
        
        # Get total count first
        total_count = collection.count()
        
        if total_count == 0:
            print(f"No records found in collection '{collection_name}'")
            return None
        
        print(f"Getting random record from {total_count} total records...")
        
        # Get all records (this is the most reliable way with ChromaDB)
        # For large collections, you might want to implement pagination
        all_records = collection.get(include=['documents', 'embeddings', 'metadatas'])
        
        if not all_records['ids']:
            print("No records retrieved")
            return None
        
        # Pick a random index
        random_index = random.randint(0, len(all_records['ids']) - 1)
        
        print(f"\n--- Random Record (Index: {random_index}) ---")
        rprint(f"ID: {all_records['ids'][random_index]}")
        rprint(f"Document: {all_records['documents'][random_index] if all_records['documents'] else 'No document'}")
        rprint(f"Metadata: {all_records['metadatas'][random_index] if all_records['metadatas'] else 'No metadata'}")
        
        # If embeddings are available, show first few dimensions
        embeddings = all_records.get('embeddings')
        if embeddings is not None and len(embeddings) > 0:
            embedding = embeddings[random_index]
            if embedding is not None and hasattr(embedding, '__len__') and len(embedding) > 0:
                print(f"Embedding (first 5 dims): {embedding[:5]}...")
                print(f"Embedding dimensions: {len(embedding)}")
            else:
                print("Embeddings: None")
        else:
            print("Embeddings: None")
        
        return {
            'id': all_records['ids'][random_index],
            'document': all_records['documents'][random_index] if all_records['documents'] else None,
            'metadata': all_records['metadatas'][random_index] if all_records['metadatas'] else None,
            'embedding': embeddings[random_index] if embeddings is not None and len(embeddings) > random_index else None
        }
        
    except Exception as e:
        print(f"An error occurred while getting random record from collection '{collection_name}': {e}")
        return None

if __name__ == "__main__":
    print("ChromaDB Record Count and Random Sample Tool")
    print("=" * 50)
    
    collection_name = "security_events_dual"
    
    # Count records
    count_records_in_collection(collection_name)
    
    print("\n" + "=" * 50)
    
    # Get one random record
    get_random_record(collection_name)
