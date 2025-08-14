import asyncio
from flask import Flask, request, render_template, jsonify
from triage_service import get_prioritized_task, init_logging
from log_retriever import get_logs
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
web_logger.setLevel(logging.INFO)

def truncate_embedding_recursive(obj, max_dims=5):
    """Recursively truncate any embedding vectors found in nested structures."""
    if isinstance(obj, np.ndarray):
        # Handle 2D numpy arrays (like ChromaDB embeddings with shape (n, embedding_dim))
        if obj.ndim == 2:
            # Each row is an embedding vector - truncate each row to max_dims
            truncated_rows = []
            for row in obj:
                row_list = row.tolist()
                if len(row_list) > max_dims:
                    truncated_row = row_list[:max_dims] + ["..."]
                else:
                    truncated_row = row_list
                truncated_rows.append(truncated_row)
            return truncated_rows
        elif obj.ndim == 1:
            # 1D array - truncate directly
            arr_list = obj.tolist()
            if len(arr_list) > max_dims:
                return arr_list[:max_dims] + ["..."]
            else:
                return arr_list
        else:
            # Higher dimensional arrays - convert to list and recurse
            return truncate_embedding_recursive(obj.tolist(), max_dims)
    elif isinstance(obj, list):
        # Check if this looks like an embedding vector (list of numbers)
        if obj and all(isinstance(x, (int, float, np.number)) for x in obj):
            # This is likely an embedding vector - truncate it
            if len(obj) > max_dims:
                return obj[:max_dims] + ["..."]
            else:
                return obj
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
        logs = get_logs()
        web_logger.info(f"Successfully retrieved {len(logs)} logs")
        return jsonify(logs)
    except Exception as e:
        web_logger.error(f"Error retrieving logs: {str(e)}")
        return jsonify({ "error_retrieving_logs": str(e) }), 500

@app.route('/triage', methods=['POST'])
async def triage_agent():
    web_logger.info("Triage route accessed")
    
    try:
        data = request.get_json()
        
        if data is None:
            web_logger.error("No JSON data received in request")
            return jsonify({"error": "No JSON data provided"}), 400
            
        log_batch = data.get('logs')
        if not log_batch:
            web_logger.error("No logs provided in request data")
            return jsonify({"error": "No logs provided"}), 400

        web_logger.info(f"Processing log batch with {len(str(log_batch))} characters")

        # Run the triage planning stage
        prioritized_task, planner_diagnostics, chroma_results = await get_prioritized_task(json.dumps(log_batch))
        
        web_logger.info("Triage planning completed successfully")

        # Convert markdown to HTML
        prioritized_task_html = markdown.markdown(prioritized_task)
        
        # Sanitize ChromaDB results to handle numpy arrays and truncate embeddings
        sanitized_chroma_results = sanitize_chroma_results(chroma_results)
        
        web_logger.info("Successfully completed triage processing")
        return jsonify({"response": prioritized_task_html, "thought_process": planner_diagnostics, "chroma_results": sanitized_chroma_results})
        
    except json.JSONDecodeError as e:
        web_logger.error(f"JSON decode error: {str(e)}")
        return jsonify({"error": f"Invalid JSON data: {str(e)}"}), 400
    except Exception as e:
        web_logger.error(f"Unexpected error during triage: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure the event loop is managed correctly for Flask and async functions
    # This is a common pattern for running Flask with asyncio
    # For production, consider using Gunicorn with an async worker
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
