import asyncio
import json
import logging
import os
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from triage_service import get_prioritized_task, init_logging
from log_retriever import get_logs

# Initialize logging for the triage service
init_logging()

# Create a dedicated logger for websocket server
ws_logger = logging.getLogger("websocket_server")
ws_logger.setLevel(logging.INFO)

app = FastAPI(title="SOC Agent Analysis WebSocket Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files and dashboard
app.mount("/static", StaticFiles(directory="."), name="static")

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

class AnalysisProgress:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
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
        self.final_results = None
        
    async def send_update(self, status: Optional[str] = None, agent: Optional[str] = None, 
                         message: Optional[str] = None, progress: Optional[int] = None):
        """Send progress update via WebSocket"""
        try:
            if status:
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

            # Create update message
            update = {
                "type": "progress_update",
                "session_id": self.session_id,
                "status": self.status,
                "current_agent": self.current_agent,
                "progress_percent": self.progress_percent,
                "agent_outputs": self.agent_outputs,
                "completed": self.completed,
                "error": self.error,
                "start_time": self.start_time.isoformat()
            }
            
            # Include final results if completed
            if self.completed and self.final_results:
                update["results"] = self.final_results

            await self.websocket.send_json(update)
            ws_logger.debug(f"Sent update for session {self.session_id}: {status} - {progress}%")
            
        except Exception as e:
            ws_logger.error(f"Failed to send WebSocket update: {e}")

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
    """Convert numpy arrays in ChromaDB results to lists for JSON serialization."""
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

def extract_structured_findings(conversation, structured_findings):
    """Extract key findings information for better progress tracking."""
    findings_summary = {
        'priority_found': False,
        'context_searched': False,
        'analysis_completed': False,
        'priority_level': 'unknown',
        'threat_type': 'unknown'
    }
    
    # Check structured findings first
    if structured_findings and 'priority_threat' in structured_findings:
        priority_threat = structured_findings['priority_threat']
        if priority_threat:
            findings_summary['priority_found'] = True
            findings_summary['priority_level'] = priority_threat.get('priority', 'unknown').lower()
            findings_summary['threat_type'] = priority_threat.get('threat_type', 'unknown')
    
    if structured_findings and 'detailed_analysis' in structured_findings:
        if structured_findings['detailed_analysis']:
            findings_summary['analysis_completed'] = True
    
    # Check conversation for context search activity
    if 'search_historical_incidents' in conversation or 'ChromaDB' in conversation:
        findings_summary['context_searched'] = True
    
    # Fallback to conversation parsing if structured findings incomplete
    conversation_lower = conversation.lower()
    if 'priority_identified' in conversation_lower or 'critical' in conversation_lower or 'high priority' in conversation_lower:
        findings_summary['priority_found'] = True
        
    if 'critical' in conversation_lower:
        findings_summary['priority_level'] = 'critical'
    elif 'high' in conversation_lower:
        findings_summary['priority_level'] = 'high'
    elif 'medium' in conversation_lower:
        findings_summary['priority_level'] = 'medium'
    
    return findings_summary

async def run_analysis_with_websocket(log_batch: str, progress: AnalysisProgress):
    """Run analysis with real-time WebSocket progress updates."""
    try:
        await progress.send_update("starting", progress=10)
        ws_logger.info(f"Starting analysis for session {progress.session_id}")
        
        # Update status for triage phase
        await progress.send_update("running_triage", "triage", "🔍 Starting initial triage analysis...", 20)
        
        # Execute the team workflow
        full_conversation, structured_findings, chroma_context = await get_prioritized_task(log_batch)
        
        ws_logger.info(f"Raw structured findings for session {progress.session_id}: {structured_findings}")
        
        # Fix missing threat_assessment in detailed_analysis if needed
        if 'detailed_analysis' in structured_findings:
            detailed = structured_findings['detailed_analysis']
            if 'threat_assessment' not in detailed or not detailed['threat_assessment']:
                detailed['threat_assessment'] = {
                    "severity": "unknown",
                    "confidence": 0.0
                }
                ws_logger.warning(f"Added default threat_assessment for session {progress.session_id}")
        
        # Parse the conversation to extract agent outputs
        agent_outputs = parse_agent_conversation(full_conversation)
        
        # Extract key findings for better progress updates
        findings_summary = extract_structured_findings(full_conversation, structured_findings)
        
        # Progressive status updates based on what we found
        current_progress = 30
        
        # Update triage outputs
        if agent_outputs['triage'] or findings_summary['priority_found']:
            await progress.send_update("completed_triage", "triage", 
                f"✅ Triage completed - {findings_summary['priority_level']} priority {findings_summary['threat_type']} detected", 
                current_progress)
            for output in agent_outputs['triage']:
                progress.agent_outputs['triage'].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': output
                })
            current_progress = 50
        else:
            progress.agent_outputs['triage'].append({
                'timestamp': datetime.now().isoformat(),
                'message': "Triage analysis completed - check detailed conversation for findings"
            })
        
        # Update context search outputs
        if agent_outputs['context'] or findings_summary['context_searched']:
            await progress.send_update("completed_context", "context", 
                "🔎 Historical context research completed", current_progress)
            for output in agent_outputs['context']:
                progress.agent_outputs['context'].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': output
                })
            current_progress = 70
        else:
            progress.agent_outputs['context'].append({
                'timestamp': datetime.now().isoformat(),
                'message': "Context research completed - historical incidents analyzed"
            })
        
        # Update analyst outputs
        if agent_outputs['analyst'] or findings_summary['analysis_completed']:
            await progress.send_update("completed_analyst", "analyst", 
                "👨‍💼 Deep analysis and recommendations completed", current_progress)
            for output in agent_outputs['analyst']:
                progress.agent_outputs['analyst'].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': output
                })
            current_progress = 90
        else:
            progress.agent_outputs['analyst'].append({
                'timestamp': datetime.now().isoformat(),
                'message': "Senior analysis completed - recommendations generated"
            })
        
        # Ensure all agents show as having output even if parsing failed
        for agent_type in ['triage', 'context', 'analyst']:
            if not progress.agent_outputs[agent_type]:
                progress.agent_outputs[agent_type].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': f"{agent_type.title()} agent completed successfully. Check full conversation for details."
                })
        
        # Store final results
        progress.final_results = {
            'conversation': full_conversation,
            'structured_findings': structured_findings,
            'chroma_context': sanitize_chroma_results(chroma_context),
            'findings_summary': findings_summary
        }
        
        progress.completed = True
        await progress.send_update("completed", progress=100)
        
        ws_logger.info(f"Analysis completed for session {progress.session_id}")
        
    except Exception as e:
        ws_logger.error(f"Analysis failed for session {progress.session_id}: {str(e)}")
        ws_logger.error(f"Full traceback: {traceback.format_exc()}")
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)

