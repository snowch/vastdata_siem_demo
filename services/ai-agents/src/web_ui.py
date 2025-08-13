import asyncio
from flask import Flask, request, render_template, jsonify
from triage_service import get_prioritized_task, init_logging # Import the refactored functions
from log_retriever import get_logs # Import the new log retriever
# from triage_service import get_prioritized_task, run_investigation_team, init_logging # Import the refactored functions
import json
import os
import markdown

app = Flask(__name__, template_folder='../templates')

# Initialize logging for the triage service
init_logging()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/retrieve_logs', methods=['GET'])
def retrieve_logs():
    try:
        logs = get_logs()
        return jsonify(logs)
    except Exception as e:
        return jsonify({ "error_retrieving_logs": str(e) })

@app.route('/triage', methods=['POST'])
async def triage_agent():
    data = request.get_json()
    log_batch = data.get('logs')

    if not log_batch:
        return jsonify({"error": "No logs provided"}), 400

    try:
        # Run the triage planning stage
        prioritized_task, planner_diagnostics = await get_prioritized_task(json.dumps(log_batch))
        
        # Optionally, run the investigation team and get its output
        # For simplicity, we'll just return the prioritized task for now
        # If you want the full investigation summary, you'd need to modify run_investigation_team
        # to return the assessment_agent's final message.
        # await run_investigation_team(prioritized_task) 

        # Convert markdown to HTML if prioritized_task is markdown
        prioritized_task_html = markdown.markdown(prioritized_task)

        return jsonify({"response": prioritized_task_html, "thought_process": planner_diagnostics})
    except Exception as e:
        print(f"Error during triage: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure the event loop is managed correctly for Flask and async functions
    # This is a common pattern for running Flask with asyncio
    # For production, consider using Gunicorn with an async worker
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
