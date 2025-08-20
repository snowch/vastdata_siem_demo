# services/ai-agents/src/api/routes/websocket.py - CLEAN ARCHITECTURE VERSION
"""
WebSocket routes with clean message architecture and type advertisement
"""

import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.services.agent_service import run_analysis_workflow
from infrastructure.trino_db_reader import get_logs
import logging

# Import clean message architecture
from core.messaging.registry import (
    MessageRegistry,
    ResultMessageType,
    StatusMessageType,
    InteractionMessageType,
    ControlMessageType,
    validate_message_type,
    get_message_category,
    MessageTypesAdvertisementMessage,
    ConnectionEstablishedMessage,
    LogsRetrievedMessage,
    ErrorMessage,
    PongMessage
)

router = APIRouter()
ws_logger = logging.getLogger("websocket_server")

# Store active WebSocket sessions with clean architecture
active_sessions = {}

class CleanSession:
    """Clean session management with type-safe messaging"""
    
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.user_input_future = None
        self.current_approval_stage = None
        self.approval_history = []
        self.message_count = 0
        self.supported_types = MessageRegistry.get_supported_types()
        
    async def send_typed_message(self, message) -> bool:
        """Send a typed message with validation"""
        try:
            # Convert Pydantic model to dict if needed
            if hasattr(message, 'model_dump'):
                message_data = message.model_dump()
            else:
                message_data = message
            
            # Validate message type
            message_type = message_data.get('type')
            if not validate_message_type(message_type):
                ws_logger.error(f"❌ Invalid message type: {message_type} for session {self.session_id}")
                return False
            
            # Send message
            await self.websocket.send_json(message_data)
            self.message_count += 1
            
            category = get_message_category(message_type)
            ws_logger.debug(f"✅ CLEAN ARCH: Sent {category}/{message_type} to session {self.session_id}")
            
            return True
            
        except WebSocketDisconnect:
            ws_logger.info(f"Client disconnected while sending message to session {self.session_id}")
            return False
        except Exception as e:
            ws_logger.error(f"❌ Error sending typed message to session {self.session_id}: {e}")
            return False

# ============================================================================
# MESSAGE TYPE ADVERTISEMENT
# ============================================================================

async def send_connection_established(session: CleanSession):
    """Send connection established message with features and type advertisement"""
    try:
        # Create connection established message
        connection_msg = MessageRegistry.create_message(
            ControlMessageType.CONNECTION_ESTABLISHED,
            session_id=session.session_id,
            features=["clean_message_architecture", "type_validation", "multi_stage_approval", "real_time_streaming"],
            server_info={
                "version": "2.0.0-clean",
                "architecture": "clean_messaging",
                "supported_agents": ["triage", "context", "analyst"]
            }
        )
        
        await session.send_typed_message(connection_msg)
        
        # Send message types advertisement
        advertisement_msg = MessageRegistry.create_message(
            ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT,
            session_id=session.session_id
        )
        
        await session.send_typed_message(advertisement_msg)
        
        ws_logger.info(f"📢 CLEAN ARCH: Advertised {len(session.supported_types['all_types'])} message types to session {session.session_id}")
        
    except Exception as e:
        ws_logger.error(f"❌ Error sending connection established to session {session.session_id}: {e}")

# ============================================================================
# USER APPROVAL WORKFLOW
# ============================================================================

