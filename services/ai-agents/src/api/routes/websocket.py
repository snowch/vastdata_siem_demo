# services/ai-agents/src/api/routes/websocket.py - THIRD UPDATE
# Remove complex AnalysisProgress class - use simplified session management

import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.services.agent_service import run_analysis_workflow
from infrastructure.trino_db_reader import get_logs
import logging

router = APIRouter()
ws_logger = logging.getLogger("websocket_server")

# Store active WebSocket sessions - much simpler now
active_sessions = {}

class SimplifiedSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.user_input_future = None
        self.current_approval_stage = None
        self.approval_history = []

async def request_user_approval(prompt: str, session_id: str) -> str:
    """Simplified user approval function"""
    ws_logger.info(f"Requesting user approval for session {session_id}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found in active sessions")
        return "approve"
    
    session = active_sessions[session_id]
    
    try:
        # Determine approval stage based on prompt content
        approval_stage = determine_approval_stage(prompt)
        session.current_approval_stage = approval_stage
        
        ws_logger.info(f"Approval stage determined as: {approval_stage} for session {session_id}")
        
        # Create a future to wait for user input
        session.user_input_future = asyncio.Future()
        
        # Send approval request - simplified format
        user_input_event = {
            "type": "UserInputRequestedEvent",
            "content": prompt,
            "source": f"{approval_stage.title()}Agent" if approval_stage != "unknown" else "ApprovalAgent",
            "approval_stage": approval_stage,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        ws_logger.info(f"Sending approval request: {user_input_event}")
        await session.websocket.send_json(user_input_event)
        
        # Wait for user response with timeout
        try:
            user_response = await asyncio.wait_for(
                session.user_input_future, 
                timeout=300.0  # 5 minute timeout
            )
            
            # Record approval in history
            session.approval_history.append({
                "stage": approval_stage,
                "prompt": prompt,
                "response": user_response,
                "timestamp": datetime.now().isoformat()
            })
            
            ws_logger.info(f"User response received for {approval_stage} stage in session {session_id}: {user_response}")
            return user_response
            
        except asyncio.TimeoutError:
            ws_logger.warning(f"User approval timeout for {approval_stage} stage in session {session_id}")
            return "approve"  # Auto-approve on timeout
            
    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected while waiting for user input")
        raise
    except Exception as e:
        ws_logger.error(f"Error requesting user approval: {e}")
        return "approve"

def determine_approval_stage(prompt: str) -> str:
    """Determine which approval stage based on the prompt content."""
    prompt_lower = prompt.lower()
    
    # Triage stage indicators
    if any(keyword in prompt_lower for keyword in [
        "priority threat", "investigate this", "brute force", "attack detected",
        "proceed with investigating", "high priority", "critical threat"
    ]):
        return "triage"
    
    # Context stage indicators  
    elif any(keyword in prompt_lower for keyword in [
        "historical incidents", "similar incidents", "context", "past incidents",
        "relevant to the current analysis", "historical context", "found incidents"
    ]):
        return "context"
    
    # Analyst stage indicators
    elif any(keyword in prompt_lower for keyword in [
        "recommend", "actions", "authorize", "recommendations", "implement",
        "block ip", "reset passwords", "remediation", "containment"
    ]):
        return "analyst"
    
    return "unknown"

async def real_time_message_callback(message_data: dict):
    """
    Simplified callback function to handle real-time agent messages.
    """
    session_id = message_data.get('session_id')
    if not session_id or session_id not in active_sessions:
        ws_logger.error(f"Invalid session ID in real-time callback: {session_id}")
        return
    
    session = active_sessions[session_id]
    message_type = message_data.get('type')
    
    try:
        ws_logger.debug(f"Real-time message callback: {message_type} for session {session_id}")
        
        # Send all real-time messages directly to frontend
        if message_type in [
            'real_time_agent_output',
            'function_call_detected', 
            'priority_findings',
            'context_results',
            'analysis_complete',
            'workflow_rejected',
            'analysis_complete_final',
            'UserInputRequestedEvent'
        ]:
            await session.websocket.send_json(message_data)
            ws_logger.debug(f"Sent {message_type} to session {session_id}")
        
    except Exception as e:
        ws_logger.error(f"Error in real-time message callback for session {session_id}: {e}")

async def run_simplified_analysis(log_batch: str, session_id: str):
    """
    Simplified analysis runner - no complex progress object needed.
    """
    try:
        ws_logger.info(f"Starting simplified analysis for session {session_id}")
        
        # Run analysis workflow - it will send specific events via callback
        success = await run_analysis_workflow(
            log_batch=log_batch,
            session_id=session_id,
            user_input_callback=request_user_approval,
            message_callback=real_time_message_callback
        )
        
        # Send simple completion message
        if session_id in active_sessions:
            await active_sessions[session_id].websocket.send_json({
                "type": "analysis_workflow_complete", 
                "was_rejected": not success,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
        
        ws_logger.info(f"Simplified analysis completed for session {session_id} - Success: {success}")
        
    except Exception as e:
        ws_logger.error(f"Simplified analysis failed for session {session_id}: {str(e)}")
        if session_id in active_sessions:
            try:
                await active_sessions[session_id].websocket.send_json({
                    "type": "error",
                    "content": f"Analysis error: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id
                })
            except Exception as send_error:
                ws_logger.error(f"Failed to send error message: {send_error}")

async def handle_user_input_response(data: dict, session_id: str):
    """Simplified user input response handler."""
    content = data.get("content", "")
    target_agent = data.get("target_agent", "")
    
    ws_logger.info(f"User input response for session {session_id}, target: {target_agent}, content: {content}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found for user input")
        return
    
    session = active_sessions[session_id]
    
    if session.user_input_future and not session.user_input_future.done():
        # Process the response based on current approval stage
        processed_response = process_approval_response(content, target_agent, session.current_approval_stage)
        session.user_input_future.set_result(processed_response)
        ws_logger.info(f"User input processed for session {session_id}")
    else:
        ws_logger.warning(f"No pending user input request for session {session_id}")

def process_approval_response(content: str, target_agent: str, approval_stage: str) -> str:
    """Process approval response based on the stage and content."""
    content_lower = content.lower().strip()
    
    # Handle standard responses
    if content_lower in ['approve', 'approved', 'yes', 'continue']:
        return f"APPROVED - {approval_stage.title()} stage approved. Proceed to next stage."
    elif content_lower in ['reject', 'rejected', 'no', 'stop', 'cancel']:
        return f"REJECTED - {approval_stage.title()} stage rejected. WORKFLOW_REJECTED"
    elif content_lower.startswith('custom:'):
        custom_instructions = content[7:].strip()
        return f"CUSTOM - User provided specific instructions for {approval_stage} stage: {custom_instructions}"
    else:
        # Treat as custom instructions
        return f"CUSTOM - User response for {approval_stage} stage: {content}"

async def handle_start_analysis(data: dict, session_id: str, websocket: WebSocket):
    """Simplified start analysis handler"""
    log_batch = data.get("logs")
    if not log_batch:
        await websocket.send_json({
            "type": "error",
            "message": "No logs provided for analysis"
        })
        return

    ws_logger.info(f"Starting simplified analysis workflow for session {session_id}")

    # Start analysis task - no complex progress object needed
    asyncio.create_task(run_simplified_analysis(log_batch, session_id))

async def handle_retrieve_logs(session_id: str, websocket: WebSocket):
    """Handle log retrieval request"""
    ws_logger.info(f"Log retrieval requested via WebSocket: {session_id}")
    try:
        logs = get_logs()
        await websocket.send_json({
            "type": "logs_retrieved",
            "logs": logs,
            "message": f"Retrieved {len(logs)} log entries successfully"
        })
        ws_logger.info(f"Successfully sent {len(logs)} logs to session {session_id}")
    except Exception as e:
        ws_logger.error(f"Error retrieving logs for session {session_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Server error: {str(e)}"
        })

async def handle_ping(websocket: WebSocket):
    """Handle ping request"""
    try:
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
        ws_logger.debug("Sent pong response")
    except Exception as e:
        ws_logger.error(f"Error sending pong response: {e}")

async def handle_get_approval_history(session_id: str, websocket: WebSocket):
    """Get approval history for the session"""
    try:
        session = active_sessions.get(session_id)
        if session:
            await websocket.send_json({
                "type": "approval_history",
                "history": session.approval_history,
                "current_stage": session.current_approval_stage
            })
            ws_logger.info(f"Sent approval history for session {session_id}: {len(session.approval_history)} entries")
        else:
            await websocket.send_json({
                "type": "approval_history",
                "history": [],
                "current_stage": None
            })
            ws_logger.warning(f"No session found for approval history request: {session_id}")
    except Exception as e:
        ws_logger.error(f"Error getting approval history for session {session_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error retrieving approval history: {str(e)}"
        })

# Main WebSocket endpoint - simplified
@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """Simplified WebSocket endpoint for real-time analysis workflow."""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"Simplified WebSocket connection established: {session_id}")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to Simplified SOC Analysis",
        "features": ["real_time_streaming", "multi_stage_approval", "simplified_progress"]
    })

    # Create simplified session
    active_sessions[session_id] = SimplifiedSession(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            ws_logger.debug(f"Received message type: {message_type} for session {session_id}")

            try:
                if message_type == "start_analysis":
                    await handle_start_analysis(data, session_id, websocket)

                elif message_type == "TextMessage":
                    await handle_user_input_response(data, session_id)

                elif message_type == "user_approval":
                    # Legacy support for old approval format
                    decision = data.get("decision", "")
                    await handle_user_input_response({"content": decision}, session_id)

                elif message_type == "retrieve_logs":
                    await handle_retrieve_logs(session_id, websocket)

                elif message_type == "ping":
                    await handle_ping(websocket)

                elif message_type == "get_approval_history":
                    await handle_get_approval_history(session_id, websocket)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })

            except WebSocketDisconnect:
                ws_logger.info(f"Client disconnected during message processing for session {session_id}")
                break
            except Exception as e:
                ws_logger.error(f"Error processing message for session {session_id}: {str(e)}")
                error_message = {
                    "type": "error",
                    "content": f"Error: {str(e)}",
                    "source": "system"
                }
                try:
                    await websocket.send_json(error_message)
                except WebSocketDisconnect:
                    ws_logger.info(f"Client disconnected while sending error for session {session_id}")
                    break

    except WebSocketDisconnect:
        ws_logger.info(f"Simplified WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"Unexpected WebSocket error for session {session_id}: {str(e)}")
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]
            ws_logger.info(f"Cleaned up simplified session {session_id}")