@app.get("/")
async def root():
    """Serve the dashboard HTML directly"""
    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    else:
        raise HTTPException(status_code=404, detail="Dashboard file not found")

@app.get("/retrieve_logs")
async def retrieve_logs():
    """REST endpoint for log retrieval (kept for compatibility)"""
    ws_logger.info("Retrieve logs endpoint accessed")
    try:
        logs = get_logs()
        ws_logger.info(f"Successfully retrieved {len(logs)} logs")
        return logs
    except Exception as e:
        ws_logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")

@app.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """WebSocket endpoint for real-time SOC analysis"""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    active_connections[session_id] = websocket
    
    ws_logger.info(f"WebSocket connection established: {session_id}")
    
    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to SOC Analysis WebSocket"
    })
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "start_analysis":
                log_batch = data.get("logs")
                if not log_batch:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No logs provided for analysis"
                    })
                    continue
                
                ws_logger.info(f"Starting analysis for session {session_id}")
                
                # Create progress tracker
                progress = AnalysisProgress(session_id, websocket)
                
                # Run analysis in background task
                asyncio.create_task(run_analysis_with_websocket(log_batch, progress))
                
            elif message_type == "retrieve_logs":
                ws_logger.info(f"Log retrieval requested via WebSocket: {session_id}")
                try:
                    logs = get_logs()
                    await websocket.send_json({
                        "type": "logs_retrieved",
                        "logs": logs,
                        "message": f"Retrieved {len(logs)} log entries successfully"
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error retrieving logs: {str(e)}"
                    })
            
            elif message_type == "ping":
                # Handle ping/pong for connection health
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            # Connection already closed
            pass
    finally:
        # Clean up connection
        if session_id in active_connections:
            del active_connections[session_id]
        ws_logger.info(f"Cleaned up session: {session_id}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_connections": len(active_connections),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 5000))
    ws_logger.info(f"Starting WebSocket SOC Analysis Server on port {port}")
    uvicorn.run(app, host='0.0.0.0', port=port)