async def request_user_approval(prompt: str, session_id: str) -> str:
    """Clean user approval function with typed messaging"""
    ws_logger.info(f"👤 CLEAN ARCH: Requesting user approval for session {session_id}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found in active sessions")
        return "approve"
    
    session = active_sessions[session_id]
    
    try:
        # Determine approval stage based on prompt content
        approval_stage = determine_approval_stage(prompt)
        session.current_approval_stage = approval_stage
        
        ws_logger.info(f"📋 CLEAN ARCH: Approval stage determined as: {approval_stage} for session {session_id}")
        
        # Create a future to wait for user input
        session.user_input_future = asyncio.Future()
        
        # Send clean approval request message
        approval_msg = MessageRegistry.create_message(
            InteractionMessageType.APPROVAL_REQUEST,
            session_id=session_id,
            stage=approval_stage,
            prompt=prompt,
            context={
                "timestamp": datetime.now().isoformat(),
                "stage_description": get_stage_description(approval_stage)
            },
            timeout_seconds=300
        )
        
        await session.send_typed_message(approval_msg)
        
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
            
            ws_logger.info(f"✅ CLEAN ARCH: User response received for {approval_stage} stage in session {session_id}: {user_response}")
            return user_response
            
        except asyncio.TimeoutError:
            ws_logger.warning(f"⏰ User approval timeout for {approval_stage} stage in session {session_id}")
            
            # Send timeout message
            timeout_msg = MessageRegistry.create_message(
                InteractionMessageType.APPROVAL_TIMEOUT,
                session_id=session_id,
                stage=approval_stage,
                default_action="auto_approve"
            )
            await session.send_typed_message(timeout_msg)
            
            return "approve"  # Auto-approve on timeout
            
    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected while waiting for user input")
        raise
    except Exception as e:
        ws_logger.error(f"❌ Error requesting user approval: {e}")
        
        # Send error message
        error_msg = MessageRegistry.create_message(
            ControlMessageType.ERROR,
            session_id=session_id,
            message=f"Approval request error: {str(e)}",
            error_code="APPROVAL_ERROR"
        )
        await session.send_typed_message(error_msg)
        
        return "approve"

def determine_approval_stage(prompt: str) -> str:
    """Determine which approval stage based on the prompt content"""
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

def get_stage_description(stage: str) -> str:
    """Get a human-readable description for an approval stage"""
    descriptions = {
        "triage": "Initial threat assessment and prioritization",
        "context": "Historical incident correlation and pattern analysis",
        "analyst": "Deep analysis and actionable recommendations",
        "unknown": "General approval required"
    }
    return descriptions.get(stage, "Unknown stage")

# ============================================================================
# REAL-TIME MESSAGE CALLBACK
# ============================================================================

async def real_time_message_callback(message_data: dict):
    """
    Clean callback function to handle real-time agent messages with type validation
    """
    session_id = message_data.get('session_id')
    if not session_id or session_id not in active_sessions:
        ws_logger.error(f"❌ CLEAN ARCH: Invalid session ID in callback: {session_id}")
        return
    
    session = active_sessions[session_id]
    message_type = message_data.get('type')
    
    try:
        ws_logger.debug(f"📨 CLEAN ARCH: Real-time callback - {message_type} for session {session_id}")
        
        # Validate message type
        if not validate_message_type(message_type):
            ws_logger.error(f"❌ CLEAN ARCH: Invalid message type in callback: {message_type}")
            return
        
        # Send all clean architecture messages directly to frontend
        await session.send_typed_message(message_data)
        ws_logger.debug(f"✅ CLEAN ARCH: Sent {message_type} to session {session_id}")
        
    except Exception as e:
        ws_logger.error(f"❌ CLEAN ARCH: Error in real-time callback for session {session_id}: {e}")

# ============================================================================
# ANALYSIS WORKFLOW RUNNER
# ============================================================================

async def run_clean_analysis(log_batch: str, session_id: str):
    """
    Clean analysis runner using the new message architecture
    """
    try:
        ws_logger.info(f"🚀 CLEAN ARCH: Starting analysis for session {session_id}")
        
        # Run analysis workflow with clean messaging
        success = await run_analysis_workflow(
            log_batch=log_batch,
            session_id=session_id,
            user_input_callback=request_user_approval,
            message_callback=real_time_message_callback
        )
        
        ws_logger.info(f"✅ CLEAN ARCH: Analysis completed for session {session_id} - Success: {success}")
        
    except Exception as e:
        ws_logger.error(f"❌ CLEAN ARCH: Analysis failed for session {session_id}: {str(e)}")
        
        if session_id in active_sessions:
            error_msg = MessageRegistry.create_message(
                ControlMessageType.ERROR,
                session_id=session_id,
                message=f"Analysis error: {str(e)}",
                error_code="ANALYSIS_ERROR",
                details={"session_id": session_id}
            )
            
            try:
                await active_sessions[session_id].send_typed_message(error_msg)
            except Exception as send_error:
                ws_logger.error(f"❌ Failed to send error message: {send_error}")

