import asyncio
from flask import Flask, request, render_template, jsonify, Response
from triage_service import get_prioritized_task, init_logging
from log_retriever import get_logs
import json
import os
import markdown
import logging
import traceback
import numpy as np
import threading
import time
from datetime import datetime

app = Flask(__name__, template_folder='../templates')

# Initialize logging for the triage service
init_logging()

# Create a dedicated logger for web_ui
web_logger = logging.getLogger("web_ui")
web_logger.setLevel(logging.INFO)

# Global store for progress tracking
progress_store = {}

class AnalysisProgress:
    def __init__(self, session_id):
        self.session_id = session_id
        self.status = "initializing"
        self.current_agent = None
        self.agent_outputs = {
            'triage': [],
            'context': [],
            'analyst': []
        }
        self.progress_percent = 0
        self.error = None
        self.completed = False
        self.start_time = datetime.now()
        
    def update_status(self, status, agent=None, message=None, progress=None):
        self.status = status
        if agent:
            self.current_agent = agent
        if message and agent:
            self.agent_outputs[agent].append({
                'timestamp': datetime.now().isoformat(),
                'message': message
            })
        if progress is not None:
            self.progress_percent = progress

def truncate_embedding_recursive(obj, max_dims=5):
    """Recursively truncate any embedding vectors found in nested structures."""
    if isinstance(obj, np.ndarray):
        if obj.ndim == 2:
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
            arr_list = obj.tolist()
            if len(arr_list) > max_dims:
                return arr_list[:max_dims] + ["..."]
            else:
                return arr_list
        else:
            return truncate_embedding_recursive(obj.tolist(), max_dims)
    elif isinstance(obj, list):
        if obj and all(isinstance(x, (int, float, np.number)) for x in obj):
            if len(obj) > max_dims:
                return obj[:max_dims] + ["..."]
            else:
                return obj
        else:
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
            sanitized[key] = truncate_embedding_recursive(value, max_dims=5)
        elif isinstance(value, np.ndarray):
            sanitized[key] = value.tolist()
        elif isinstance(value, list):
            sanitized[key] = []
            for item in value:
                if isinstance(item, np.ndarray):
                    sanitized[key].append(item.tolist())
                elif isinstance(item, list):
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

def parse_agent_conversation(conversation):
    """Parse the conversation string to extract individual agent outputs."""
    lines = conversation.split('\n')
    agent_outputs = {'triage': [], 'context': [], 'analyst': []}
    current_agent = None
    current_message = []
    
    agent_mapping = {
        'TriageSpecialist': 'triage',
        'ContextAgent': 'context',
        'SeniorAnalyst': 'analyst'
    }
    
    for line in lines:
        # Check if line contains agent identifier
        agent_found = None
        for agent_name, agent_key in agent_mapping.items():
            if f'[{agent_name}]' in line:
                agent_found = agent_key
                break
        
        if agent_found:
            # Save previous agent's message if exists
            if current_agent and current_message:
                message_text = '\n'.join(current_message).strip()
                if message_text:
                    agent_outputs[current_agent].append(message_text)
            
            # Start new agent message
            current_agent = agent_found
            current_message = [line]
        elif current_agent and line.strip():
            current_message.append(line)
    
    # Don't forget the last message
    if current_agent and current_message:
        message_text = '\n'.join(current_message).strip()
        if message_text:
            agent_outputs[current_agent].append(message_text)
    
    return agent_outputs

