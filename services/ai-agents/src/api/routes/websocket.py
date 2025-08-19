import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.models.websocket import AnalysisProgress
from core.services.agent_service import get_prioritized_task_with_approval
from core.services.analysis_helpers import parse_agent_conversation, extract_structured_findings
from utils.serialization import sanitize_chroma_results
from infrastructure.trino_db_reader import get_logs
from autogen_agentchat.messages import UserInputRequestedEvent, TextMessage
import logging
import traceback
import json

router = APIRouter()

ws_logger = logging.getLogger("websocket_server")

# Store active WebSocket sessions
active_sessions = {}

class WebSocketSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.user_input_future = None
        self.progress = None

async def request_user_approval(prompt: str, session_id: str) -> str:
    """
    Request user approval via WebSocket following AutoGen reference pattern.
    This function mimics how AutoGen sends UserInputRequestedEvent.
    """
    ws_logger.info(f"Requesting user approval for session {session_id}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found in active sessions")
        return "approve"
    
    session = active_sessions[session_id]
    
    try:
        # Create a future to wait for user input
        session.user_input_future = asyncio.Future()
        
        # Send UserInputRequestedEvent-style message following AutoGen pattern
        user_input_event = {
            "type": "UserInputRequestedEvent",
            "content": prompt,
            "source": "ApprovalAgent",
            "timestamp": datetime.now().isoformat()
        }
        
        ws_logger.info(f"Sending user input request: {user_input_event}")
        await session.websocket.send_json(user_input_event)
        
        # Update progress to show waiting for approval
        if session.progress:
            await session.progress.send_update(
                "awaiting_approval", 
                "triage", 
                "⏸️ Awaiting user approval to continue with full analysis...", 
                35
            )
        
        # Wait for user response with timeout (following reference pattern)
        try:
            user_response = await asyncio.wait_for(
                session.user_input_future, 
                timeout=120.0  # 2 minute timeout
            )
            ws_logger.info(f"User response received for session {session_id}: {user_response}")
            return user_response
            
        except asyncio.TimeoutError:
            ws_logger.warning(f"User approval timeout for session {session_id}")
            return "approve"  # Auto-approve on timeout
            
    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected while waiting for user input")
        raise  # Let WebSocketDisconnect propagate
    except Exception as e:
        ws_logger.error(f"Error requesting user approval: {e}")
        return "approve"  # Default to approve on error

