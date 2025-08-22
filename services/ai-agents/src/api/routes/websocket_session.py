# services/ai-agents/src/api/routes/websocket_session.py
"""
WebSocket session management - clean separation of concerns
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from core.messaging.registry import MessageRegistry, ControlMessageType
import logging

ws_logger = logging.getLogger("websocket_server")

class Session:
    """Represents a single WebSocket session"""
    
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.user_input_future: Optional[asyncio.Future] = None
        self.current_approval_stage: Optional[str] = None
        self.approval_history: list = []
        self.message_count = 0
        self.created_at = datetime.now()
        
    async def send_message(self, message) -> bool:
        """Send a message to the client"""
        try:
            if hasattr(message, 'model_dump'):
                message_data = message.model_dump(mode='json')
            else:
                message_data = message
            
            await self.websocket.send_json(message_data)
            self.message_count += 1
            
            message_type = message_data.get('type', 'unknown')
            ws_logger.debug(f"✅ Sent {message_type} to {self.session_id}")
            return True
            
        except WebSocketDisconnect:
            ws_logger.info(f"Client disconnected while sending to {self.session_id}")
            return False
        except Exception as e:
            ws_logger.error(f"❌ Error sending message to {self.session_id}: {e}")
            return False
    
    async def send_error(self, error_message: str, error_code: str = "GENERAL_ERROR"):
        """Send an error message"""
        error_msg = MessageRegistry.create_message(
            ControlMessageType.ERROR,
            session_id=self.session_id,
            message=error_message,
            error_code=error_code
        )
        await self.send_message(error_msg)
    
    async def request_user_input(self, prompt: str, stage: str, timeout: int = 300):
        """Request user input with timeout"""
        if self.user_input_future and not self.user_input_future.done():
            ws_logger.warning(f"Previous input request still pending for {self.session_id}")
            return "timeout"
        
        self.user_input_future = asyncio.Future()
        self.current_approval_stage = stage
        
        # Send approval request
        approval_msg = MessageRegistry.create_message(
            "approval_request",  # Using string to avoid circular import
            session_id=self.session_id,
            stage=stage,
            prompt=prompt,
            timeout_seconds=timeout
        )
        
        await self.send_message(approval_msg)
        
        try:
            response = await asyncio.wait_for(self.user_input_future, timeout=timeout)
            
            # Record in history
            self.approval_history.append({
                "stage": stage,
                "prompt": prompt,
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
            
            return response
            
        except asyncio.TimeoutError:
            ws_logger.warning(f"User input timeout for {self.session_id}")
            return "auto_approve"
    
    def set_user_response(self, response: str):
        """Set user response for pending input request"""
        if self.user_input_future and not self.user_input_future.done():
            self.user_input_future.set_result(response)
            return True
        return False


class SessionManager:
    """Manages all WebSocket sessions"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Session] = {}
    
    async def create_session(self, session_id: str, websocket: WebSocket) -> Session:
        """Create a new session"""
        session = Session(session_id, websocket)
        self.active_sessions[session_id] = session
        ws_logger.info(f"📝 Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        return self.active_sessions.get(session_id)
    
    async def cleanup_session(self, session_id: str):
        """Clean up session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            # Cancel any pending futures
            if session.user_input_future and not session.user_input_future.done():
                session.user_input_future.cancel()
            
            del self.active_sessions[session_id]
            ws_logger.info(f"🧹 Cleaned up session: {session_id}")
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.active_sessions)
    
    async def broadcast_message(self, message, exclude_session: str = None):
        """Broadcast message to all sessions"""
        for session_id, session in self.active_sessions.items():
            if session_id != exclude_session:
                await session.send_message(message)