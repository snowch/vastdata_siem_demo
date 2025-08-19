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
import re

router = APIRouter()

ws_logger = logging.getLogger("websocket_server")

# Store active WebSocket sessions with enhanced state tracking
active_sessions = {}

class WebSocketSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.user_input_future = None
        self.progress = None
        self.current_approval_stage = None
        self.approval_history = []

async def request_user_approval(prompt: str, session_id: str) -> str:
    """
    Enhanced user approval function that handles multi-stage approvals.
    Determines the approval stage based on the prompt content.
    """
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
        
        # Send enhanced UserInputRequestedEvent with stage information
        user_input_event = {
            "type": "UserInputRequestedEvent",
            "content": prompt,
            "source": f"{approval_stage.title()}Agent" if approval_stage != "unknown" else "ApprovalAgent",
            "approval_stage": approval_stage,
            "timestamp": datetime.now().isoformat()
        }
        
        ws_logger.info(f"Sending multi-stage approval request: {user_input_event}")
        await session.websocket.send_json(user_input_event)
        
        # Update progress to show waiting for approval
        if session.progress:
            stage_messages = {
                "triage": "⏸️ Awaiting approval to investigate this priority threat...",
                "context": "⏸️ Awaiting validation of historical context relevance...", 
                "analyst": "⏸️ Awaiting authorization for recommended actions..."
            }
            await session.progress.send_update(
                "awaiting_approval", 
                approval_stage, 
                stage_messages.get(approval_stage, "⏸️ Awaiting user approval..."), 
                get_stage_progress(approval_stage)
            )
        
        # Wait for user response with timeout
        try:
            user_response = await asyncio.wait_for(
                session.user_input_future, 
                timeout=300.0  # 5 minute timeout for multi-stage
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
    """
    Determine which approval stage based on the prompt content.
    """
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

def get_stage_progress(stage: str) -> int:
    """Get the appropriate progress percentage for each stage."""
    stage_progress = {
        "triage": 35,
        "context": 65, 
        "analyst": 85
    }
    return stage_progress.get(stage, 50)

async def send_agent_outputs(progress: AnalysisProgress, agent_outputs: dict, findings_summary: dict):
    """Enhanced agent output handling for multi-stage approval"""
    current_progress = 40

    # Triage outputs 
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

    # Context outputs
    if agent_outputs['context'] or findings_summary['context_searched']:
        await progress.send_update("completed_context", "context",
            "🔎 Historical context research completed and validated", current_progress + 20)
        for output in agent_outputs['context']:
            progress.agent_outputs['context'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress += 20

    # Analyst outputs
    if agent_outputs['analyst'] or findings_summary['analysis_completed']:
        await progress.send_update("completed_analyst", "analyst",
            "👨‍💼 Deep analysis and recommendations authorized", current_progress + 20)
        for output in agent_outputs['analyst']:
            progress.agent_outputs['analyst'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress += 20

    # Ensure all agents have outputs
    for agent_type in ['triage', 'context', 'analyst']:
        if not progress.agent_outputs[agent_type]:
            progress.agent_outputs[agent_type].append({
                'timestamp': datetime.now().isoformat(),
                'message': f"{agent_type.title()} stage completed successfully with user approval."
            })

    return current_progress

async def run_analysis_with_websocket(log_batch: str, progress: AnalysisProgress, session_id: str):
    """Enhanced analysis workflow with multi-stage approval support"""
    try:
        await progress.send_update("starting", progress=10)
        ws_logger.info(f"Starting multi-stage analysis for session {session_id}")

        await progress.send_update("running_triage", "triage", "🔍 Starting triage analysis...", 20)

        # Run analysis with multi-stage approval workflow
        full_conversation, structured_findings, chroma_context = await get_prioritized_task_with_approval(
            log_batch=log_batch,
            session_id=session_id,
            user_input_callback=request_user_approval
        )

        ws_logger.info(f"Multi-stage analysis completed for session {session_id}")
        ws_logger.debug(f"Structured findings: {structured_findings}")

        # Check if analysis was rejected at any stage
        if structured_findings.get('was_rejected', False):
            rejection_stage = structured_findings.get('rejection_stage', 'unknown')
            await progress.send_update("rejected", rejection_stage, 
                f"❌ Analysis rejected at {rejection_stage} stage", 100)
            progress.completed = True
            progress.final_results = {
                'conversation': full_conversation,
                'structured_findings': structured_findings,
                'chroma_context': sanitize_chroma_results(chroma_context),
                'was_rejected': True,
                'rejection_stage': rejection_stage
            }
            await progress.send_update()
            return

        # Process successful completion with approval history
        session = active_sessions.get(session_id)
        approval_history = session.approval_history if session else []
        
        if 'detailed_analysis' in structured_findings:
            detailed = structured_findings['detailed_analysis']
            if 'threat_assessment' not in detailed or not detailed['threat_assessment']:
                detailed['threat_assessment'] = {
                    "severity": "unknown",
                    "confidence": 0.0
                }

        # Parse agent outputs and update progress
        agent_outputs = parse_agent_conversation(full_conversation)
        findings_summary = extract_structured_findings(full_conversation, structured_findings)
        current_progress = await send_agent_outputs(progress, agent_outputs, findings_summary)

        # Set enhanced final results
        progress.final_results = {
            'conversation': full_conversation,
            'structured_findings': structured_findings,
            'chroma_context': sanitize_chroma_results(chroma_context),
            'findings_summary': findings_summary,
            'approval_history': approval_history,
            'stages_completed': len(approval_history)
        }

        progress.completed = True
        await progress.send_update("completed", progress=100)

        ws_logger.info(f"Multi-stage analysis workflow completed successfully for session {session_id}")

    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected during analysis for session {session_id}")
        raise
    except Exception as e:
        ws_logger.error(f"Multi-stage analysis failed for session {session_id}: {str(e)}")
        ws_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)

async def handle_user_input_response(data: dict, session_id: str):
    """
    Enhanced user input response handler for multi-stage approval.
    """
    content = data.get("content", "")
    target_agent = data.get("target_agent", "")
    
    ws_logger.info(f"Multi-stage user input response for session {session_id}, target: {target_agent}, content: {content}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found for user input")
        return
    
    session = active_sessions[session_id]
    
    if session.user_input_future and not session.user_input_future.done():
        # Process the response based on target agent
        processed_response = process_approval_response(content, target_agent, session.current_approval_stage)
        session.user_input_future.set_result(processed_response)
        ws_logger.info(f"Multi-stage user input processed for session {session_id}")
    else:
        ws_logger.warning(f"No pending user input request for session {session_id}")

def process_approval_response(content: str, target_agent: str, approval_stage: str) -> str:
    """
    Process approval response based on the stage and content.
    """
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

# Rest of the WebSocket handling remains similar but with enhanced logging and stage tracking
@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """
    Enhanced WebSocket endpoint for multi-stage analysis workflow.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"Multi-stage WebSocket connection established: {session_id}")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to Enhanced SOC Analysis with Multi-Stage Approval",
        "features": ["multi_stage_approval", "custom_instructions", "approval_history"]
    })

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
        ws_logger.info(f"Multi-stage WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"Unexpected WebSocket error for session {session_id}: {str(e)}")
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]
            ws_logger.info(f"Cleaned up multi-stage session {session_id}")

# Additional helper functions for the enhanced workflow
async def handle_start_analysis(data: dict, session_id: str, websocket: WebSocket):
    """Enhanced start analysis handler"""
    log_batch = data.get("logs")
    if not log_batch:
        await websocket.send_json({
            "type": "error",
            "message": "No logs provided for analysis"
        })
        return

    ws_logger.info(f"Starting enhanced multi-stage analysis workflow for session {session_id}")

    # Create session and progress
    progress = AnalysisProgress(session_id, websocket)
    session = WebSocketSession(session_id, websocket)
    session.progress = progress
    active_sessions[session_id] = session

    # Start analysis task
    asyncio.create_task(run_analysis_with_websocket(log_batch, progress, session_id))

async def handle_get_approval_history(session_id: str, websocket: WebSocket):
    """Get approval history for the session"""
    session = active_sessions.get(session_id)
    if session:
        await websocket.send_json({
            "type": "approval_history",
            "history": session.approval_history,
            "current_stage": session.current_approval_stage
        })
    else:
        await websocket.send_json({
            "type": "approval_history",
            "history": [],
            "current_stage": None
        })

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