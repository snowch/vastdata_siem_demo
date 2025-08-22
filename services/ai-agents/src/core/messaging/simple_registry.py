# services/ai-agents/src/core/messaging/simple_registry.py
"""
Simplified Message Registry - Easier to maintain and extend
"""

from enum import Enum
from typing import Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

# ============================================================================
# SIMPLIFIED MESSAGE TYPES
# ============================================================================

class MessageType(str, Enum):
    """Simplified message type enumeration"""
    # Results
    TRIAGE_FINDINGS = "triage_findings"
    CONTEXT_RESEARCH = "context_research"
    ANALYSIS_RECOMMENDATIONS = "analysis_recommendations"
    
    # Workflow
    WORKFLOW_PROGRESS = "workflow_progress"
    ANALYSIS_COMPLETE = "analysis_complete"
    WORKFLOW_REJECTED = "workflow_rejected"
    
    # Interaction
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    APPROVAL_TIMEOUT = "approval_timeout"
    
    # System
    CONNECTION_ESTABLISHED = "connection_established"
    ERROR = "error"
    LOGS_RETRIEVED = "logs_retrieved"
    PING = "ping"
    PONG = "pong"

# ============================================================================
# BASE MESSAGE MODEL
# ============================================================================

class BaseMessage(BaseModel):
    """Simplified base message"""
    type: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# SIMPLIFIED REGISTRY
# ============================================================================

class SimpleMessageRegistry:
    """Simplified message registry for easier maintenance"""
    
    @classmethod
    def create_message(
        cls, 
        message_type: str, 
        session_id: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """Create a message with minimal structure"""
        return {
            "type": message_type,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
    
    @classmethod
    def triage_findings(
        cls, 
        session_id: str, 
        findings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create triage findings message"""
        return cls.create_message(
            MessageType.TRIAGE_FINDINGS,
            session_id,
            agent="triage",
            data=findings
        )
    
    @classmethod
    def context_research(
        cls, 
        session_id: str, 
        research: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create context research message"""
        return cls.create_message(
            MessageType.CONTEXT_RESEARCH,
            session_id,
            agent="context",
            data=research
        )
    
    @classmethod
    def analysis_recommendations(
        cls, 
        session_id: str, 
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create analysis recommendations message"""
        return cls.create_message(
            MessageType.ANALYSIS_RECOMMENDATIONS,
            session_id,
            agent="analyst",
            data=analysis
        )
    
    @classmethod
    def workflow_progress(
        cls, 
        session_id: str, 
        progress_percentage: int, 
        current_stage: str,
        completed_stages: List[str] = None
    ) -> Dict[str, Any]:
        """Create workflow progress message"""
        return cls.create_message(
            MessageType.WORKFLOW_PROGRESS,
            session_id,
            progress_percentage=progress_percentage,
            current_stage=current_stage,
            completed_stages=completed_stages or []
        )
    
    @classmethod
    def analysis_complete(
        cls, 
        session_id: str, 
        success: bool, 
        results_summary: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create analysis complete message"""
        return cls.create_message(
            MessageType.ANALYSIS_COMPLETE,
            session_id,
            success=success,
            results_summary=results_summary or {}
        )
    
    @classmethod
    def approval_request(
        cls, 
        session_id: str, 
        stage: str, 
        prompt: str, 
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create approval request message"""
        return cls.create_message(
            MessageType.APPROVAL_REQUEST,
            session_id,
            stage=stage,
            prompt=prompt,
            context=context or {}
        )
    
    @classmethod
    def error_message(
        cls, 
        session_id: str, 
        message: str, 
        error_code: str = None
    ) -> Dict[str, Any]:
        """Create error message"""
        return cls.create_message(
            MessageType.ERROR,
            session_id,
            message=message,
            error_code=error_code or "GENERAL_ERROR"
        )
    
    @classmethod
    def connection_established(
        cls, 
        session_id: str, 
        features: List[str] = None
    ) -> Dict[str, Any]:
        """Create connection established message"""
        return cls.create_message(
            MessageType.CONNECTION_ESTABLISHED,
            session_id,
            features=features or ["simplified_messaging"]
        )
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get all supported message types"""
        return [msg_type.value for msg_type in MessageType]
    
    @classmethod
    def validate_message_type(cls, message_type: str) -> bool:
        """Validate if message type is supported"""
        return message_type in cls.get_supported_types()

# ============================================================================
# COMPATIBILITY LAYER
# ============================================================================

# Provide compatibility with the complex registry
MessageRegistry = SimpleMessageRegistry
ControlMessageType = MessageType  # For backward compatibility

# Export commonly used functions
def create_message(message_type: str, session_id: str, **kwargs):
    return SimpleMessageRegistry.create_message(message_type, session_id, **kwargs)

def validate_message_type(message_type: str) -> bool:
    return SimpleMessageRegistry.validate_message_type(message_type)

def get_message_category(message_type: str) -> str:
    """Simple category determination"""
    if message_type in [MessageType.TRIAGE_FINDINGS, MessageType.CONTEXT_RESEARCH, MessageType.ANALYSIS_RECOMMENDATIONS]:
        return "results"
    elif message_type in [MessageType.WORKFLOW_PROGRESS, MessageType.ANALYSIS_COMPLETE]:
        return "workflow"
    elif message_type in [MessageType.APPROVAL_REQUEST, MessageType.APPROVAL_RESPONSE]:
        return "interaction"
    else:
        return "system"