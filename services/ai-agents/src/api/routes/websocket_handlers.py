# services/ai-agents/src/api/routes/websocket_handlers.py - COMPLETE FIXED FILE
"""
WebSocket message handlers - clean separation of concerns
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from core.services.agent_service import run_analysis_workflow
from infrastructure.trino_db_reader import get_logs
from core.messaging.simple_registry import MessageRegistry, ControlMessageType
from .websocket_session import SessionManager
from .websocket_messages import MessageFactory
import logging

ws_logger = logging.getLogger("websocket_server")

class MessageHandlers:
    """Handles all WebSocket message types"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.message_factory = MessageFactory()
        
        # Handler mapping
        self.handlers = {
            "start_analysis": self.handle_start_analysis,
            "TextMessage": self.handle_user_input,
            "user_approval": self.handle_user_approval,
            "retrieve_logs": self.handle_retrieve_logs,
            "ping": self.handle_ping,
            "get_approval_history": self.handle_get_approval_history,
            "get_supported_types": self.handle_get_supported_types,
        }
    
    async def handle_message(self, data: Dict[str, Any], session_id: str):
        """Route message to appropriate handler"""
        message_type = data.get("type")
        
        if not message_type:
            await self._send_error(session_id, "Missing message type")
            return
        
        handler = self.handlers.get(message_type)
        if not handler:
            await self._send_error(
                session_id, 
                f"Unknown message type: {message_type}",
                "UNKNOWN_MESSAGE_TYPE"
            )
            return
        
        try:
            await handler(data, session_id)
        except Exception as e:
            ws_logger.error(f"❌ Error handling {message_type} for {session_id}: {e}")
            await self._send_error(session_id, f"Message processing error: {str(e)}")
    
    async def handle_start_analysis(self, data: Dict[str, Any], session_id: str):
        """Handle analysis start request"""
        log_batch = data.get("logs")
        if not log_batch:
            await self._send_error(session_id, "No logs provided for analysis")
            return
        
        ws_logger.info(f"🚀 Starting analysis for session {session_id}")
        
        # Start analysis in background
        asyncio.create_task(self._run_analysis(log_batch, session_id))
    
    async def handle_user_input(self, data: Dict[str, Any], session_id: str):
        """Handle user input response - FIXED TO ACTIVATE NEXT STAGE"""
        content = data.get("content", "")
        
        session = self.session_manager.get_session(session_id)
        if not session:
            ws_logger.error(f"Session not found: {session_id}")
            return
        
        # Use the session's current approval stage
        stage = session.current_approval_stage or "unknown"
        ws_logger.info(f"📥 Processing user response for {stage} stage: {content}")
        
        processed_response = self._process_user_response(content, stage)
        
        if session.set_user_response(processed_response):
            ws_logger.info(f"👤 User input processed for {session_id} ({stage})")
            
            # CRITICAL FIX: After approval, activate the NEXT stage
            if content.lower().strip() in ['approve', 'approved', 'yes', 'continue']:
                next_stage = self._get_next_stage(stage)
                if next_stage:
                    await self._send_agent_status_update(session_id, next_stage, "active")
                    ws_logger.info(f"✅ Activated next stage: {next_stage}")
            
        else:
            ws_logger.warning(f"⚠️ No pending user input for {session_id}")
    
    async def handle_user_approval(self, data: Dict[str, Any], session_id: str):
        """Handle legacy approval format"""
        decision = data.get("decision", "")
        await self.handle_user_input({"content": decision}, session_id)
    
    async def handle_retrieve_logs(self, data: Dict[str, Any], session_id: str):
        """Handle log retrieval request"""
        ws_logger.info(f"📥 Log retrieval requested: {session_id}")
        
        try:
            logs = get_logs()
            
            logs_msg = MessageRegistry.create_message(
                ControlMessageType.LOGS_RETRIEVED,
                session_id=session_id,
                logs=logs,
                count=len(logs),
                message=f"Retrieved {len(logs)} log entries successfully"
            )
            
            session = self.session_manager.get_session(session_id)
            if session:
                await session.send_message(logs_msg)
                ws_logger.info(f"✅ Sent {len(logs)} logs to {session_id}")
            
        except Exception as e:
            await self._send_error(session_id, f"Log retrieval error: {str(e)}")
    
    async def handle_ping(self, data: Dict[str, Any], session_id: str):
        """Handle ping request"""
        pong_msg = MessageRegistry.create_message(
            ControlMessageType.PONG,
            session_id=session_id
        )
        
        session = self.session_manager.get_session(session_id)
        if session:
            await session.send_message(pong_msg)
            ws_logger.debug(f"🏓 Sent pong to {session_id}")
    
    async def handle_get_approval_history(self, data: Dict[str, Any], session_id: str):
        """Get approval history for session"""
        session = self.session_manager.get_session(session_id)
        
        history_data = {
            "type": "approval_history_response",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "history": session.approval_history if session else [],
            "current_stage": session.current_approval_stage if session else None,
            "total_approvals": len(session.approval_history) if session else 0
        }
        
        if session:
            await session.send_message(history_data)
    
    async def handle_get_supported_types(self, data: Dict[str, Any], session_id: str):
        """Handle request for supported message types"""
        advertisement_msg = MessageRegistry.create_message(
            ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT,
            session_id=session_id
        )
        
        session = self.session_manager.get_session(session_id)
        if session:
            await session.send_message(advertisement_msg)
    
    async def _run_analysis(self, log_batch: str, session_id: str):
        """Run analysis workflow in background"""
        try:
            # Get session for user input callback
            session = self.session_manager.get_session(session_id)
            if not session:
                ws_logger.error(f"Session not found for analysis: {session_id}")
                return
            
            # Create user input callback
            async def user_input_callback(prompt: str, session_id: str) -> str:
                return await session.request_user_input(prompt, "analysis")
            
            # Create message callback
            async def message_callback(message_data: dict):
                await session.send_message(message_data)
            
            # Run the analysis
            success = await run_analysis_workflow(
                log_batch=log_batch,
                session_id=session_id,
                user_input_callback=user_input_callback,
                message_callback=message_callback
            )
            
            ws_logger.info(f"✅ Analysis completed for {session_id}: {success}")
            
        except Exception as e:
            ws_logger.error(f"❌ Analysis failed for {session_id}: {e}")
            await self._send_error(session_id, f"Analysis error: {str(e)}")
    
    def _process_user_response(self, content: str, approval_stage: str) -> str:
        """Process user response based on content and stage"""
        content_lower = content.lower().strip()
        
        if content_lower in ['approve', 'approved', 'yes', 'continue']:
            return f"APPROVED - {approval_stage} stage approved. Proceed to next stage."
        elif content_lower in ['reject', 'rejected', 'no', 'stop', 'cancel']:
            return f"REJECTED - {approval_stage} stage rejected. WORKFLOW_REJECTED"
        elif content_lower.startswith('custom:'):
            custom_instructions = content[7:].strip()
            return f"CUSTOM - User provided instructions: {custom_instructions}"
        else:
            return f"CUSTOM - User response: {content}"
    
    def _get_next_stage(self, current_stage: str) -> str:
        """Get the next stage after approval"""
        stage_flow = {
            'triage': 'context',
            'context': 'analyst',
            'analyst': None  # No next stage after analyst
        }
        return stage_flow.get(current_stage)
    
    async def _send_agent_status_update(self, session_id: str, agent: str, status: str):
        """Send agent status update message"""
        status_msg = {
            "type": "agent_status_update",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "status": status,
            "message": f"{agent} agent status updated to {status}"
        }
        
        session = self.session_manager.get_session(session_id)
        if session:
            await session.send_message(status_msg)
            ws_logger.info(f"📤 Sent agent status update: {agent} -> {status}")
    
    async def _send_error(self, session_id: str, message: str, error_code: str = "GENERAL_ERROR"):
        """Send error message to session"""
        session = self.session_manager.get_session(session_id)
        if session:
            await session.send_error(message, error_code)