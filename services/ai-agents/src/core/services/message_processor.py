# services/ai-agents/src/core/services/message_processor.py - FIX APPROVAL WORKFLOW
"""
Message Processor - Handles streaming messages from agents
FIXED: Proper approval workflow - only complete after final approval
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
        
        # 🔧 FIX: Track approval workflow state
        self.pending_final_approval = False
        self.analyst_results_received = False
    
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
            
            # 🔧 FIX: Handle text messages for approval responses
            elif isinstance(message, TextMessage):
                await self._handle_text_message(message, source, external_termination)
            
        except Exception as e:
            agent_logger.error(f"❌ Error processing message: {e}")
            await self.send_error(f"Message processing error: {str(e)}")
    
    async def _handle_structured_message(self, message, source: str, external_termination: ExternalTermination):
        """Handle structured messages from agents - FIXED COMPLETION LOGIC"""
        content = message.content
        
        # Triage findings
        if isinstance(content, PriorityFindings):
            if source == "TriageSpecialist":
                await self._process_triage_findings(content)
        
        # Context research
        elif isinstance(content, ContextResearchResult):
            if source == "ContextAgent":
                await self._process_context_research(content)
        
        # Final analysis results - 🔧 FIX: Handle completion properly
        elif isinstance(content, SOCAnalysisResult):
            if source == "SeniorAnalystSpecialist":
                await self._process_analyst_results(content, external_termination)
    
    async def _process_triage_findings(self, findings: PriorityFindings):
        """Process triage findings - same as before"""
        self.state_manager.store_triage_findings(findings)
        
        # Send findings to UI
        await self._send_message({
            "type": "triage_findings",
            "session_id": self.session_id,
            "agent": "triage",
            "data": findings.model_dump()
        })
        
        # Set triage to "complete" (spinner disappears, findings show)
        await self._send_agent_status_update("triage", "complete")
        
        # Update progress
        await self.send_progress_update(
            self.state_manager.get_progress_percentage(),
            "Triage Complete"
        )
    
    async def _process_context_research(self, research: ContextResearchResult):
        """Process context research - same as before"""
        self.state_manager.store_context_research(research)
        
        # Send research to UI
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
        
        # Set context to "complete"
        await self._send_agent_status_update("context", "complete")
        
        # Update progress
        await self.send_progress_update(
            self.state_manager.get_progress_percentage(),
            "Context Research Complete"
        )
    
    async def _process_analyst_results(self, result: SOCAnalysisResult, external_termination: ExternalTermination):
        """Process analyst results - 🔧 FIXED: Don't complete until approval"""
        self.state_manager.store_structured_result(result)
        
        # Extract analysis data
        analysis_data = result.detailed_analysis.model_dump()
        self.state_manager.store_analyst_results(analysis_data)
        
        # Send analysis to UI
        await self._send_message({
            "type": "analysis_recommendations",
            "session_id": self.session_id,
            "agent": "analyst",
            "data": analysis_data
        })
        
        # Set analyst to "complete" (shows results)
        await self._send_agent_status_update("analyst", "complete")
        
        # 🔧 FIX: Track that analyst results were received
        self.analyst_results_received = True
        
        # 🔧 FIX: Check completion flags - but don't complete if awaiting approval
        if (result.workflow_complete and result.analysis_status == "complete"):
            # Traditional immediate completion (for backward compatibility)
            external_termination.set()
            agent_logger.info("✅ Workflow completion detected via immediate completion flags")
        elif (result.analysis_status == "awaiting_approval"):
            # 🔧 NEW: Proper approval workflow
            self.pending_final_approval = True
            agent_logger.info("⏳ Analyst results ready - awaiting final approval")
            agent_logger.info("🔧 Workflow will complete after approval is received")
        else:
            # Default case - treat as awaiting approval
            self.pending_final_approval = True
            agent_logger.info("⏳ Analyst results ready - defaulting to awaiting approval")
    
    async def _handle_approval_request(self, message, source: str):
        """Handle approval requests - same as before"""
        # Map agent source to stage name
        stage = self._map_source_to_stage(source)
        context = self.state_manager.get_context_for_approval(stage)
        
        # Send approval request to UI (this will show the approval box)
        await self._send_message({
            "type": "approval_request",
            "session_id": self.session_id,
            "stage": stage,
            "prompt": getattr(message, 'content', 'Approval required'),
            "context": context,
            "timeout_seconds": 300
        })
        
        agent_logger.info(f"📝 Approval request sent for {stage} (agent stays 'complete')")
    
    def _map_source_to_stage(self, source: str) -> str:
        """Map agent source names to UI stage names - same as before"""
        # Direct mapping for approval agents
        if "TriageApproval" in source:
            return "triage"
        elif "ContextApproval" in source:
            return "context" 
        elif "AnalystApproval" in source:
            return "analyst"
        
        # Fallback mapping for agent names
        source_lower = source.lower()
        if 'triage' in source_lower:
            return 'triage'
        elif 'context' in source_lower:
            return 'context'
        elif 'analyst' in source_lower:
            return 'analyst'
        
        # Default to workflow state
        completed_stages = self.state_manager.completed_stages
        if 'triage' not in completed_stages:
            return 'triage'
        elif 'context' not in completed_stages:
            return 'context'
        else:
            return 'analyst'
    
    async def _handle_text_message(self, message, source: str, external_termination: ExternalTermination):
        """Handle text messages - 🔧 FIXED: Proper approval detection"""
        content = str(message.content)
        
        # 🔧 FIX: Check for approval responses from approval agents
        if source in ["AnalystApprovalAgent", "TriageApprovalAgent", "ContextApprovalAgent"]:
            agent_logger.info(f"📝 Approval response from {source}: {content}")
            
            # 🔧 FIX: If this is analyst approval and workflow is pending
            if (source == "AnalystApprovalAgent" and 
                self.pending_final_approval and 
                self.analyst_results_received):
                
                # Check if approval was given (not rejected)
                content_lower = content.lower()
                if any(keyword in content_lower for keyword in ['approve', 'approved', 'yes', 'continue', 'custom']):
                    agent_logger.info("✅ Final analyst approval received - completing workflow")
                    
                    # Mark workflow as complete
                    self.state_manager.workflow_complete = True
                    self.pending_final_approval = False
                    
                    # Trigger completion
                    external_termination.set()
                    
                    # Send completion message
                    await self.send_completion_message(True, self.state_manager.get_workflow_duration())
                    
                elif any(keyword in content_lower for keyword in ['reject', 'no', 'stop', 'cancel']):
                    agent_logger.info("❌ Final analyst approval rejected - workflow stopped")
                    self.state_manager.workflow_rejected = True
                    external_termination.set()
                else:
                    agent_logger.info("ℹ️ Custom analyst response - treating as approval")
                    # Custom responses are treated as approvals
                    self.state_manager.workflow_complete = True
                    self.pending_final_approval = False
                    external_termination.set()
                    await self.send_completion_message(True, self.state_manager.get_workflow_duration())
        
        # Legacy completion detection (fallback)
        elif ("ANALYSIS_COMPLETE" in content and 
              source == "SeniorAnalystSpecialist" and
              not self.state_manager.is_workflow_complete()):
            
            agent_logger.info("✅ Workflow completion detected via legacy text signal")
            self.state_manager.workflow_complete = True
            external_termination.set()
    
    async def send_progress_update(self, percentage: int, stage: str):
        """Send progress update - same as before"""
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
        agent_logger.info(f"📤 Sent workflow completion message: success={success}")
    
    async def send_error(self, error_message: str):
        """Send error message - same as before"""
        await self._send_message({
            "type": "error",
            "session_id": self.session_id,
            "message": error_message,
            "error_code": "WORKFLOW_ERROR"
        })
    
    async def _send_agent_status_update(self, agent: str, status: str):
        """Send agent status update - same as before"""
        status_msg = {
            "type": "agent_status_update",
            "session_id": self.session_id,
            "agent": agent,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "message": f"{agent} agent status: {status}"
        }
        
        await self._send_message(status_msg)
        agent_logger.info(f"📤 Agent status update sent: {agent} -> {status}")
    
    async def _send_message(self, message_data):
        """Send message via callback - same as before"""
        if self.message_callback:
            try:
                await self.message_callback(message_data)
            except Exception as e:
                agent_logger.error(f"❌ Error sending message: {e}")