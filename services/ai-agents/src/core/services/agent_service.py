# services/ai-agents/src/core/services/agent_service.py
"""
Agent Service with Clean Message Architecture - STRUCTURED MESSAGE VERSION
Removed regex parsing in favor of structured message data from Pydantic models
Updated to remove analyst function tool detection since analyst now uses structured output only
"""

import json
import logging
import traceback
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Awaitable
from core.agents.triage import TriageAgent
from core.agents.context import ContextAgent
from core.agents.analyst import AnalystAgent
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import StructuredMessage, UserInputRequestedEvent, TextMessage
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    TokenUsageTermination,
    TimeoutTermination,
    SourceMatchTermination,
    ExternalTermination
)
from autogen_core import CancellationToken
from core.models.analysis import SOCAnalysisResult, PriorityFindings, ContextResearchResult

# Import the new message registry
from core.messaging.registry import (
    MessageRegistry,
    ResultMessageType,
    StatusMessageType,
    InteractionMessageType,
    ControlMessageType,
    create_triage_findings,
    create_agent_status_update,
    create_approval_request,
    create_error_message,
    validate_message_type,
    get_message_category
)

agent_logger = logging.getLogger("agent_diagnostics")

# ============================================================================
# STRUCTURED DATA STORAGE FOR WORKFLOW STATE
# ============================================================================

class WorkflowState:
    """Centralized workflow state using structured data instead of regex parsing"""
    
    def __init__(self):
        self.triage_findings: Optional[PriorityFindings] = None
        self.context_research: Optional[ContextResearchResult] = None
        self.analyst_results: Optional[Dict[str, Any]] = None
        self.structured_result: Optional[SOCAnalysisResult] = None
        
    def store_triage_findings(self, findings: PriorityFindings):
        """Store structured triage findings"""
        self.triage_findings = findings
        agent_logger.info(f"✅ STRUCTURED: Stored triage findings - {findings.threat_type} from {findings.source_ip}")
        
    def store_context_research(self, research: ContextResearchResult):
        """Store structured context research"""
        self.context_research = research
        agent_logger.info(f"✅ STRUCTURED: Stored context research - {research.total_documents_found} documents")
        
    def store_analyst_results(self, results: Dict[str, Any]):
        """Store structured analyst results"""
        self.analyst_results = results
        agent_logger.info(f"✅ STRUCTURED: Stored analyst results")
        
    def get_context_for_approval(self, stage: str) -> Dict[str, Any]:
        """Get structured context data for approval requests - NO REGEX NEEDED"""
        if stage == "triage" and self.triage_findings:
            return {
                "threat_type": self.triage_findings.threat_type,
                "source_ip": self.triage_findings.source_ip,
                "priority": self.triage_findings.priority,
                "confidence_score": self.triage_findings.confidence_score,
                "brief_summary": self.triage_findings.brief_summary,
                "target_hosts": self.triage_findings.target_hosts,
                "attack_pattern": self.triage_findings.attack_pattern,
                "stage_type": "threat_assessment"
            }
        elif stage == "context" and self.context_research:
            return {
                "total_documents_found": self.context_research.total_documents_found,
                "pattern_analysis": self.context_research.pattern_analysis,
                "confidence_assessment": self.context_research.confidence_assessment,
                "search_queries_executed": self.context_research.search_queries_executed,
                "recommended_actions": self.context_research.recommended_actions,
                "stage_type": "historical_context"
            }
        elif stage == "analyst" and self.analyst_results:
            return {
                "recommendations_count": len(self.analyst_results.get('recommended_actions', [])),
                "business_impact": self.analyst_results.get('business_impact', ''),
                "threat_assessment": self.analyst_results.get('threat_assessment', {}),
                "recommended_actions": self.analyst_results.get('recommended_actions', []),
                "stage_type": "security_recommendations"
            }
        return {}

# ============================================================================
# CLEAN MESSAGE SENDER WITH STRUCTURED DATA
# ============================================================================