async def run_analysis_with_progress(log_batch, session_id):
    """Run analysis with progress tracking."""
    progress = progress_store[session_id]
    
    try:
        progress.update_status("starting", progress=10)
        web_logger.info(f"Starting analysis for session {session_id}")
        
        # Run the actual analysis
        progress.update_status("running_triage", "triage", "Starting initial triage analysis...", 20)
        
        # Execute the team workflow
        full_conversation, structured_findings, chroma_context = await get_prioritized_task(log_batch)
        
        # Parse the conversation to extract agent outputs
        agent_outputs = parse_agent_conversation(full_conversation)
        
        # Update progress with agent outputs
        progress.update_status("completed_triage", "triage", "Triage analysis completed", 40)
        for output in agent_outputs['triage']:
            progress.agent_outputs['triage'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        
        progress.update_status("running_context", "context", "Searching historical incidents...", 60)
        for output in agent_outputs['context']:
            progress.agent_outputs['context'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        
        progress.update_status("running_analyst", "analyst", "Performing deep analysis...", 80)
        for output in agent_outputs['analyst']:
            progress.agent_outputs['analyst'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        
        # Store final results
        progress.final_results = {
            'conversation': full_conversation,
            'structured_findings': structured_findings,
            'chroma_context': sanitize_chroma_results(chroma_context)
        }
        
        progress.update_status("completed", progress=100)
        progress.completed = True
        
        web_logger.info(f"Analysis completed for session {session_id}")
        
    except Exception as e:
        web_logger.error(f"Analysis failed for session {session_id}: {str(e)}")
        web_logger.error(f"Traceback: {traceback.format_exc()}")
        progress.error = str(e)
        progress.update_status("error", progress=100)

@app.route('/')
def index():
    web_logger.info("Index route accessed")
    try:
        # Serve the new dashboard HTML directly
        with open('dashboard.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        # Fallback to template if file doesn't exist
        try:
            return render_template('index.html')
        except Exception as e:
            web_logger.error(f"Error rendering page: {str(e)}")
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
def triage_agent():
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

        # Create session ID and progress tracker
        session_id = f"session_{int(time.time())}"
        progress_store[session_id] = AnalysisProgress(session_id)
        
        # Start analysis in background thread
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_analysis_with_progress(log_batch, session_id))
            loop.close()
        
        thread = threading.Thread(target=run_async)
        thread.daemon = True
        thread.start()
        
        # Return session ID for progress tracking
        return jsonify({
            "session_id": session_id,
            "status": "analysis_started",
            "message": "Analysis started successfully. Use /progress endpoint to track status."
        })
        
    except json.JSONDecodeError as e:
        web_logger.error(f"JSON decode error: {str(e)}")
        return jsonify({"error": f"Invalid JSON data: {str(e)}"}), 400
    except Exception as e:
        web_logger.error(f"Unexpected error during triage: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/progress/<session_id>')
def get_progress(session_id):
    """Get current progress for a session."""
    if session_id not in progress_store:
        return jsonify({"error": "Session not found"}), 404
    
    progress = progress_store[session_id]
    
    response_data = {
        "session_id": session_id,
        "status": progress.status,
        "current_agent": progress.current_agent,
        "progress_percent": progress.progress_percent,
        "agent_outputs": progress.agent_outputs,
        "completed": progress.completed,
        "error": progress.error,
        "start_time": progress.start_time.isoformat()
    }
    
    # Include final results if completed
    if progress.completed and hasattr(progress, 'final_results'):
        response_data["results"] = progress.final_results
    
    return jsonify(response_data)

@app.route('/progress_stream/<session_id>')
def progress_stream(session_id):
    """Server-sent events stream for real-time progress updates."""
    if session_id not in progress_store:
        return jsonify({"error": "Session not found"}), 404
    
    def event_stream():
        progress = progress_store[session_id]
        last_update_time = time.time()
        
        while not progress.completed and not progress.error:
            current_time = time.time()
            
            # Send update every 2 seconds or when status changes
            if current_time - last_update_time >= 2:
                data = {
                    "status": progress.status,
                    "current_agent": progress.current_agent,
                    "progress_percent": progress.progress_percent,
                    "agent_outputs": progress.agent_outputs
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                last_update_time = current_time
            
            time.sleep(0.5)
        
        # Send final update
        final_data = {
            "status": progress.status,
            "progress_percent": progress.progress_percent,
            "completed": progress.completed,
            "error": progress.error,
            "agent_outputs": progress.agent_outputs
        }
        
        if progress.completed and hasattr(progress, 'final_results'):
            final_data["results"] = progress.final_results
        
        yield f"data: {json.dumps(final_data)}\n\n"
        
        # Clean up old sessions after completion
        if session_id in progress_store:
            # Keep for 5 minutes after completion for result retrieval
            def cleanup():
                time.sleep(300)  # 5 minutes
                if session_id in progress_store:
                    del progress_store[session_id]
            
            cleanup_thread = threading.Thread(target=cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
    
    return Response(event_stream(), mimetype="text/plain")

# Legacy endpoint for backward compatibility
@app.route('/triage_sync', methods=['POST'])
async def triage_agent_sync():
    """Synchronous triage endpoint for backward compatibility."""
    web_logger.info("Synchronous triage route accessed")
    
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({"error": "No JSON data provided"}), 400
            
        log_batch = data.get('logs')
        if not log_batch:
            return jsonify({"error": "No logs provided"}), 400

        # Run analysis synchronously
        prioritized_task, structured_findings, chroma_results = await get_prioritized_task(json.dumps(log_batch))
        
        # Convert markdown to HTML
        prioritized_task_html = markdown.markdown(prioritized_task)
        
        # Sanitize ChromaDB results
        sanitized_chroma_results = sanitize_chroma_results(chroma_results)
        
        return jsonify({
            "response": prioritized_task_html, 
            "chroma_results": sanitized_chroma_results,
            "structured_findings": structured_findings
        })
        
    except Exception as e:
        web_logger.error(f"Unexpected error during sync triage: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)