# ============================================================================
# MESSAGE HANDLERS
# ============================================================================

async def handle_user_input_response(data: dict, session_id: str):
    """Clean user input response handler"""
    content = data.get("content", "")
    target_agent = data.get("target_agent", "")
    
    ws_logger.info(f"👤 CLEAN ARCH: User input response for session {session_id}, target: {target_agent}, content: {content}")
    
    if session_id not in active_sessions:
        ws_logger.error(f"Session {session_id} not found for user input")
        return
    
    session = active_sessions[session_id]
    
    if session.user_input_future and not session.user_input_future.done():
        # Process the response based on current approval stage
        processed_response = process_approval_response(content, target_agent, session.current_approval_stage)
        session.user_input_future.set_result(processed_response)
        ws_logger.info(f"✅ CLEAN ARCH: User input processed for session {session_id}")
    else:
        ws_logger.warning(f"⚠️ No pending user input request for session {session_id}")

def process_approval_response(content: str, target_agent: str, approval_stage: str) -> str:
    """Process approval response based on the stage and content"""
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
    """Clean start analysis handler"""
    log_batch = data.get("logs")
    if not log_batch:
        error_msg = MessageRegistry.create_message(
            ControlMessageType.ERROR,
            session_id=session_id,
            message="No logs provided for analysis",
            error_code="MISSING_LOGS"
        )
        await active_sessions[session_id].send_typed_message(error_msg)
        return

    ws_logger.info(f"🚀 CLEAN ARCH: Starting analysis workflow for session {session_id}")

    # Start analysis task with clean architecture
    asyncio.create_task(run_clean_analysis(log_batch, session_id))

async def handle_retrieve_logs(session_id: str, websocket: WebSocket):
    """Handle log retrieval request with clean messaging"""
    ws_logger.info(f"📥 CLEAN ARCH: Log retrieval requested via WebSocket: {session_id}")
    
    try:
        logs = get_logs()
        
        logs_msg = MessageRegistry.create_message(
            ControlMessageType.LOGS_RETRIEVED,
            session_id=session_id,
            logs=logs,
            count=len(logs),
            message=f"Retrieved {len(logs)} log entries successfully"
        )
        
        await active_sessions[session_id].send_typed_message(logs_msg)
        ws_logger.info(f"✅ CLEAN ARCH: Successfully sent {len(logs)} logs to session {session_id}")
        
    except Exception as e:
        ws_logger.error(f"❌ Error retrieving logs for session {session_id}: {e}")
        
        error_msg = MessageRegistry.create_message(
            ControlMessageType.ERROR,
            session_id=session_id,
            message=f"Log retrieval error: {str(e)}",
            error_code="LOG_RETRIEVAL_ERROR"
        )
        await active_sessions[session_id].send_typed_message(error_msg)

async def handle_ping(session_id: str, websocket: WebSocket):
    """Handle ping request with clean messaging"""
    try:
        pong_msg = MessageRegistry.create_message(
            ControlMessageType.PONG,
            session_id=session_id
        )
        await active_sessions[session_id].send_typed_message(pong_msg)
        ws_logger.debug(f"🏓 CLEAN ARCH: Sent pong response to session {session_id}")
    except Exception as e:
        ws_logger.error(f"❌ Error sending pong response to session {session_id}: {e}")

async def handle_get_approval_history(session_id: str, websocket: WebSocket):
    """Get approval history for the session with clean messaging"""
    try:
        session = active_sessions.get(session_id)
        if session:
            # Send as a custom message (could be added to registry if needed frequently)
            history_data = {
                "type": "approval_history_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "history": session.approval_history,
                "current_stage": session.current_approval_stage,
                "total_approvals": len(session.approval_history)
            }
            
            await websocket.send_json(history_data)
            ws_logger.info(f"📋 CLEAN ARCH: Sent approval history for session {session_id}: {len(session.approval_history)} entries")
        else:
            # Send empty response
            empty_response = {
                "type": "approval_history_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "history": [],
                "current_stage": None,
                "total_approvals": 0
            }
            await websocket.send_json(empty_response)
            ws_logger.warning(f"⚠️ No session found for approval history request: {session_id}")
            
    except Exception as e:
        ws_logger.error(f"❌ Error getting approval history for session {session_id}: {e}")
        
        error_msg = MessageRegistry.create_message(
            ControlMessageType.ERROR,
            session_id=session_id,
            message=f"Error retrieving approval history: {str(e)}",
            error_code="APPROVAL_HISTORY_ERROR"
        )
        await active_sessions[session_id].send_typed_message(error_msg)