class CleanMessageSender:
    """Type-safe message sender using structured data instead of regex"""

    def __init__(self, session_id: str, workflow_state: WorkflowState, message_callback: Optional[Callable] = None):
        self.session_id = session_id
        self.workflow_state = workflow_state
        self.message_callback = message_callback
        self._awaiting_approval = False

    async def send_message(self, message) -> bool:
        """Send a typed message through the callback"""
        if not self.message_callback:
            agent_logger.warning(f"No message callback available for session {self.session_id}")
            return False

        try:
            # Convert Pydantic model to dict for JSON serialization
            if hasattr(message, 'model_dump'):
                message_data = message.model_dump(mode='json')
            else:
                message_data = message

            # Validate message type
            message_type = message_data.get('type')
            if not validate_message_type(message_type):
                agent_logger.error(f"❌ Invalid message type: {message_type}")
                return False

            agent_logger.debug(f"🚀 STRUCTURED: Sending {message_type} for session {self.session_id}")
            await self.message_callback(message_data)
            return True

        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send message: {e}")
            agent_logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False

    def clear_approval_state(self):
        """Clear the approval waiting state"""
        self._awaiting_approval = False
        agent_logger.debug(f"🔄 STRUCTURED: Cleared approval state for session {self.session_id}")

    async def send_triage_findings(self, findings_data: Dict[str, Any]) -> bool:
        """Send structured triage findings"""
        try:
            message = create_triage_findings(self.session_id, findings_data)
            agent_logger.info(f"✅ STRUCTURED: Sending triage findings - {findings_data.get('threat_type')} from {findings_data.get('source_ip')}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to create triage findings message: {e}")
            return False

    async def send_context_research(self, research_data: Dict[str, Any]) -> bool:
        """Send structured context research results"""
        try:
            message = MessageRegistry.create_message(
                ResultMessageType.CONTEXT_RESEARCH,
                session_id=self.session_id,
                data=research_data
            )
            agent_logger.info(f"✅ STRUCTURED: Sending context research - {research_data.get('total_documents_found', 0)} documents")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to create context research message: {e}")
            return False

    async def send_analysis_recommendations(self, analysis_data: Dict[str, Any]) -> bool:
        """Send structured analysis recommendations"""
        try:
            message = MessageRegistry.create_message(
                ResultMessageType.ANALYSIS_RECOMMENDATIONS,
                session_id=self.session_id,
                data=analysis_data
            )
            actions_count = len(analysis_data.get('recommended_actions', []))
            agent_logger.info(f"✅ STRUCTURED: Sending analysis recommendations - {actions_count} actions")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to create analysis recommendations message: {e}")
            return False

    async def send_agent_status_update(self, agent: str, status: str, message: str = None, previous_status: str = None) -> bool:
        """Send agent status update"""
        try:
            status_message = MessageRegistry.create_message(
                StatusMessageType.AGENT_STATUS_UPDATE,
                session_id=self.session_id,
                agent=agent,
                status=status,
                message=message,
                previous_status=previous_status
            )
            agent_logger.info(f"📊 STRUCTURED: Agent {agent} status: {previous_status} → {status}")
            return await self.send_message(status_message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send agent status update: {e}")
            return False

    async def send_function_detected(self, agent: str, function_name: str, description: str = None) -> bool:
        """Send function call detection"""
        try:
            message = MessageRegistry.create_message(
                StatusMessageType.AGENT_FUNCTION_DETECTED,
                session_id=self.session_id,
                agent=agent,
                function_name=function_name,
                description=description
            )
            agent_logger.info(f"🔧 STRUCTURED: Function detected - {function_name} from {agent}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send function detection: {e}")
            return False

    async def send_agent_output_stream(self, agent: str, content: str, is_final: bool = False) -> bool:
        """Send real-time agent output"""
        try:
            message = MessageRegistry.create_message(
                StatusMessageType.AGENT_OUTPUT_STREAM,
                session_id=self.session_id,
                agent=agent,
                content=content,
                is_final=is_final
            )
            agent_logger.debug(f"💬 STRUCTURED: Streaming output from {agent}: {content[:50]}...")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send agent output stream: {e}")
            return False

    async def send_workflow_progress(self, progress_percentage: int, current_stage: str, completed_stages: List[str] = None, estimated_time_remaining: int = None) -> bool:
        """Send workflow progress update"""
        try:
            message = MessageRegistry.create_message(
                StatusMessageType.WORKFLOW_PROGRESS,
                session_id=self.session_id,
                progress_percentage=progress_percentage,
                current_stage=current_stage,
                completed_stages=completed_stages or [],
                estimated_time_remaining=estimated_time_remaining
            )
            agent_logger.info(f"📈 STRUCTURED: Workflow progress: {progress_percentage}% - {current_stage}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send workflow progress: {e}")
            return False

    async def send_structured_approval_request(self, stage: str, base_prompt: str, context: Dict[str, Any] = None, timeout_seconds: int = 300) -> bool:
        """Send approval request with structured context data - NO REGEX"""
        try:
            # Get structured context from workflow state
            structured_context = self.workflow_state.get_context_for_approval(stage)
            
            # Merge with any additional context provided
            if context:
                structured_context.update(context)
            
            # Create intelligent prompt based on structured data
            intelligent_prompt = self._create_intelligent_prompt(stage, base_prompt, structured_context)
            
            message = MessageRegistry.create_message(
                InteractionMessageType.APPROVAL_REQUEST,
                session_id=self.session_id,
                stage=stage,
                prompt=intelligent_prompt,
                context=structured_context,
                timeout_seconds=timeout_seconds
            )
            
            agent_logger.info(f"📋 STRUCTURED: Sending approval request for {stage} with structured context")
            return await self.send_message(message)
            
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send structured approval request: {e}")
            return False

    def _create_intelligent_prompt(self, stage: str, base_prompt: str, context: Dict[str, Any]) -> str:
        """Create intelligent prompts using structured data instead of regex parsing"""
        
        if stage == "triage" and context.get("stage_type") == "threat_assessment":
            threat_type = context.get("threat_type", "security threat")
            source_ip = context.get("source_ip", "unknown source")
            priority = context.get("priority", "medium")
            confidence = context.get("confidence_score", 0.5)
            
            return f"Detected {priority.upper()} priority {threat_type} from {source_ip} (confidence: {confidence:.1%}). Do you want to proceed with investigating this threat?"
            
        elif stage == "context" and context.get("stage_type") == "historical_context":
            incidents_found = context.get("total_documents_found", 0)
            confidence = context.get("confidence_assessment", "medium")
            
            if incidents_found > 0:
                return f"Found {incidents_found} related historical incidents (confidence: {confidence}). Are these insights relevant for the current threat analysis?"
            else:
                return "No related historical incidents found. Should we proceed with analysis using general threat intelligence?"
                
        elif stage == "analyst" and context.get("stage_type") == "security_recommendations":
            recommendations_count = context.get("recommendations_count", 0)
            business_impact = context.get("business_impact", "Under assessment")
            
            if recommendations_count > 0:
                return f"Security analysis complete with {recommendations_count} recommendations. Business impact: {business_impact}. Do you approve these recommended actions?"
            else:
                return f"Security analysis complete. Business impact: {business_impact}. Do you approve the assessment?"
        
        # Fallback to base prompt
        return base_prompt

    async def send_analysis_complete(self, success: bool, results_summary: Dict[str, Any] = None, duration_seconds: float = None) -> bool:
        """Send analysis completion notification"""
        try:
            message = MessageRegistry.create_message(
                ControlMessageType.ANALYSIS_COMPLETE,
                session_id=self.session_id,
                success=success,
                results_summary=results_summary or {},
                duration_seconds=duration_seconds
            )
            agent_logger.info(f"🎉 STRUCTURED: Analysis complete - Success: {success}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send analysis complete: {e}")
            return False

    async def send_workflow_rejected(self, rejected_stage: str, reason: str = None) -> bool:
        """Send workflow rejection notification"""
        try:
            message = MessageRegistry.create_message(
                ControlMessageType.WORKFLOW_REJECTED,
                session_id=self.session_id,
                rejected_stage=rejected_stage,
                reason=reason
            )
            agent_logger.info(f"❌ STRUCTURED: Workflow rejected at {rejected_stage} stage")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send workflow rejection: {e}")
            return False

    async def send_error(self, error_message: str, error_code: str = None, details: Dict[str, Any] = None) -> bool:
        """Send error notification"""
        try:
            message = create_error_message(
                self.session_id,
                error_message,
                error_code,
                details
            )
            agent_logger.error(f"💥 STRUCTURED: Sending error - {error_message}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ STRUCTURED: Failed to send error message: {e}")
            return False

# ============================================================================
# WORKFLOW PROGRESS TRACKER
# ============================================================================

class WorkflowProgressTracker:
    """Track workflow progress and calculate smart percentages"""

    def __init__(self, sender: CleanMessageSender):
        self.sender = sender
        self.start_time = datetime.now()
        self.completed_stages = []
        self.current_stage = "initializing"

        # Stage definitions with their completion percentages
        self.stages = {
            "initializing": 5,
            "triage_active": 25,
            "triage_complete": 35,
            "context_active": 55,
            "context_complete": 65,
            "analyst_active": 85,
            "analyst_complete": 95,
            "finalizing": 100
        }

    async def update_stage(self, new_stage: str) -> bool:
        """Update current stage and send progress"""
        if new_stage == self.current_stage:
            return True

        # Mark previous stage as completed
        if self.current_stage not in self.completed_stages:
            self.completed_stages.append(self.current_stage)

        self.current_stage = new_stage
        progress = self.stages.get(new_stage, 0)

        # Calculate estimated time remaining
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if progress > 0 and progress < 100:
            estimated_remaining = int((elapsed / progress) * (100 - progress))
        else:
            estimated_remaining = None

        return await self.sender.send_workflow_progress(
            progress_percentage=progress,
            current_stage=new_stage.replace('_', ' ').title(),
            completed_stages=self.completed_stages.copy(),
            estimated_time_remaining=estimated_remaining
        )

# ============================================================================
# ENHANCED MESSAGE PROCESSOR WITH STRUCTURED DATA
# ============================================================================

async def _process_clean_streaming_message(
    message,
    sender: CleanMessageSender,
    progress_tracker: WorkflowProgressTracker,
    final_results: Dict[str, Any],
    workflow_state: WorkflowState,
    external_termination: ExternalTermination  # ADD: external termination parameter
):
    """Process streaming messages using structured data instead of regex parsing"""
    try:
        if not hasattr(message, 'source') or not hasattr(message, 'content'):
            return

        source = message.source
        content = str(message.content)

        agent_logger.debug(f"🔍 STRUCTURED: Processing message from {source}: {type(message).__name__}")

        # ====================================================================
        # NEW: CHECK FOR ANY APPROVAL AGENT TERMINATION CONDITIONS
        # ====================================================================
        
        # Check for any approval agent response that should terminate workflow
        approval_agents = ["TriageApprovalAgent", "ContextApprovalAgent", "AnalystApprovalAgent"]
        
        if source in approval_agents:
            should_terminate = False
            termination_reason = ""
            
            # Check for workflow rejection
            if ("WORKFLOW_REJECTED" in content or 
                ("REJECTED" in content and "human operator" in content)):
                should_terminate = True
                termination_reason = "User rejected workflow"
                final_results['was_rejected'] = True
                
            # Check for user cancellation/rejection at any stage
            elif ("REJECTED" in content or 
                  "rejected" in content.lower() or
                  "cancel" in content.lower() or
                  "stop" in content.lower()):
                should_terminate = True
                termination_reason = f"User cancelled at {source} stage"
                final_results['was_rejected'] = True
                
            # Check for successful analyst approval (final stage)
            elif (source == "AnalystApprovalAgent" and 
                  ("APPROVED" in content or "approved" in content.lower())):
                should_terminate = True
                termination_reason = "Analyst approval completed - workflow finished"
                final_results['workflow_complete'] = True
                
            # If any termination condition is met, trigger external termination
            if should_terminate:
                agent_logger.info(f"🎯 TERMINATION: {termination_reason} - triggering external termination")
                external_termination.set()
                
                # Send appropriate notification
                if final_results.get('was_rejected'):
                    await sender.send_workflow_rejected(
                        rejected_stage=source.replace("ApprovalAgent", "").lower(),
                        reason=termination_reason
                    )
                else:
                    await sender.send_analysis_complete(
                        success=True,
                        results_summary={
                            "termination_reason": termination_reason,
                            "final_stage": source
                        }
                    )
                
                return  # Exit early, no need to process further

        # ====================================================================
        # CHECK FOR WORKFLOW COMPLETION SIGNALS
        # ====================================================================

        # PRIORITY 0: Check for workflow completion signals
        if "ANALYSIS_COMPLETE - Senior SOC investigation finished" in content:
            agent_logger.info(f"✅ STRUCTURED: Workflow completion signal detected")
            final_results['workflow_complete'] = True
            external_termination.set()  # Also trigger external termination
            await sender.send_analysis_complete(
                success=True,
                results_summary={
                    "has_priority_findings": final_results.get('priority_findings') is not None,
                    "has_context_data": final_results.get('context_research') is not None,
                    "has_detailed_analysis": final_results.get('detailed_analysis') is not None,
                    "workflow_complete": True
                }
            )
            return

        # ====================================================================
        # HANDLE STRUCTURED RESULTS WITH WORKFLOW STATE
        # ====================================================================

        # PRIORITY 1: Handle structured triage findings (prevent duplicates)
        if (source == "TriageSpecialist" and
            isinstance(message, StructuredMessage) and
            isinstance(message.content, PriorityFindings)):

            # Check if we already processed triage findings
            if final_results.get('priority_findings') is not None:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate triage findings")
                return

            findings = message.content
            findings_dict = findings.model_dump()
            final_results['priority_findings'] = findings_dict

            # Store in workflow state for future approval requests
            workflow_state.store_triage_findings(findings)

            agent_logger.info(f"✅ STRUCTURED: Structured triage findings: {findings.threat_type} from {findings.source_ip}")

            # Send using clean architecture
            await sender.send_triage_findings(findings_dict)
            await sender.send_agent_status_update("triage", "complete", "Triage analysis complete")
            await progress_tracker.update_stage("triage_complete")

            return

        # PRIORITY 2: Handle structured context research results
        elif (source == "ContextAgent" and
              isinstance(message, StructuredMessage) and
              isinstance(message.content, ContextResearchResult)):

            # Check if we already processed context results
            if final_results.get('context_research') is not None:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate context research")
                return

            context_result = message.content
            context_dict = context_result.model_dump()
            final_results['context_research'] = context_dict

            # Store in workflow state for future approval requests
            workflow_state.store_context_research(context_result)

            agent_logger.info(f"✅ STRUCTURED: Structured context research: {context_result.total_documents_found} documents")

            # Parse the list of JSON strings into a list of dictionaries
            raw_incidents = context_dict.get('related_incidents', [])
            parsed_incidents = []
            for incident_str in raw_incidents:
                try:
                    # The items are strings, so we need to load them as JSON
                    parsed_incidents.append(json.loads(incident_str))
                except json.JSONDecodeError:
                    # If a string is not valid JSON, handle it gracefully
                    agent_logger.warning(f"Could not parse incident string to JSON: {incident_str}")
                    parsed_incidents.append({"raw_text": incident_str, "parse_error": True})

            # Send structured context research results
            research_data = {
                "search_queries": context_dict.get('search_queries_executed', []),
                "total_documents_found": context_dict.get('total_documents_found', 0),
                "relevant_incidents": parsed_incidents,
                "pattern_analysis": context_dict.get('pattern_analysis', ''),
                "recommendations": context_dict.get('recommended_actions', []),
                "confidence_assessment": context_dict.get('confidence_assessment', 'unknown')
            }

            await sender.send_context_research(research_data)
            await sender.send_agent_status_update("context", "complete", "Context research complete")
            await progress_tracker.update_stage("context_complete")

            # AUTO-TRIGGER STRUCTURED APPROVAL REQUEST - NO REGEX NEEDED
            if not sender._awaiting_approval:
                agent_logger.info(f"🔄 STRUCTURED: Auto-triggering context approval with structured data")
                sender._awaiting_approval = True

                await sender.send_structured_approval_request(
                    stage="context",
                    base_prompt="Are these historical insights relevant for the current threat analysis?",
                    context={
                        "source": source, 
                        "timestamp": datetime.now().isoformat(),
                        "auto_triggered": True
                    }
                )
                
                agent_logger.info(f"✅ STRUCTURED: Context approval request auto-triggered with intelligent prompt")

            return

        # PRIORITY 3: Handle structured analyst results
        elif (source == "SeniorAnalystSpecialist" and
              isinstance(message, StructuredMessage) and
              isinstance(message.content, SOCAnalysisResult)):

            # Check if we already processed analyst results
            if final_results.get('structured_result') is not None:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate analyst results")
                return

            result = message.content.model_dump()
            final_results['structured_result'] = result

            # Store in workflow state for future approval requests
            if 'detailed_analysis' in result:
                workflow_state.store_analyst_results(result['detailed_analysis'])

            agent_logger.info(f"✅ STRUCTURED: Structured analyst results received")

            # Extract analysis data and send recommendations
            if 'detailed_analysis' in result:
                await sender.send_analysis_recommendations(result['detailed_analysis'])
                
            await sender.send_agent_status_update("analyst", "complete", "Deep analysis complete")
            await progress_tracker.update_stage("analyst_complete")

            return

        # ====================================================================
        # ENHANCED APPROVAL REQUEST PROCESSING WITH STRUCTURED DATA
        # ====================================================================

        elif isinstance(message, UserInputRequestedEvent):
            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate approval request")
                return

            agent_logger.info(f"👤 STRUCTURED: Approval request from {source}")
            sender._awaiting_approval = True

            # Determine stage from source
            stage = _determine_approval_stage_from_source(source)

            await sender.send_structured_approval_request(
                stage=stage,
                base_prompt=getattr(message, 'content', 'Approval required'),
                context={"source": source, "timestamp": datetime.now().isoformat()}
            )

            return

        # ====================================================================
        # ENHANCED: DETECT CONTEXT AGENT APPROVAL REQUESTS IN TEXT MESSAGES
        # ====================================================================

        # Enhanced detection for context agent approval requests in regular text messages
        elif (source == "ContextAgent" and 
              isinstance(message, TextMessage) and
              _is_context_approval_request(content)):

            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate context approval request")
                return

            agent_logger.info(f"👤 STRUCTURED: Context agent approval request detected in text message")
            sender._awaiting_approval = True

            # Use structured data instead of regex extraction
            await sender.send_structured_approval_request(
                stage="context",
                base_prompt="Are these historical insights relevant for the current threat analysis?",
                context={
                    "source": source, 
                    "timestamp": datetime.now().isoformat(),
                    "detected_from_text": True
                }
            )

            return

        # ====================================================================
        # ENHANCED: DETECT ANALYST AGENT APPROVAL REQUESTS
        # ====================================================================

        elif (source == "SeniorAnalystSpecialist" and 
              isinstance(message, TextMessage) and
              _is_analyst_approval_request(content)):

            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ STRUCTURED: Ignoring duplicate analyst approval request")
                return

            agent_logger.info(f"👤 STRUCTURED: Analyst agent approval request detected in text message")
            sender._awaiting_approval = True

            # Use structured data instead of regex
            await sender.send_structured_approval_request(
                stage="analyst",
                base_prompt="Do you approve these recommended actions?",
                context={
                    "source": source, 
                    "timestamp": datetime.now().isoformat(),
                    "detected_from_text": True
                }
            )

            return

        # ====================================================================
        # FUNCTION CALL DETECTION (for progress tracking) - UPDATED
        # ====================================================================

        if ('FunctionCall(' in content or
            'report_priority_findings' in content or
            'analyze_historical_incidents' in content):

            agent_type = _determine_agent_type_from_source(source)
            function_name = _extract_function_name(content)

            if agent_type:
                await sender.send_function_detected(
                    agent=agent_type,
                    function_name=function_name,
                    description=f"Function call detected in {source}"
                )

                # Update progress for function calls
                if agent_type == "triage":
                    await progress_tracker.update_stage("triage_active")
                elif agent_type == "context":
                    await progress_tracker.update_stage("context_active")

        # ====================================================================
        # AGENT OUTPUT STREAMING (for non-structured content)
        # ====================================================================

        # Send as agent output stream for relevant agents
        agent_type = _determine_agent_type_from_source(source)
        if agent_type and source not in ['user', 'system']:

            # Filter out system messages but allow actual agent content
            if not _is_system_message(content):
                await sender.send_agent_output_stream(
                    agent=agent_type,
                    content=content,
                    is_final=False
                )

    except Exception as e:
        agent_logger.error(f"❌ STRUCTURED: Critical error processing message: {e}")
        agent_logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        await sender.send_error(f"Message processing error: {str(e)}")
        
# ============================================================================
# SIMPLIFIED HELPER FUNCTIONS (NO MORE REGEX PARSING)
# ============================================================================

def _determine_agent_type_from_source(source: str) -> Optional[str]:
    """Determine agent type from message source"""
    source_lower = source.lower()

    if 'triage' in source_lower:
        return 'triage'
    elif 'context' in source_lower:
        return 'context'
    elif 'analyst' in source_lower or 'senior' in source_lower:
        return 'analyst'

    return None

def _determine_approval_stage_from_source(source: str) -> str:
    """Determine approval stage from message source or content"""
    if 'triage' in source.lower():
        return 'triage'
    elif 'context' in source.lower():
        return 'context'
    elif 'analyst' in source.lower():
        return 'analyst'

    return 'unknown'

def _determine_rejection_stage(content: str) -> str:
    """Determine which stage was rejected from content"""
    content_lower = content.lower()

    if 'triage' in content_lower:
        return 'triage'
    elif 'context' in content_lower:
        return 'context'
    elif 'analyst' in content_lower or 'recommendation' in content_lower:
        return 'analyst'

    return 'unknown'

def _extract_function_name(content: str) -> str:
    """Extract function name from content - UPDATED"""
    if 'report_priority_findings' in content:
        return 'report_priority_findings'
    elif 'analyze_historical_incidents' in content:
        return 'analyze_historical_incidents'
    # REMOVED: 'report_detailed_analysis' detection
    elif 'FunctionCall(' in content:
        # Try to extract function name from FunctionCall
        try:
            start = content.find('FunctionCall(') + len('FunctionCall(')
            end = content.find(',', start)
            if end == -1:
                end = content.find(')', start)
            return content[start:end].strip().strip('"\'')
        except:
            return 'unknown_function'

    return 'unknown_function'

def _is_context_approval_request(content: str) -> bool:
    """Enhanced detection for context agent approval requests"""
    content_lower = content.lower()
    
    # Look for specific phrases that indicate context approval request
    approval_indicators = [
        "context validation required",
        "🔍 context validation required",
        "historical insights relevant",
        "should we proceed with deep security analysis",
        "proceed with deep analysis using this context",
        "are these insights relevant",
        "multistageapprovalagent:",
        "should we proceed",
        "based on my analysis of",
        "are these insights relevant for the current threat analysis"
    ]
    
    # Check if content contains approval indicators
    has_approval_indicator = any(indicator in content_lower for indicator in approval_indicators)
    
    # Also check for question marks and context-related terms
    has_question = "?" in content
    has_context_terms = any(term in content_lower for term in [
        "historical", "context", "incidents", "pattern", "analysis"
    ])
    
    # Check for agent addressing pattern
    has_agent_address = "multistageapprovalagent:" in content_lower
    
    result = has_approval_indicator or has_agent_address or (has_question and has_context_terms)
    
    if result:
        agent_logger.info(f"✅ Context approval request detected in content")
    
    return result

def _is_analyst_approval_request(content: str) -> bool:
    """Enhanced detection for analyst agent approval requests"""
    content_lower = content.lower()
    
    # Look for specific phrases that indicate analyst approval request
    approval_indicators = [
        "multistageapprovalagent:",
        "do you authorize",
        "approve these recommendations",
        "authorize these recommendations",
        "recommended actions",
        "immediate (within",
        "short-term (within",
        "long-term (within",
        "business impact:",
        "based on my analysis, i recommend"
    ]
    
    # Check if content contains approval indicators
    has_approval_indicator = any(indicator in content_lower for indicator in approval_indicators)
    
    # Also check for question marks and analyst-related terms
    has_question = "?" in content
    has_analyst_terms = any(term in content_lower for term in [
        "recommend", "action", "authorize", "immediate", "short-term", "long-term"
    ])
    
    result = has_approval_indicator or (has_question and has_analyst_terms)
    
    if result:
        agent_logger.info(f"✅ Analyst approval request detected in content")
    
    return result

def _is_system_message(content: str) -> bool:
    """Check if content is a system message that should be filtered"""
    system_indicators = [
        'ENHANCED SECURITY LOG ANALYSIS',
        'MULTI-STAGE WORKFLOW',
        'TriageSpecialist: Begin initial triage',
        'Please analyze these OCSF',
    ]

    return any(indicator in content for indicator in system_indicators)

# ============================================================================
# TEAM CREATION AND WORKFLOW FUNCTIONS
# ============================================================================

async def _create_soc_team(
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
    external_termination: ExternalTermination  # Add parameter
):
    """Create SOC team with multiple approval agents and external termination control"""
    model_client = OpenAIChatCompletionClient(model="gpt-4o")

    # Create agents
    triage_agent = TriageAgent(model_client)
    context_agent = ContextAgent(model_client)
    analyst_agent = AnalystAgent(model_client)

    # Create multiple approval agents for different stages
    triage_approval_agent = UserProxyAgent(
        name="TriageApprovalAgent",
        input_func=user_input_func
    )
    
    context_approval_agent = UserProxyAgent(
        name="ContextApprovalAgent", 
        input_func=user_input_func
    )
    
    analyst_approval_agent = UserProxyAgent(
        name="AnalystApprovalAgent",
        input_func=user_input_func
    )

    # FIXED: Proper agent order for multi-stage approval workflow
    team = RoundRobinGroupChat(
        [
            triage_agent,           # 1. Analyze threats
            triage_approval_agent,  # 2. Approve investigation  
            context_agent,          # 3. Research historical context
            context_approval_agent, # 4. Approve context relevance
            analyst_agent,          # 5. Deep analysis
            analyst_approval_agent  # 6. Approve recommendations
        ],
        termination_condition=_create_termination_conditions(external_termination),  # Pass external termination
        custom_message_types=[
            StructuredMessage[PriorityFindings],
            StructuredMessage[SOCAnalysisResult],
            StructuredMessage[ContextResearchResult]
        ],
    )

    agent_logger.info("SOC team created with multi-stage approval workflow and external termination")
    return team, model_client

def _create_termination_conditions(external_termination: ExternalTermination):
    """Create comprehensive termination conditions including external control"""
    
    # Normal completion when analyst finishes with specific phrase
    normal_completion = (
        SourceMatchTermination("SeniorAnalystSpecialist") &
        TextMentionTermination("ANALYSIS_COMPLETE - Senior SOC investigation finished")
    )

    # Rejection termination from any approval agent
    rejection_termination = (
        (SourceMatchTermination("TriageApprovalAgent") |
         SourceMatchTermination("ContextApprovalAgent") |
         SourceMatchTermination("AnalystApprovalAgent")) &
        TextMentionTermination("WORKFLOW_REJECTED")
    )

    # Backup termination conditions
    max_messages = MaxMessageTermination(60)
    token_limit = TokenUsageTermination(max_total_token=90000)
    timeout = TimeoutTermination(timeout_seconds=1200)

    # Combined termination
    termination = (
        external_termination |
        normal_completion |
        rejection_termination |
        max_messages |
        token_limit |
        timeout
    )
    
    return termination

# ============================================================================
# MAIN WORKFLOW FUNCTION WITH STRUCTURED DATA
# ============================================================================

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    Execute SOC analysis workflow with external termination control
    """
    agent_logger.info(f"🚀 STRUCTURED: Starting SOC analysis workflow for session {session_id}")

    # Initialize workflow state for structured data storage
    workflow_state = WorkflowState()
    
    # CREATE EXTERNAL TERMINATION CONTROLLER
    external_termination = ExternalTermination()
    
    # Initialize clean message sender with workflow state
    sender = CleanMessageSender(session_id, workflow_state, message_callback)
    progress_tracker = WorkflowProgressTracker(sender)

    # Initialize results tracking
    final_results = {
        'priority_findings': None,
        'context_research': None,
        'detailed_analysis': None,
        'structured_result': None,
        'was_rejected': False,
        'workflow_complete': False
    }

    # Start workflow progress
    await progress_tracker.update_stage("initializing")
    start_time = datetime.now()

    # Define the user input function with external termination logic
    async def _user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
        """Handle user input requests with clean messaging and termination control"""
        if user_input_callback:
            try:
                user_response = await user_input_callback(prompt, session_id)
                agent_logger.info(f"👤 STRUCTURED: User response for session {session_id}: {user_response}")

                # CLEAR APPROVAL STATE WHEN RESPONSE IS RECEIVED
                sender.clear_approval_state()

                # Process response based on content
                if user_response.lower() in ['approve', 'approved', 'yes', 'continue']:
                    if 'triage' in prompt.lower() or 'priority threat' in prompt.lower():
                        await progress_tracker.update_stage("context_active")
                        return "APPROVED - Triage findings approved. ContextAgent, please search for similar historical incidents."
                    elif 'historical' in prompt.lower() or 'context' in prompt.lower():
                        await progress_tracker.update_stage("analyst_active")
                        return "APPROVED - Historical context validated as relevant. SeniorAnalystSpecialist, please perform deep analysis."
                    elif 'recommend' in prompt.lower() or 'action' in prompt.lower():
                        await progress_tracker.update_stage("finalizing")
                        return "APPROVED - Recommended actions authorized. Analysis workflow is now complete."
                    else:
                        return "APPROVED - Proceeding to next stage of analysis."

                elif user_response.lower() in ['reject', 'rejected', 'no', 'stop', 'cancel']:
                    return "REJECTED - Analysis workflow rejected by human operator. WORKFLOW_REJECTED"

                elif user_response.lower().startswith('custom:'):
                    custom_instructions = user_response[7:].strip()
                    return f"CUSTOM INSTRUCTIONS - {custom_instructions}. Please incorporate these modifications and continue."

                else:
                    return f"USER RESPONSE - {user_response}. Please consider this feedback and continue appropriately."

            except asyncio.TimeoutError:
                agent_logger.warning(f"User input timeout for session {session_id}")
                sender.clear_approval_state()
                return "TIMEOUT - No user response received. Auto-approving to continue analysis."
            except Exception as e:
                agent_logger.error(f"Error getting user input for session {session_id}: {e}")
                sender.clear_approval_state()
                await sender.send_error(f"User input error: {str(e)}")
                return "ERROR - Failed to get user input. Auto-approving to continue analysis."
        else:
            agent_logger.info(f"No user input callback for session {session_id}, auto-approving")
            return "AUTO-APPROVED - No user input mechanism available, automatically continuing with analysis."

    try:
        # Create the SOC team with external termination
        team, model_client = await _create_soc_team(
            user_input_func=_user_input_func,
            external_termination=external_termination
        )

        # Create the enhanced analysis task
        task = f"""ENHANCED SECURITY LOG ANALYSIS WITH CLEAN ARCHITECTURE AND MULTI-STAGE APPROVAL

Please analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

MULTI-STAGE WORKFLOW WITH DEDICATED APPROVAL AGENTS:
1. **TRIAGE STAGE**: TriageSpecialist performs initial threat identification
   - After findings: TriageApprovalAgent handles approval for investigation
   - Wait for user decision on investigation

2. **CONTEXT STAGE**: ContextAgent searches historical incidents (if approved)
   - After research: ContextApprovalAgent handles validation of historical findings
   - Wait for user validation of context relevance

3. **ANALYSIS STAGE**: SeniorAnalystSpecialist performs deep analysis (if context approved)
   - After recommendations: AnalystApprovalAgent handles authorization for proposed actions
   - Wait for user authorization of recommended actions

4. **COMPLETION**: Workflow automatically terminates after analyst approval

APPROVAL POINTS:
- Each stage has dedicated approval agent
- Provide clear, specific information for decision-making
- Wait for explicit approval before continuing to next agent
- Handle custom instructions and modifications
- Workflow terminates automatically after final analyst approval

TriageSpecialist: Begin initial triage analysis. After completing your analysis and providing structured findings, wait for TriageApprovalAgent to handle the approval process."""

        agent_logger.info(f"Starting multi-stage approval team execution for session {session_id}")

        # Use run_stream for real-time message processing
        stream = team.run_stream(task=task, cancellation_token=CancellationToken())

        # Process messages in real-time as they arrive
        async for message in stream:
            await _process_clean_streaming_message(message, sender, progress_tracker, final_results, workflow_state, external_termination)

            # Break early if workflow is complete OR external termination is set
            if final_results.get('workflow_complete') or external_termination.terminated:
                if external_termination.terminated:
                    agent_logger.info(f"🎯 STRUCTURED: Workflow terminated externally for session {session_id}")
                else:
                    agent_logger.info(f"🎉 STRUCTURED: Workflow completed early for session {session_id}")
                break

        await model_client.close()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Send final completion update if not already sent
        if not final_results.get('workflow_complete'):
            success = not final_results.get('was_rejected', False)

            await sender.send_analysis_complete(
                success=success,
                results_summary={
                    "has_priority_findings": final_results.get('priority_findings') is not None,
                    "has_context_data": final_results.get('context_research') is not None,
                    "has_detailed_analysis": final_results.get('detailed_analysis') is not None,
                    "was_rejected": final_results.get('was_rejected', False),
                    "terminated_externally": external_termination.terminated
                },
                duration_seconds=duration
            )

        agent_logger.info(f"Structured data SOC analysis workflow completed for session {session_id}")
        agent_logger.info(f"Final status - Duration: {duration:.1f}s, External termination: {external_termination.terminated}")

        return not final_results.get('was_rejected', False)

    except Exception as e:
        agent_logger.error(f"Structured data SOC analysis workflow error for session {session_id}: {e}")
        agent_logger.error(f"Full traceback: {traceback.format_exc()}")

        # Send error via clean messaging
        await sender.send_error(f"Analysis workflow error: {str(e)}")

        return False
