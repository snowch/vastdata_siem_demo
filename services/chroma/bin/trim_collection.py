#!/usr/bin/env python3

import chromadb
import argparse
import os
import math

# --- Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Trim a ChromaDB collection to a specified size by deleting the oldest records in batches."
)
parser.add_argument(
    "--keep",
    type=int,
    required=True,
    help="The number of the most recent records to keep in the collection.",
)
parser.add_argument(
    "--batch_size",
    type=int,
    default=5000,
    help="The number of records to delete in each batch.",
)
parser.add_argument(
    "--collection_name",
    type=str,
    default=os.environ.get("CHROMA_COLLECTION", "security_events_dual"),
    help="The name of the collection to modify.",
)
parser.add_argument(
    "--chroma_host",
    type=str,
    default=os.environ.get("CHROMA_HOST", "localhost"),
    help="The hostname or IP address of the ChromaDB server.",
)
parser.add_argument(
    "--chroma_port",
    type=int,
    default=os.environ.get("CHROMA_PORT", 8000),
    help="The port number of the ChromaDB server.",
)

args = parser.parse_args()

# --- Main Execution ---
try:
    # --- Connect to ChromaDB ---
    client = chromadb.HttpClient(host=args.chroma_host, port=args.chroma_port)
    collection = client.get_collection(name=args.collection_name)
    print(f"Successfully connected to collection '{args.collection_name}'.")

    # --- Calculate Deletions ---
    total_count = collection.count()
    
    if total_count <= args.keep:
        print(f"Collection size ({total_count}) is already at or below the desired size ({args.keep}). No action taken.")
        exit(0)
        
    num_to_delete = total_count - args.keep
    num_batches = math.ceil(num_to_delete / args.batch_size)
    
    print(f"Collection contains {total_count} records. Trimming to {args.keep} by deleting {num_to_delete} oldest entries.")
    print(f"This will be done in {num_batches} batches of up to {args.batch_size} records each.")

    # --- Batch Deletion Loop ---
    deleted_count = 0
    for i in range(num_batches):
        print(f"\n--- Processing Batch {i + 1} of {num_batches} ---")
        
        # Determine how many records to fetch in this batch
        limit = min(args.batch_size, num_to_delete - deleted_count)
        
        if limit <= 0:
            print("No more records to delete. Exiting loop.")
            break
            
        print(f"Fetching {limit} oldest record IDs...")
        
        # Fetch only the IDs of the oldest records
        records_to_delete = collection.peek(limit=limit)
        ids_to_delete = records_to_delete.get('ids')
        
        if not ids_to_delete:
            print("Could not retrieve more record IDs to delete. The collection might be smaller than expected. Aborting.")
            break

        # --- Perform Deletion ---
        print(f"Deleting {len(ids_to_delete)} records...")
        collection.delete(ids=ids_to_delete)
        deleted_count += len(ids_to_delete)
        
        print(f"Batch deleted successfully. Total deleted so far: {deleted_count}")

    # --- Final Verification ---
    final_count = collection.count()
    print("\n" + "=" * 50)
    print("Trimming process complete.")
    print(f"Initial record count: {total_count}")
    print(f"Total records deleted: {deleted_count}")
    print(f"Final record count: {final_count}")
    print("=" * 50)


except Exception as e:
    print(f"An error occurred: {e}")