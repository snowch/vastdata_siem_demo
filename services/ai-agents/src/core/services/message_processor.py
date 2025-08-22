# services/ai-agents/src/core/services/message_processor.py
"""
Message Processor - Handles streaming messages from agents
"""

from datetime import datetime
from typing import Optional, Callable
from autogen_agentchat.messages import StructuredMessage, TextMessage, UserInputRequestedEvent
from autogen_agentchat.conditions import ExternalTermination

from core.models.analysis import PriorityFindings, ContextResearchResult, SOCAnalysisResult
from .state_manager import WorkflowStateManager
import logging

agent_logger = logging.getLogger("agent_diagnostics")

class MessageProcessor:
    """Processes streaming messages from the agent workflow"""
    
    def __init__(
        self, 
        session_id: str, 
        state_manager: WorkflowStateManager,
        message_callback: Optional[Callable] = None
    ):
        self.session_id = session_id
        self.state_manager = state_manager
        self.message_callback = message_callback
    
    async def process_message(self, message, external_termination: ExternalTermination):
        """Process a single message from the workflow"""
        try:
            if not hasattr(message, 'source') or not hasattr(message, 'content'):
                return
            
            source = message.source
            content = message.content
            
            agent_logger.debug(f"🔍 Processing message from {source}: {type(message).__name__}")
            
            # Handle structured results
            if isinstance(message, StructuredMessage):
                await self._handle_structured_message(message, source, external_termination)
            
            # Handle approval requests
            elif isinstance(message, UserInputRequestedEvent):
                await self._handle_approval_request(message, source)
            
            # Handle text messages for additional info
            elif isinstance(message, TextMessage):
                await self._handle_text_message(message, source, external_termination)
            
        except Exception as e:
            agent_logger.error(f"❌ Error processing message: {e}")
            await self.send_error(f"Message processing error: {str(e)}")
    
    async def _handle_structured_message(self, message, source: str, external_termination: ExternalTermination):
        """Handle structured messages from agents"""
        content = message.content
        
        # Triage findings
        if isinstance(content, PriorityFindings):
            if source == "TriageSpecialist":
                await self._process_triage_findings(content)
        
        # Context research
        elif isinstance(content, ContextResearchResult):
            if source == "ContextAgent":
                await self._process_context_research(content)
        
        # Final analysis results
        elif isinstance(content, SOCAnalysisResult):
            if source == "SeniorAnalystSpecialist":
                await self._process_analyst_results(content, external_termination)
    
    async def _process_triage_findings(self, findings: PriorityFindings):
        """Process triage findings"""
        self.state_manager.store_triage_findings(findings)
        
        # Send to UI
        await self._send_message({
            "type": "triage_findings",
            "session_id": self.session_id,
            "agent": "triage",
            "data": findings.model_dump()
        })
        
        await self._send_agent_status_update("triage", "complete")
        await self.send_progress_update(
            self.state_manager.get_progress_percentage(),
            "Triage Complete"
        )
    
    async def _process_context_research(self, research: ContextResearchResult):
        """Process context research"""
        self.state_manager.store_context_research(research)
        
        # Send to UI
        await self._send_message({
            "type": "context_research",
            "session_id": self.session_id,
            "agent": "context",
            "data": {
                "search_queries": research.search_queries_executed,
                "total_documents_found": research.total_documents_found,
                "pattern_analysis": research.pattern_analysis,
                "recommendations": research.recommended_actions,
                "confidence_assessment": research.confidence_assessment
            }
        })
        
        await self._send_agent_status_update("context", "complete")
        await self.send_progress_update(
            self.state_manager.get_progress_percentage(),
            "Context Research Complete"
        )
    
    async def _process_analyst_results(self, result: SOCAnalysisResult, external_termination: ExternalTermination):
        """Process final analyst results"""
        self.state_manager.store_structured_result(result)
        
        # Extract analysis data
        analysis_data = result.detailed_analysis.model_dump()
        self.state_manager.store_analyst_results(analysis_data)
        
        # Send to UI
        await self._send_message({
            "type": "analysis_recommendations",
            "session_id": self.session_id,
            "agent": "analyst",
            "data": analysis_data
        })
        
        await self._send_agent_status_update("analyst", "complete")
        
        # Check for completion
        if result.workflow_complete or result.analysis_status == "complete":
            external_termination.set()
            agent_logger.info("✅ Workflow completion detected via structured flags")
    
    async def _handle_approval_request(self, message, source: str):
        """Handle approval requests"""
        stage = self._determine_stage_from_source(source)
        context = self.state_manager.get_context_for_approval(stage)
        
        await self._send_message({
            "type": "approval_request",
            "session_id": self.session_id,
            "stage": stage,
            "prompt": getattr(message, 'content', 'Approval required'),
            "context": context,
            "timeout_seconds": 300
        })
        
        await self._send_agent_status_update(stage, "awaiting-approval")
    
    async def _handle_text_message(self, message, source: str, external_termination: ExternalTermination):
        """Handle text messages for completion detection"""
        content = str(message.content)
        
        # Check for completion signals
        if ("ANALYSIS_COMPLETE" in content and 
            source == "SeniorAnalystSpecialist" and
            not self.state_manager.is_workflow_complete()):
            
            agent_logger.info("✅ Workflow completion detected via text signal")
            self.state_manager.workflow_complete = True
            external_termination.set()
    
    async def send_progress_update(self, percentage: int, stage: str):
        """Send progress update"""
        await self._send_message({
            "type": "workflow_progress",
            "session_id": self.session_id,
            "progress_percentage": percentage,
            "current_stage": stage,
            "completed_stages": self.state_manager.completed_stages.copy()
        })
    
    async def send_completion_message(self, success: bool, duration: float):
        """Send workflow completion message"""
        await self._send_message({
            "type": "analysis_complete",
            "session_id": self.session_id,
            "success": success,
            "results_summary": self.state_manager.get_completion_summary(),
            "duration_seconds": duration
        })
    
    async def send_error(self, error_message: str):
        """Send error message"""
        await self._send_message({
            "type": "error",
            "session_id": self.session_id,
            "message": error_message,
            "error_code": "WORKFLOW_ERROR"
        })
    
    async def _send_agent_status_update(self, agent: str, status: str):
        """Send agent status update"""
        await self._send_message({
            "type": "agent_status_update",
            "session_id": self.session_id,
            "agent": agent,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _send_message(self, message_data):
        """Send message via callback"""
        if self.message_callback:
            try:
                await self.message_callback(message_data)
            except Exception as e:
                agent_logger.error(f"❌ Error sending message: {e}")
    
    def _determine_stage_from_source(self, source: str) -> str:
        """Determine stage from message source"""
        if 'triage' in source.lower():
            return 'triage'
        elif 'context' in source.lower():
            return 'context'
        elif 'analyst' in source.lower():
            return 'analyst'
        return 'unknown'