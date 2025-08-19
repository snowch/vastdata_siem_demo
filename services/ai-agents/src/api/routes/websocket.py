import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.models.websocket import AnalysisProgress
from core.services.agent_service import run_analysis_workflow
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
    """Enhanced user approval function that handles multi-stage approvals."""
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

def get_stage_progress(stage: str) -> int:
    """Get the appropriate progress percentage for each stage."""
    stage_progress = {
        "triage": 35,
        "context": 65, 
        "analyst": 85
    }
    return stage_progress.get(stage, 50)

async def real_time_message_callback(message_data: dict):
    """
    Enhanced callback function to handle real-time agent messages with better function call detection.
    """
    session_id = message_data.get('session_id')
    if not session_id or session_id not in active_sessions:
        ws_logger.error(f"Invalid session ID in real-time callback: {session_id}")
        return
    
    session = active_sessions[session_id]
    message_type = message_data.get('type')
    
    try:
        ws_logger.debug(f"Real-time message callback: {message_type} for session {session_id}")
        
        if message_type == 'agent_message':
            # Enhanced function call detection and handling
            agent_source = message_data.get('source', '').lower()
            content = message_data.get('content', '')
            
            # DEBUG: Log all agent messages for troubleshooting
            ws_logger.info(f"🔍 Agent message from {agent_source}: {content[:200]}...")
            
            # Enhanced function call detection
            if ('FunctionCall(' in content or 
                'report_priority_findings' in content or 
                'report_detailed_analysis' in content or
                'status' in content and ('priority_identified' in content or 'analysis_complete' in content)):
                
                ws_logger.info(f"🔧 FUNCTION CALL DETECTED from {agent_source}")
                print(f"🔧 FUNCTION CALL CONTENT: {content}")
                
                # Determine which function was called
                if 'report_priority_findings' in content or 'priority_identified' in content:
                    await handle_priority_function_call(session, content, agent_source)
                elif 'report_detailed_analysis' in content or 'analysis_complete' in content:
                    await handle_analysis_function_call(session, content, agent_source)
                
                # Send function call detection to frontend
                await session.websocket.send_json({
                    "type": "function_call_detected",
                    "agent": determine_agent_type(agent_source),
                    "function": "priority_findings" if 'priority' in content else "detailed_analysis",
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id
                })
            
            # Filter out initial task messages and system messages
            if (agent_source in ['user', 'system'] or 
                'ENHANCED SECURITY LOG ANALYSIS' in content or 
                'MULTI-STAGE WORKFLOW' in content or
                len(content) > 2000):  # Skip very long initial messages
                ws_logger.debug(f"Skipping initial/system message from {agent_source}")
                return
            
            # Determine which agent this is from with enhanced mapping
            agent_type = determine_agent_type(agent_source)
            
            if not agent_type:
                ws_logger.debug(f"Unknown agent source: {agent_source}, skipping")
                return
            
            # Send immediate update to frontend
            await session.websocket.send_json({
                "type": "real_time_agent_output",
                "agent": agent_type,
                "content": content,
                "source": message_data.get('source'),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            # Update progress if we have it
            if session.progress and agent_type not in ['approval', 'unknown']:
                # Add to agent outputs for progress tracking
                session.progress.agent_outputs[agent_type].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': content
                })
                
                # Send progress update
                await session.progress.send_update(
                    f"processing_{agent_type}",
                    agent_type,
                    f"🔄 {agent_type.title()} is processing...",
                    get_stage_progress(agent_type)
                )
        
        elif message_type == 'UserInputRequestedEvent':
            # This is handled by the approval system, just log it
            ws_logger.info(f"Approval request relayed for session {session_id}")
        
        elif message_type == 'priority_findings':
            # Send priority findings update immediately
            await session.websocket.send_json({
                "type": "priority_findings_update",
                "data": message_data.get('data'),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            if session.progress:
                await session.progress.send_update(
                    "triage_complete",
                    "triage",
                    "✅ Priority threat identified - findings available",
                    40
                )
        
        elif message_type == 'context_results':
            # Send context results update immediately
            await session.websocket.send_json({
                "type": "context_results_update",
                "data": sanitize_chroma_results(message_data.get('data', {})),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            if session.progress:
                await session.progress.send_update(
                    "context_complete",
                    "context",
                    "🔎 Historical context research completed",
                    70
                )
        
        elif message_type == 'analysis_complete':
            # Send detailed analysis update immediately
            await session.websocket.send_json({
                "type": "detailed_analysis_update",
                "data": message_data.get('data'),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            if session.progress:
                await session.progress.send_update(
                    "analysis_complete",
                    "analyst",
                    "👨‍💼 Deep analysis completed with recommendations",
                    95
                )
        
        elif message_type == 'workflow_rejected':
            # Handle workflow rejection
            await session.websocket.send_json({
                "type": "workflow_rejected",
                "content": message_data.get('content'),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            if session.progress:
                await session.progress.send_update(
                    "rejected",
                    "workflow",
                    "❌ Analysis workflow rejected by user",
                    100
                )
        
        elif message_type == 'analysis_complete_final':
            # Final completion notification
            await session.websocket.send_json({
                "type": "analysis_workflow_complete",
                "was_rejected": message_data.get('was_rejected', False),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
            
            if session.progress and not message_data.get('was_rejected', False):
                await session.progress.send_update(
                    "completed",
                    "workflow",
                    "🎉 Multi-agent analysis completed successfully",
                    100
                )
        
        elif message_type == 'error':
            # Handle errors in real-time
            await session.websocket.send_json({
                "type": "real_time_error",
                "content": message_data.get('content'),
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            })
    
    except Exception as e:
        ws_logger.error(f"Error in real-time message callback for session {session_id}: {e}")

def determine_agent_type(agent_source: str) -> str:
    """Enhanced agent type determination"""
    agent_source_lower = agent_source.lower()
    
    # Enhanced mapping with more variations
    agent_mappings = {
        'triagespecialist': 'triage',
        'triage': 'triage',
        'contextAgent': 'context',
        'context': 'context', 
        'senioranalystspecialist': 'analyst',
        'senioranalyst': 'analyst',
        'analyst': 'analyst',
        'multistageapprovalagent': 'approval',
        'approval': 'approval'
    }
    
    for source_key, agent_type in agent_mappings.items():
        if source_key in agent_source_lower:
            return agent_type
    
    return None

async def handle_priority_function_call(session, content: str, agent_source: str):
    """Handle priority findings function call results"""
    try:
        ws_logger.info("🎯 Processing priority findings function call")
        
        # Try to extract JSON result from the content
        json_patterns = [
            r'\{[^}]*"status"[^}]*"priority_identified"[^}]*\}',
            r'\{.*?"status".*?"priority_identified".*?\}',
            r'"status":\s*"priority_identified"[^}]*\}'
        ]
        
        result_data = None
        for pattern in json_patterns:
            json_match = re.search(pattern, content, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group())
                    break
                except json.JSONDecodeError:
                    continue
        
        if result_data and result_data.get('status') == 'priority_identified':
            findings = result_data.get('data', {})
            ws_logger.info(f"✅ Priority findings extracted: {findings.get('threat_type')} from {findings.get('source_ip')}")
            
            # Send priority findings update
            await session.websocket.send_json({
                "type": "priority_findings_update",
                "data": findings,
                "timestamp": datetime.now().isoformat(),
                "session_id": session.session_id
            })
            
            # Update progress
            if session.progress:
                await session.progress.send_update(
                    "triage_complete",
                    "triage",
                    "✅ Priority threat identified - findings available",
                    40
                )
        else:
            ws_logger.warning("Could not extract priority findings from function call result")
            
    except Exception as e:
        ws_logger.error(f"Error handling priority function call: {e}")

async def handle_analysis_function_call(session, content: str, agent_source: str):
    """Handle detailed analysis function call results"""
    try:
        ws_logger.info("🎯 Processing detailed analysis function call")
        
        # Try to extract JSON result
        json_match = re.search(r'\{.*?"status".*?"analysis_complete".*?\}', content, re.DOTALL)
        if json_match:
            result_data = json.loads(json_match.group())
            
            if result_data.get('status') == 'analysis_complete':
                analysis = result_data.get('data', {})
                ws_logger.info(f"✅ Detailed analysis extracted: {len(analysis.get('recommended_actions', []))} recommendations")
                
                # Send analysis update
                await session.websocket.send_json({
                    "type": "detailed_analysis_update",
                    "data": analysis,
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session.session_id
                })
                
                # Update progress
                if session.progress:
                    await session.progress.send_update(
                        "analysis_complete",
                        "analyst",
                        "👨‍💼 Deep analysis completed with recommendations",
                        95
                    )
    except Exception as e:
        ws_logger.error(f"Error handling analysis function call: {e}")

async def run_analysis_with_realtime_websocket(log_batch: str, progress: AnalysisProgress, session_id: str):
    """
    Enhanced analysis workflow with real-time streaming of agent outputs via WebSocket.
    """
    try:
        await progress.send_update("starting", progress=10)
        ws_logger.info(f"Starting real-time analysis for session {session_id}")

        await progress.send_update("running_triage", "triage", "🔍 Starting triage analysis...", 20)

        # Run analysis with real-time streaming using the new function
        success = await run_analysis_workflow(
            log_batch=log_batch,
            session_id=session_id,
            progress=progress,
            user_input_callback=request_user_approval,
            message_callback=real_time_message_callback
        )

        ws_logger.info(f"Real-time analysis completed for session {session_id} - Success: {success}")

        # Check if analysis was rejected
        if progress.final_results.get('was_rejected', False):
            rejection_stage = progress.final_results.get('rejection_stage', 'unknown')
            await progress.send_update("rejected", rejection_stage, 
                f"❌ Analysis rejected at {rejection_stage} stage", 100)
            return

        # Process successful completion
        session = active_sessions.get(session_id)
        approval_history = session.approval_history if session else []
        
        # Enhance final results with session data
        progress.final_results.update({
            'approval_history': approval_history,
            'stages_completed': len(approval_history),
            'success': success
        })

        if not success:
            await progress.send_update("error", progress=100)
        else:
            await progress.send_update("completed", progress=100)

        ws_logger.info(f"Real-time analysis workflow completed for session {session_id} - Success: {success}")

    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected during analysis for session {session_id}")
        raise
    except Exception as e:
        ws_logger.error(f"Real-time analysis failed for session {session_id}: {str(e)}")
        ws_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)

async def handle_user_input_response(data: dict, session_id: str):
    """Enhanced user input response handler for multi-stage approval."""
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
    """Enhanced start analysis handler with real-time streaming"""
    log_batch = data.get("logs")
    if not log_batch:
        await websocket.send_json({
            "type": "error",
            "message": "No logs provided for analysis"
        })
        return

    ws_logger.info(f"Starting enhanced real-time analysis workflow for session {session_id}")

    # Create session and progress
    progress = AnalysisProgress(session_id, websocket)
    session = WebSocketSession(session_id, websocket)
    session.progress = progress
    active_sessions[session_id] = session

    # Start analysis task with real-time streaming
    asyncio.create_task(run_analysis_with_realtime_websocket(log_batch, progress, session_id))

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

# Main WebSocket endpoint
@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """Enhanced WebSocket endpoint for real-time analysis workflow."""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"Real-time WebSocket connection established: {session_id}")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to Enhanced SOC Analysis with Real-time Streaming",
        "features": ["real_time_streaming", "multi_stage_approval", "custom_instructions", "approval_history"]
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
        ws_logger.info(f"Real-time WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"Unexpected WebSocket error for session {session_id}: {str(e)}")
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]
            ws_logger.info(f"Cleaned up real-time session {session_id}")