async def handle_get_supported_types(session_id: str, websocket: WebSocket):
    """Handle request for supported message types"""
    try:
        session = active_sessions.get(session_id)
        if session:
            # Send message types advertisement
            advertisement_msg = MessageRegistry.create_message(
                ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT,
                session_id=session_id
            )
            await session.send_typed_message(advertisement_msg)
            ws_logger.info(f"📢 CLEAN ARCH: Re-sent message types to session {session_id}")
        else:
            ws_logger.warning(f"⚠️ Session not found for types request: {session_id}")
            
    except Exception as e:
        ws_logger.error(f"❌ Error sending supported types to session {session_id}: {e}")

# ============================================================================
# MAIN WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """Clean WebSocket endpoint with message type advertisement and validation"""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"🔌 CLEAN ARCH: WebSocket connection established: {session_id}")

    # Create clean session
    session = CleanSession(session_id, websocket)
    active_sessions[session_id] = session

    # Send connection established and advertise message types
    await send_connection_established(session)

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            ws_logger.debug(f"📨 CLEAN ARCH: Received message type: {message_type} for session {session_id}")

            try:
                # Route to appropriate handler
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
                    await handle_ping(session_id, websocket)

                elif message_type == "get_approval_history":
                    await handle_get_approval_history(session_id, websocket)

                elif message_type == "get_supported_types":
                    await handle_get_supported_types(session_id, websocket)

                else:
                    # Send error for unknown message type
                    error_msg = MessageRegistry.create_message(
                        ControlMessageType.ERROR,
                        session_id=session_id,
                        message=f"Unknown message type: {message_type}",
                        error_code="UNKNOWN_MESSAGE_TYPE",
                        details={"received_type": message_type, "supported_types": session.supported_types['all_types']}
                    )
                    await session.send_typed_message(error_msg)

            except WebSocketDisconnect:
                ws_logger.info(f"🔌 Client disconnected during message processing for session {session_id}")
                break
            except Exception as e:
                ws_logger.error(f"❌ Error processing message for session {session_id}: {str(e)}")
                
                error_msg = MessageRegistry.create_message(
                    ControlMessageType.ERROR,
                    session_id=session_id,
                    message=f"Message processing error: {str(e)}",
                    error_code="MESSAGE_PROCESSING_ERROR"
                )
                
                try:
                    await session.send_typed_message(error_msg)
                except WebSocketDisconnect:
                    ws_logger.info(f"🔌 Client disconnected while sending error for session {session_id}")
                    break

    except WebSocketDisconnect:
        ws_logger.info(f"🔌 CLEAN ARCH: WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"❌ Unexpected WebSocket error for session {session_id}: {str(e)}")
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]
            ws_logger.info(f"🧹 CLEAN ARCH: Cleaned up session {session_id}")

# ============================================================================
# HEALTH CHECK WITH CLEAN ARCHITECTURE INFO
# ============================================================================

@router.get("/ws/health")
async def websocket_health():
    """Health check endpoint with clean architecture information"""
    return {
        "status": "healthy",
        "architecture": "clean_messaging",
        "active_sessions": len(active_sessions),
        "supported_message_types": MessageRegistry.get_supported_types(),
        "message_categories": {
            "results": len([e.value for e in ResultMessageType]),
            "status": len([e.value for e in StatusMessageType]),
            "interaction": len([e.value for e in InteractionMessageType]),
            "control": len([e.value for e in ControlMessageType])
        },
        "features": [
            "type_validation",
            "message_advertisement", 
            "clean_architecture",
            "structured_messaging",
            "real_time_streaming"
        ],
        "timestamp": datetime.now().isoformat()
    }