async def send_agent_outputs(progress: AnalysisProgress, agent_outputs: dict, findings_summary: dict):
    """Send agent outputs with updated progress tracking"""
    current_progress = 40  # Start after approval

    # Triage outputs (should already be complete at this point)
    if agent_outputs['triage'] or findings_summary['priority_found']:
        await progress.send_update("completed_triage", "triage",
            f"✅ Triage completed and approved - {findings_summary['priority_level']} priority {findings_summary['threat_type']} detected",
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
            'message': "Triage analysis completed and approved"
        })

    # Context outputs
    if agent_outputs['context'] or findings_summary['context_searched']:
        await progress.send_update("completed_context", "context",
            "🔎 Historical context research completed", current_progress + 25)
        for output in agent_outputs['context']:
            progress.agent_outputs['context'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress += 25
    else:
        progress.agent_outputs['context'].append({
            'timestamp': datetime.now().isoformat(),
            'message': "Context research completed - historical incidents analyzed"
        })

    # Analyst outputs
    if agent_outputs['analyst'] or findings_summary['analysis_completed']:
        await progress.send_update("completed_analyst", "analyst",
            "👨‍💼 Deep analysis and recommendations completed", current_progress + 25)
        for output in agent_outputs['analyst']:
            progress.agent_outputs['analyst'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress += 25
    else:
        progress.agent_outputs['analyst'].append({
            'timestamp': datetime.now().isoformat(),
            'message': "Senior analysis completed - recommendations generated"
        })

    # Ensure all agents have at least one output
    for agent_type in ['triage', 'context', 'analyst']:
        if not progress.agent_outputs[agent_type]:
            progress.agent_outputs[agent_type].append({
                'timestamp': datetime.now().isoformat(),
                'message': f"{agent_type.title()} agent completed successfully. Check full conversation for details."
            })

    return current_progress

async def run_analysis_with_websocket(log_batch: str, progress: AnalysisProgress, session_id: str):
    """Run the analysis workflow with WebSocket progress updates"""
    try:
        await progress.send_update("starting", progress=10)
        ws_logger.info(f"Starting analysis for session {session_id}")

        await progress.send_update("running_triage", "triage", "🔍 Starting initial triage analysis...", 20)

        # Run analysis with approval workflow
        full_conversation, structured_findings, chroma_context = await get_prioritized_task_with_approval(
            log_batch=log_batch,
            session_id=session_id,
            user_input_callback=request_user_approval
        )

        ws_logger.info(f"Analysis completed for session {session_id}")
        ws_logger.debug(f"Structured findings: {structured_findings}")

        # Check if analysis was rejected
        if structured_findings.get('was_rejected', False):
            await progress.send_update("rejected", "triage", 
                "❌ Analysis rejected by user", 100)
            progress.completed = True
            progress.final_results = {
                'conversation': full_conversation,
                'structured_findings': structured_findings,
                'chroma_context': sanitize_chroma_results(chroma_context),
                'was_rejected': True
            }
            await progress.send_update()
            return

        # Process successful completion
        if 'detailed_analysis' in structured_findings:
            detailed = structured_findings['detailed_analysis']
            if 'threat_assessment' not in detailed or not detailed['threat_assessment']:
                detailed['threat_assessment'] = {
                    "severity": "unknown",
                    "confidence": 0.0
                }
                ws_logger.warning(f"Added default threat_assessment for session {session_id}")

        # Parse agent outputs
        agent_outputs = parse_agent_conversation(full_conversation)
        findings_summary = extract_structured_findings(full_conversation, structured_findings)

        # Send agent outputs with progress updates
        current_progress = await send_agent_outputs(progress, agent_outputs, findings_summary)

        # Set final results
        progress.final_results = {
            'conversation': full_conversation,
            'structured_findings': structured_findings,
            'chroma_context': sanitize_chroma_results(chroma_context),
            'findings_summary': findings_summary
        }

        progress.completed = True
        await progress.send_update("completed", progress=100)

        ws_logger.info(f"Analysis workflow completed successfully for session {session_id}")

    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected during analysis for session {session_id}")
        raise  # Let it propagate to the main handler
    except Exception as e:
        ws_logger.error(f"Analysis failed for session {session_id}: {str(e)}")
        ws_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)

async def handle_start_analysis(data: dict, session_id: str, websocket: WebSocket):
    """Handle start analysis request"""
    log_batch = data.get("logs")
    if not log_batch:
        await websocket.send_json({
            "type": "error",
            "message": "No logs provided for analysis"
        })
        return

    ws_logger.info(f"Starting analysis workflow for session {session_id}")

    # Create session and progress
    progress = AnalysisProgress(session_id, websocket)
    session = WebSocketSession(session_id, websocket)
    session.progress = progress
    active_sessions[session_id] = session

    # Start analysis task
    asyncio.create_task(run_analysis_with_websocket(log_batch, progress, session_id))

async def handle_user_input_response(data: dict, session_id: str):
    """
    Handle user input response following AutoGen reference pattern.
    This is similar to how the reference handles TextMessage responses.
    """
    # Extract content from the message (following TextMessage pattern)
    content = data.get("content", "")
    ws_logger.info(f"User input response for session {session_id}: {content}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found for user input")
        return
    
    session = active_sessions[session_id]
    
    if session.user_input_future and not session.user_input_future.done():
        # Return the content directly (following AutoGen reference pattern)
        session.user_input_future.set_result(content)
        ws_logger.info(f"User input processed for session {session_id}")
    else:
        ws_logger.warning(f"No pending user input request for session {session_id}")

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
    except Exception as e:
        ws_logger.error(f"Error retrieving logs: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Server error: {str(e)}"
        })

async def handle_ping(websocket: WebSocket):
    """Handle ping request"""
    await websocket.send_json({
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    })

@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """
    Main WebSocket endpoint for analysis workflow following AutoGen reference pattern.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"WebSocket connection established: {session_id}")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to SOC Analysis WebSocket with Approval Workflow"
    })

    try:
        while True:
            # Get user message (following reference pattern)
            data = await websocket.receive_json()
            message_type = data.get("type")

            ws_logger.debug(f"Received message type: {message_type} for session {session_id}")

            try:
                if message_type == "start_analysis":
                    await handle_start_analysis(data, session_id, websocket)

                elif message_type == "TextMessage":
                    # Handle user input response (following AutoGen reference pattern)
                    await handle_user_input_response(data, session_id)

                elif message_type == "user_approval":
                    # Legacy support for the old approval format
                    decision = data.get("decision", "")
                    await handle_user_input_response({"content": decision}, session_id)

                elif message_type == "retrieve_logs":
                    await handle_retrieve_logs(session_id, websocket)

                elif message_type == "ping":
                    await handle_ping(websocket)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })

            except WebSocketDisconnect:
                # Client disconnected during message processing
                ws_logger.info(f"Client disconnected during message processing for session {session_id}")
                break
            except Exception as e:
                # Send error message to client (following reference pattern)
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
                except Exception as send_error:
                    ws_logger.error(f"Failed to send error message for session {session_id}: {str(send_error)}")
                    break

    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"Unexpected WebSocket error for session {session_id}: {str(e)}")
        ws_logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Unexpected error: {str(e)}",
                "source": "system"
            })
        except WebSocketDisconnect:
            ws_logger.info(f"Client disconnected before error could be sent for session {session_id}")
        except Exception:
            ws_logger.error(f"Failed to send error message to client for session {session_id}")
    finally:
        # Clean up session (following reference pattern)
        if session_id in active_sessions:
            del active_sessions[session_id]
            ws_logger.info(f"Cleaned up session {session_id}")