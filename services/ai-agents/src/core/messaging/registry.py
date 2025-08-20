# services/ai-agents/src/core/messaging/registry.py
"""
Clean Message Architecture Registry
Centralized message type definitions with Pydantic models for type safety
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============================================================================
# MESSAGE TYPE ENUMS
# ============================================================================

class MessageCategory(str, Enum):
    """High-level message categories"""
    RESULTS = "results"
    STATUS = "status" 
    INTERACTION = "interaction"
    CONTROL = "control"

class ResultMessageType(str, Enum):
    """Structured results from agent analysis"""
    TRIAGE_FINDINGS = "triage_findings"
    CONTEXT_RESEARCH = "context_research"
    ANALYSIS_RECOMMENDATIONS = "analysis_recommendations"

class StatusMessageType(str, Enum):
    """Progress and state updates"""
    AGENT_STATUS_UPDATE = "agent_status_update"
    AGENT_FUNCTION_DETECTED = "agent_function_detected"
    AGENT_OUTPUT_STREAM = "agent_output_stream"
    WORKFLOW_PROGRESS = "workflow_progress"

class InteractionMessageType(str, Enum):
    """Human interaction workflow"""
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    APPROVAL_TIMEOUT = "approval_timeout"

class ControlMessageType(str, Enum):
    """System-level control messages"""
    CONNECTION_ESTABLISHED = "connection_established"
    MESSAGE_TYPES_ADVERTISEMENT = "message_types_advertisement"
    ANALYSIS_COMPLETE = "analysis_complete"
    WORKFLOW_REJECTED = "workflow_rejected"
    ERROR = "error"
    LOGS_RETRIEVED = "logs_retrieved"
    PING = "ping"
    PONG = "pong"

# Union of all message types for validation
AllMessageTypes = Union[
    ResultMessageType,
    StatusMessageType, 
    InteractionMessageType,
    ControlMessageType
]

# ============================================================================
# BASE MESSAGE MODELS
# ============================================================================

class BaseMessage(BaseModel):
    """Base message structure for all WebSocket messages"""
    type: str = Field(..., description="Message type identifier")
    session_id: str = Field(..., description="WebSocket session identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")

class BaseResultMessage(BaseMessage):
    """Base for structured analysis results"""
    category: Literal[MessageCategory.RESULTS] = MessageCategory.RESULTS
    agent: str = Field(..., description="Agent that produced the result")
    data: Dict[str, Any] = Field(..., description="Structured result data")

class BaseStatusMessage(BaseMessage):
    """Base for status and progress updates"""
    category: Literal[MessageCategory.STATUS] = MessageCategory.STATUS
    agent: Optional[str] = Field(None, description="Agent the status relates to")

class BaseInteractionMessage(BaseMessage):
    """Base for human interaction messages"""
    category: Literal[MessageCategory.INTERACTION] = MessageCategory.INTERACTION
    stage: Optional[str] = Field(None, description="Approval stage")

class BaseControlMessage(BaseMessage):
    """Base for system control messages"""
    category: Literal[MessageCategory.CONTROL] = MessageCategory.CONTROL

# ============================================================================
# STRUCTURED RESULT MESSAGES
# ============================================================================

class TriageFindingsMessage(BaseResultMessage):
    """Triage agent findings with structured threat data"""
    type: Literal[ResultMessageType.TRIAGE_FINDINGS] = ResultMessageType.TRIAGE_FINDINGS
    agent: Literal["triage"] = "triage"
    
    class TriageFindingsData(BaseModel):
        priority: Literal["critical", "high", "medium", "low"]
        threat_type: str
        source_ip: str
        target_hosts: List[str]
        attack_pattern: str
        timeline: Dict[str, str]  # start, end
        indicators: List[str]
        confidence_score: float = Field(ge=0.0, le=1.0)
        event_count: int = Field(ge=1)
        affected_services: List[str]
        brief_summary: str
        
    data: TriageFindingsData

class ContextResearchMessage(BaseResultMessage):
    """Context agent research results"""
    type: Literal[ResultMessageType.CONTEXT_RESEARCH] = ResultMessageType.CONTEXT_RESEARCH
    agent: Literal["context"] = "context"
    
    class ContextResearchData(BaseModel):
        search_queries: List[str]
        total_documents_found: int
        relevant_incidents: List[Dict[str, Any]]
        pattern_analysis: str
        recommendations: List[str]
        confidence_assessment: str
        
    data: ContextResearchData

class AnalysisRecommendationsMessage(BaseResultMessage):
    """Analyst agent final recommendations"""
    type: Literal[ResultMessageType.ANALYSIS_RECOMMENDATIONS] = ResultMessageType.ANALYSIS_RECOMMENDATIONS
    agent: Literal["analyst"] = "analyst"
    
    class AnalysisRecommendationsData(BaseModel):
        threat_assessment: Dict[str, Any]
        attack_timeline: List[Dict[str, Any]]
        attribution_indicators: List[str]
        lateral_movement_evidence: List[str]
        data_at_risk: List[str]
        business_impact: str
        recommended_actions: List[str]
        investigation_notes: str
        
    data: AnalysisRecommendationsData

# ============================================================================
# STATUS UPDATE MESSAGES
# ============================================================================

class AgentStatusUpdateMessage(BaseStatusMessage):
    """Agent status change notification"""
    type: Literal[StatusMessageType.AGENT_STATUS_UPDATE] = StatusMessageType.AGENT_STATUS_UPDATE
    agent: str = Field(..., description="Agent name")
    status: Literal["pending", "active", "complete", "error", "awaiting-approval"] = Field(..., description="New status")
    previous_status: Optional[str] = Field(None, description="Previous status")
    message: Optional[str] = Field(None, description="Status change description")

class AgentFunctionDetectedMessage(BaseStatusMessage):
    """Agent function call detection"""
    type: Literal[StatusMessageType.AGENT_FUNCTION_DETECTED] = StatusMessageType.AGENT_FUNCTION_DETECTED
    agent: str = Field(..., description="Agent name")
    function_name: str = Field(..., description="Function being called")
    description: Optional[str] = Field(None, description="Function description")

class AgentOutputStreamMessage(BaseStatusMessage):
    """Real-time agent output streaming"""
    type: Literal[StatusMessageType.AGENT_OUTPUT_STREAM] = StatusMessageType.AGENT_OUTPUT_STREAM
    agent: str = Field(..., description="Agent name")
    content: str = Field(..., description="Output content")
    is_final: bool = Field(False, description="Whether this is final output")

class WorkflowProgressMessage(BaseStatusMessage):
    """Overall workflow progress update"""
    type: Literal[StatusMessageType.WORKFLOW_PROGRESS] = StatusMessageType.WORKFLOW_PROGRESS
    progress_percentage: int = Field(ge=0, le=100, description="Overall progress")
    current_stage: str = Field(..., description="Current workflow stage")
    completed_stages: List[str] = Field(default_factory=list, description="Completed stages")
    estimated_time_remaining: Optional[int] = Field(None, description="Estimated seconds remaining")

# ============================================================================
# INTERACTION MESSAGES
# ============================================================================

class ApprovalRequestMessage(BaseInteractionMessage):
    """Request for human approval"""
    type: Literal[InteractionMessageType.APPROVAL_REQUEST] = InteractionMessageType.APPROVAL_REQUEST
    stage: str = Field(..., description="Approval stage (triage, context, analyst)")
    prompt: str = Field(..., description="Approval prompt text")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    timeout_seconds: Optional[int] = Field(300, description="Approval timeout")
    
class ApprovalResponseMessage(BaseInteractionMessage):
    """Human approval response"""
    type: Literal[InteractionMessageType.APPROVAL_RESPONSE] = InteractionMessageType.APPROVAL_RESPONSE
    stage: str = Field(..., description="Approval stage")
    decision: Literal["approve", "reject", "custom"] = Field(..., description="Approval decision")
    custom_instructions: Optional[str] = Field(None, description="Custom instructions if decision is custom")
    
class ApprovalTimeoutMessage(BaseInteractionMessage):
    """Approval timeout notification"""
    type: Literal[InteractionMessageType.APPROVAL_TIMEOUT] = InteractionMessageType.APPROVAL_TIMEOUT
    stage: str = Field(..., description="Approval stage that timed out")
    default_action: str = Field(..., description="Default action taken")

# ============================================================================
# CONTROL MESSAGES
# ============================================================================

class ConnectionEstablishedMessage(BaseControlMessage):
    """WebSocket connection establishment"""
    type: Literal[ControlMessageType.CONNECTION_ESTABLISHED] = ControlMessageType.CONNECTION_ESTABLISHED
    features: List[str] = Field(default_factory=list, description="Enabled features")
    server_info: Dict[str, Any] = Field(default_factory=dict, description="Server information")

class MessageTypesAdvertisementMessage(BaseControlMessage):
    """Advertise supported message types to client"""
    type: Literal[ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT] = ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT
    
    class SupportedMessageTypes(BaseModel):
        results: List[str] = Field(default_factory=lambda: [e.value for e in ResultMessageType])
        status: List[str] = Field(default_factory=lambda: [e.value for e in StatusMessageType])
        interaction: List[str] = Field(default_factory=lambda: [e.value for e in InteractionMessageType])
        control: List[str] = Field(default_factory=lambda: [e.value for e in ControlMessageType])
        all_types: List[str] = Field(default_factory=lambda: [
            *[e.value for e in ResultMessageType],
            *[e.value for e in StatusMessageType], 
            *[e.value for e in InteractionMessageType],
            *[e.value for e in ControlMessageType]
        ])
        
    supported_types: SupportedMessageTypes = Field(default_factory=SupportedMessageTypes)

class AnalysisCompleteMessage(BaseControlMessage):
    """Analysis workflow completion"""
    type: Literal[ControlMessageType.ANALYSIS_COMPLETE] = ControlMessageType.ANALYSIS_COMPLETE
    success: bool = Field(..., description="Whether analysis completed successfully")
    results_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of results")
    duration_seconds: Optional[float] = Field(None, description="Analysis duration")

class WorkflowRejectedMessage(BaseControlMessage):
    """Workflow rejection notification"""
    type: Literal[ControlMessageType.WORKFLOW_REJECTED] = ControlMessageType.WORKFLOW_REJECTED
    rejected_stage: str = Field(..., description="Stage where rejection occurred")
    reason: Optional[str] = Field(None, description="Rejection reason")

class ErrorMessage(BaseControlMessage):
    """Error notification"""
    type: Literal[ControlMessageType.ERROR] = ControlMessageType.ERROR
    error_code: Optional[str] = Field(None, description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

class LogsRetrievedMessage(BaseControlMessage):
    """Logs retrieval notification"""
    type: Literal[ControlMessageType.LOGS_RETRIEVED] = ControlMessageType.LOGS_RETRIEVED
    logs: List[Dict[str, Any]] = Field(..., description="Retrieved log entries")
    count: int = Field(..., description="Number of logs retrieved")
    message: str = Field(..., description="Success message")

class PingMessage(BaseControlMessage):
    """Ping message for connection testing"""
    type: Literal[ControlMessageType.PING] = ControlMessageType.PING

class PongMessage(BaseControlMessage):
    """Pong response to ping"""
    type: Literal[ControlMessageType.PONG] = ControlMessageType.PONG

# ============================================================================
# MESSAGE REGISTRY AND FACTORY
# ============================================================================

class MessageRegistry:
    """Central registry for all message types and their models"""
    
    # Map message types to their Pydantic models
    TYPE_TO_MODEL = {
        # Results
        ResultMessageType.TRIAGE_FINDINGS: TriageFindingsMessage,
        ResultMessageType.CONTEXT_RESEARCH: ContextResearchMessage,
        ResultMessageType.ANALYSIS_RECOMMENDATIONS: AnalysisRecommendationsMessage,
        
        # Status
        StatusMessageType.AGENT_STATUS_UPDATE: AgentStatusUpdateMessage,
        StatusMessageType.AGENT_FUNCTION_DETECTED: AgentFunctionDetectedMessage,
        StatusMessageType.AGENT_OUTPUT_STREAM: AgentOutputStreamMessage,
        StatusMessageType.WORKFLOW_PROGRESS: WorkflowProgressMessage,
        
        # Interaction
        InteractionMessageType.APPROVAL_REQUEST: ApprovalRequestMessage,
        InteractionMessageType.APPROVAL_RESPONSE: ApprovalResponseMessage,
        InteractionMessageType.APPROVAL_TIMEOUT: ApprovalTimeoutMessage,
        
        # Control
        ControlMessageType.CONNECTION_ESTABLISHED: ConnectionEstablishedMessage,
        ControlMessageType.MESSAGE_TYPES_ADVERTISEMENT: MessageTypesAdvertisementMessage,
        ControlMessageType.ANALYSIS_COMPLETE: AnalysisCompleteMessage,
        ControlMessageType.WORKFLOW_REJECTED: WorkflowRejectedMessage,
        ControlMessageType.ERROR: ErrorMessage,
        ControlMessageType.LOGS_RETRIEVED: LogsRetrievedMessage,
        ControlMessageType.PING: PingMessage,
        ControlMessageType.PONG: PongMessage,
    }
    
    @classmethod
    def get_model(cls, message_type: str) -> Optional[BaseMessage]:
        """Get the Pydantic model for a message type"""
        return cls.TYPE_TO_MODEL.get(message_type)
    
    @classmethod
    def validate_message(cls, message_type: str, data: Dict[str, Any]) -> BaseMessage:
        """Validate and parse a message using its registered model"""
        model_class = cls.get_model(message_type)
        if not model_class:
            raise ValueError(f"Unknown message type: {message_type}")
        
        return model_class(**data)
    
    @classmethod
    def get_supported_types(cls) -> Dict[str, List[str]]:
        """Get all supported message types organized by category"""
        return {
            "results": [e.value for e in ResultMessageType],
            "status": [e.value for e in StatusMessageType],
            "interaction": [e.value for e in InteractionMessageType],
            "control": [e.value for e in ControlMessageType],
            "all_types": list(cls.TYPE_TO_MODEL.keys())
        }
    
    @classmethod
    def create_message(cls, message_type: str, session_id: str, **kwargs) -> BaseMessage:
        """Factory method to create typed messages"""
        model_class = cls.get_model(message_type)
        if not model_class:
            raise ValueError(f"Unknown message type: {message_type}")
        
        # Ensure required fields are provided
        message_data = {
            "type": message_type,
            "session_id": session_id,
            "timestamp": datetime.now(),
            **kwargs
        }
        
        return model_class(**message_data)

# ============================================================================
# MESSAGE VALIDATION UTILITIES
# ============================================================================

def validate_message_type(message_type: str) -> bool:
    """Validate that a message type is supported"""
    return message_type in MessageRegistry.TYPE_TO_MODEL

def get_message_category(message_type: str) -> Optional[str]:
    """Get the category for a message type"""
    model_class = MessageRegistry.get_model(message_type)
    if model_class and hasattr(model_class, 'category'):
        return model_class.category.value if hasattr(model_class.category, 'value') else model_class.category
    return None

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_triage_findings(session_id: str, findings_data: Dict[str, Any]) -> TriageFindingsMessage:
    """Convenience function to create triage findings message"""
    return MessageRegistry.create_message(
        ResultMessageType.TRIAGE_FINDINGS,
        session_id=session_id,
        data=TriageFindingsMessage.TriageFindingsData(**findings_data)
    )

def create_agent_status_update(session_id: str, agent: str, status: str, message: str = None) -> AgentStatusUpdateMessage:
    """Convenience function to create agent status update"""
    return MessageRegistry.create_message(
        StatusMessageType.AGENT_STATUS_UPDATE,
        session_id=session_id,
        agent=agent,
        status=status,
        message=message
    )

def create_approval_request(session_id: str, stage: str, prompt: str, context: Dict[str, Any] = None) -> ApprovalRequestMessage:
    """Convenience function to create approval request"""
    return MessageRegistry.create_message(
        InteractionMessageType.APPROVAL_REQUEST,
        session_id=session_id,
        stage=stage,
        prompt=prompt,
        context=context or {}
    )

def create_error_message(session_id: str, message: str, error_code: str = None, details: Dict[str, Any] = None) -> ErrorMessage:
    """Convenience function to create error message"""
    return MessageRegistry.create_message(
        ControlMessageType.ERROR,
        session_id=session_id,
        message=message,
        error_code=error_code,
        details=details
    )