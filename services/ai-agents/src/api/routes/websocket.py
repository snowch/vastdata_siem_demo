# services/ai-agents/src/api/routes/websocket.py - REFACTORED VERSION
"""
Simplified WebSocket routes - core coordination only
Complex logic moved to dedicated modules
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.services.agent_service import run_analysis_workflow
from infrastructure.trino_db_reader import get_logs
from .websocket_handlers import MessageHandlers
from .websocket_session import SessionManager
from .websocket_messages import MessageFactory
import logging

router = APIRouter()
ws_logger = logging.getLogger("websocket_server")

# Initialize components
session_manager = SessionManager()
message_handlers = MessageHandlers(session_manager)
message_factory = MessageFactory()

@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """Main WebSocket endpoint - simplified coordinator"""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    
    ws_logger.info(f"🔌 WebSocket connection: {session_id}")
    
    # Create session
    session = await session_manager.create_session(session_id, websocket)
    
    # Send connection established
    await session.send_message(
        message_factory.connection_established(session_id)
    )
    
    try:
        while True:
            data = await websocket.receive_json()
            await message_handlers.handle_message(data, session_id)
            
    except WebSocketDisconnect:
        ws_logger.info(f"🔌 Client disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"❌ WebSocket error for {session_id}: {e}")
        await session.send_error(f"Unexpected error: {str(e)}")
    finally:
        await session_manager.cleanup_session(session_id)

@router.get("/ws/health")
async def websocket_health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_sessions": session_manager.get_session_count(),
        "features": ["clean_architecture", "modular_design"],
        "timestamp": datetime.now().isoformat()
    }