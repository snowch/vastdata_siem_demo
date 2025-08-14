import asyncio
from flask import Flask, request, render_template, jsonify
from triage_service import get_prioritized_task, init_logging # Import the refactored functions
from log_retriever import get_logs # Import the new log retriever
# from triage_service import get_prioritized_task, run_investigation_team, init_logging # Import the refactored functions
import json
import os
import markdown
import logging
import traceback
import numpy as np

app = Flask(__name__, template_folder='../templates')

# Initialize logging for the triage service
init_logging()

# Create a dedicated logger for web_ui
web_logger = logging.getLogger("web_ui")
web_logger.setLevel(logging.DEBUG)

# Add console handler for web_ui logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
web_logger.addHandler(console_handler)

# Add file handler for web_ui logger
file_handler = logging.FileHandler('web_ui.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
web_logger.addHandler(file_handler)

def truncate_embedding_recursive(obj, max_dims=5):
    """Recursively truncate any embedding vectors found in nested structures."""
    if isinstance(obj, np.ndarray):
        # Handle 2D numpy arrays (like ChromaDB embeddings with shape (n, embedding_dim))
        if obj.ndim == 2:
            # Each row is an embedding vector - truncate each row to max_dims
            truncated_rows = []
            for row in obj:
                row_list = row.tolist()
                truncated_row = row_list[:max_dims] if len(row_list) > max_dims else row_list
                truncated_rows.append(truncated_row)
            return truncated_rows
        elif obj.ndim == 1:
            # 1D array - truncate directly
            arr_list = obj.tolist()
            return arr_list[:max_dims] if len(arr_list) > max_dims else arr_list
        else:
            # Higher dimensional arrays - convert to list and recurse
            return truncate_embedding_recursive(obj.tolist(), max_dims)
    elif isinstance(obj, list):
        # Check if this looks like an embedding vector (list of numbers)
        if obj and all(isinstance(x, (int, float, np.number)) for x in obj):
            # This is likely an embedding vector - truncate it
            return obj[:max_dims] if len(obj) > max_dims else obj
        else:
            # This is a nested structure - recurse into it
            return [truncate_embedding_recursive(item, max_dims) for item in obj]
    else:
        return obj

def sanitize_chroma_results(chroma_results):
    """Convert numpy arrays in ChromaDB results to lists for JSON serialization and limit embeddings to first 5."""
    if not isinstance(chroma_results, dict):
        return chroma_results
    
    sanitized = {}
    for key, value in chroma_results.items():
        if key == 'embeddings':
            # Apply aggressive truncation to any embedding structures
            sanitized[key] = truncate_embedding_recursive(value, max_dims=5)
        elif isinstance(value, np.ndarray):
            sanitized[key] = value.tolist()
        elif isinstance(value, list):
            # Handle nested lists that might contain numpy arrays
            sanitized[key] = []
            for item in value:
                if isinstance(item, np.ndarray):
                    sanitized[key].append(item.tolist())
                elif isinstance(item, list):
                    # Handle nested lists of numpy arrays
                    nested_list = []
                    for nested_item in item:
                        if isinstance(nested_item, np.ndarray):
                            nested_list.append(nested_item.tolist())
                        else:
                            nested_list.append(nested_item)
                    sanitized[key].append(nested_list)
                else:
                    sanitized[key].append(item)
        else:
            sanitized[key] = value
    
    return sanitized

@app.route('/')
def index():
    web_logger.info("Index route accessed")
    try:
        return render_template('index.html')
    except Exception as e:
        web_logger.error(f"Error rendering index.html: {str(e)}")
        web_logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to load page"}), 500

@app.route('/retrieve_logs', methods=['GET'])
def retrieve_logs():
    web_logger.info("Retrieve logs route accessed")
    try:
        web_logger.debug("Calling get_logs() function")
        logs = get_logs()
        web_logger.info(f"Successfully retrieved logs, type: {type(logs)}")
        web_logger.debug(f"Logs content preview: {str(logs)[:200]}...")
        return jsonify(logs)
    except Exception as e:
        web_logger.error(f"Error retrieving logs: {str(e)}")
        web_logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({ "error_retrieving_logs": str(e) }), 500

@app.route('/triage', methods=['POST'])
async def triage_agent():
    web_logger.info("Triage route accessed")
    
    try:
        # Parse request data
        web_logger.debug("Parsing request JSON")
        data = request.get_json()
        
        if data is None:
            web_logger.error("No JSON data received in request")
            return jsonify({"error": "No JSON data provided"}), 400
            
        web_logger.debug(f"Request data keys: {list(data.keys()) if data else 'None'}")
        log_batch = data.get('logs')

        if not log_batch:
            web_logger.error("No logs provided in request data")
            return jsonify({"error": "No logs provided"}), 400

        web_logger.info(f"Processing log batch, type: {type(log_batch)}, length: {len(str(log_batch))}")
        web_logger.debug(f"Log batch preview: {str(log_batch)[:200]}...")

        # Run the triage planning stage
        web_logger.info("Starting triage planning stage")
        prioritized_task, planner_diagnostics, chroma_results = await get_prioritized_task(json.dumps(log_batch))
        
        web_logger.info("Triage planning completed successfully")
        web_logger.debug(f"Prioritized task length: {len(prioritized_task)}")
        web_logger.debug(f"Planner diagnostics count: {len(planner_diagnostics)}")
        web_logger.debug(f"Chroma results type: {type(chroma_results)}")
        
        # Optionally, run the investigation team and get its output
        # For simplicity, we'll just return the prioritized task for now
        # If you want the full investigation summary, you'd need to modify run_investigation_team
        # to return the assessment_agent's final message.
        # await run_investigation_team(prioritized_task) 

        # Convert markdown to HTML if prioritized_task is markdown
        web_logger.debug("Converting markdown to HTML")
        prioritized_task_html = markdown.markdown(prioritized_task)
        
        # Sanitize ChromaDB results to handle numpy arrays
        web_logger.debug("Sanitizing ChromaDB results for JSON serialization")
        web_logger.debug(f"Original chroma results keys: {list(chroma_results.keys()) if isinstance(chroma_results, dict) else 'Not a dict'}")
        if isinstance(chroma_results, dict) and 'embeddings' in chroma_results:
            embeddings = chroma_results['embeddings']
            web_logger.debug(f"Embeddings type: {type(embeddings)}, length: {len(embeddings) if isinstance(embeddings, list) else 'Not a list'}")
            if isinstance(embeddings, list) and len(embeddings) > 0:
                first_embedding = embeddings[0]
                web_logger.debug(f"First embedding type: {type(first_embedding)}, length: {len(first_embedding) if hasattr(first_embedding, '__len__') else 'No length'}")
                
                # Let's see the actual shape if it's a numpy array
                if isinstance(first_embedding, np.ndarray):
                    web_logger.debug(f"First embedding shape: {first_embedding.shape}")
                    web_logger.debug(f"First embedding first 10 values: {first_embedding[:10].tolist() if len(first_embedding) > 10 else first_embedding.tolist()}")
                
                # Check if it's a nested structure
                if isinstance(first_embedding, list) and len(first_embedding) > 0:
                    inner_embedding = first_embedding[0]
                    web_logger.debug(f"Inner embedding type: {type(inner_embedding)}, length: {len(inner_embedding) if hasattr(inner_embedding, '__len__') else 'No length'}")
                    if isinstance(inner_embedding, (list, np.ndarray)):
                        actual_length = len(inner_embedding)
                        web_logger.debug(f"Actual embedding vector length: {actual_length}")
                        if isinstance(inner_embedding, (list, np.ndarray)) and len(inner_embedding) > 10:
                            web_logger.debug(f"Inner embedding first 10 values: {inner_embedding[:10]}")
        
        sanitized_chroma_results = sanitize_chroma_results(chroma_results)
        web_logger.debug(f"Sanitized chroma results type: {type(sanitized_chroma_results)}")
        if isinstance(sanitized_chroma_results, dict) and 'embeddings' in sanitized_chroma_results:
            sanitized_embeddings = sanitized_chroma_results['embeddings']
            web_logger.debug(f"Sanitized embeddings length: {len(sanitized_embeddings) if isinstance(sanitized_embeddings, list) else 'Not a list'}")
            if isinstance(sanitized_embeddings, list) and len(sanitized_embeddings) > 0:
                first_sanitized = sanitized_embeddings[0]
                web_logger.debug(f"First sanitized embedding length: {len(first_sanitized) if hasattr(first_sanitized, '__len__') else 'No length'}")
        
        web_logger.info("Successfully completed triage processing")
        return jsonify({"response": prioritized_task_html, "thought_process": planner_diagnostics, "chroma_results": sanitized_chroma_results})
        
    except json.JSONDecodeError as e:
        web_logger.error(f"JSON decode error: {str(e)}")
        web_logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Invalid JSON data: {str(e)}"}), 400
    except Exception as e:
        web_logger.error(f"Unexpected error during triage: {str(e)}")
        web_logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure the event loop is managed correctly for Flask and async functions
    # This is a common pattern for running Flask with asyncio
    # For production, consider using Gunicorn with an async worker
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
