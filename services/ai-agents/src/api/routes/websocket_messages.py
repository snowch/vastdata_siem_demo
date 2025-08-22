# services/ai-agents/src/api/routes/websocket_messages.py
"""
WebSocket message factory - centralized message creation
"""

from datetime import datetime
from typing import Dict, Any, List
from core.messaging.registry import MessageRegistry, ControlMessageType

class MessageFactory:
    """Factory for creating WebSocket messages"""
    
    def connection_established(self, session_id: str) -> Dict[str, Any]:
        """Create connection established message"""
        return MessageRegistry.create_message(
            ControlMessageType.CONNECTION_ESTABLISHED,
            session_id=session_id,
            features=[
                "clean_message_architecture", 
                "modular_design", 
                "multi_stage_approval",
                "real_time_streaming"
            ],
            server_info={
                "version": "3.0.0-refactored",
                "architecture": "modular_clean_messaging",
                "supported_agents": ["triage", "context", "analyst"]
            }
        )
    
    def analysis_complete(
        self, 
        session_id: str, 
        success: bool, 
        results_summary: Dict[str, Any] = None,
        duration_seconds: float = None
    ) -> Dict[str, Any]:
        """Create analysis complete message"""
        return MessageRegistry.create_message(
            ControlMessageType.ANALYSIS_COMPLETE,
            session_id=session_id,
            success=success,
            results_summary=results_summary or {},
            duration_seconds=duration_seconds
        )
    
    def workflow_rejected(
        self, 
        session_id: str, 
        rejected_stage: str, 
        reason: str = None
    ) -> Dict[str, Any]:
        """Create workflow rejected message"""
        return MessageRegistry.create_message(
            ControlMessageType.WORKFLOW_REJECTED,
            session_id=session_id,
            rejected_stage=rejected_stage,
            reason=reason
        )
    
    def agent_status_update(
        self, 
        session_id: str, 
        agent: str, 
        status: str, 
        message: str = None
    ) -> Dict[str, Any]:
        """Create agent status update message"""
        return {
            "type": "agent_status_update",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "status": status,
            "message": message
        }
    
    def workflow_progress(
        self, 
        session_id: str, 
        progress_percentage: int, 
        current_stage: str,
        completed_stages: List[str] = None,
        estimated_time_remaining: int = None
    ) -> Dict[str, Any]:
        """Create workflow progress message"""
        return {
            "type": "workflow_progress",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "progress_percentage": progress_percentage,
            "current_stage": current_stage,
            "completed_stages": completed_stages or [],
            "estimated_time_remaining": estimated_time_remaining
        }
    
    def triage_findings(
        self, 
        session_id: str, 
        findings_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create triage findings message"""
        return {
            "type": "triage_findings",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent": "triage",
            "data": findings_data
        }
    
    def context_research(
        self, 
        session_id: str, 
        research_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create context research message"""
        return {
            "type": "context_research",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent": "context",
            "data": research_data
        }
    
    def analysis_recommendations(
        self, 
        session_id: str, 
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create analysis recommendations message"""
        return {
            "type": "analysis_recommendations",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent": "analyst",
            "data": analysis_data
        }