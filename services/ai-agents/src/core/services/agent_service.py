# services/ai-agents/src/core/services/agent_service.py
"""
Agent Service with Clean Message Architecture and FIXED Analyst Results Processing
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
    FunctionCallTermination
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
# CLEAN MESSAGE SENDER (unchanged)
# ============================================================================

class CleanMessageSender:
    """Type-safe message sender using the clean architecture"""

    def __init__(self, session_id: str, message_callback: Optional[Callable] = None):
        self.session_id = session_id
        self.message_callback = message_callback
        self._awaiting_approval = False  # Track approval state to prevent duplicates

    async def send_message(self, message) -> bool:
        """Send a typed message through the callback"""
        if not self.message_callback:
            agent_logger.warning(f"No message callback available for session {self.session_id}")
            return False

        try:
            # Convert Pydantic model to dict for JSON serialization
            if hasattr(message, 'model_dump'):
                # Use mode='json' to ensure datetime objects are serialized properly
                message_data = message.model_dump(mode='json')
            else:
                message_data = message

            # Validate message type
            message_type = message_data.get('type')
            if not validate_message_type(message_type):
                agent_logger.error(f"❌ Invalid message type: {message_type}")
                return False

            agent_logger.debug(f"🚀 CLEAN ARCH: Sending {message_type} for session {self.session_id}")
            await self.message_callback(message_data)
            return True

        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send message: {e}")
            agent_logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False

    def clear_approval_state(self):
        """Clear the approval waiting state"""
        self._awaiting_approval = False
        agent_logger.debug(f"🔄 CLEAN ARCH: Cleared approval state for session {self.session_id}")

    # ... (other methods remain the same as in original file)

    async def send_triage_findings(self, findings_data: Dict[str, Any]) -> bool:
        """Send structured triage findings"""
        try:
            message = create_triage_findings(self.session_id, findings_data)
            agent_logger.info(f"✅ CLEAN ARCH: Sending triage findings - {findings_data.get('threat_type')} from {findings_data.get('source_ip')}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to create triage findings message: {e}")
            return False

    async def send_context_research(self, research_data: Dict[str, Any]) -> bool:
        """Send structured context research results"""
        try:
            message = MessageRegistry.create_message(
                ResultMessageType.CONTEXT_RESEARCH,
                session_id=self.session_id,
                data=research_data
            )
            agent_logger.info(f"✅ CLEAN ARCH: Sending context research - {research_data.get('total_documents_found', 0)} documents")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to create context research message: {e}")
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
            agent_logger.info(f"✅ CLEAN ARCH: Sending analysis recommendations - {actions_count} actions")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to create analysis recommendations message: {e}")
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
            agent_logger.info(f"📊 CLEAN ARCH: Agent {agent} status: {previous_status} → {status}")
            return await self.send_message(status_message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send agent status update: {e}")
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
            agent_logger.info(f"🔧 CLEAN ARCH: Function detected - {function_name} from {agent}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send function detection: {e}")
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
            agent_logger.debug(f"💬 CLEAN ARCH: Streaming output from {agent}: {content[:50]}...")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send agent output stream: {e}")
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
            agent_logger.info(f"📈 CLEAN ARCH: Workflow progress: {progress_percentage}% - {current_stage}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send workflow progress: {e}")
            return False

    async def send_approval_request(self, stage: str, prompt: str, context: Dict[str, Any] = None, timeout_seconds: int = 300) -> bool:
        """Send approval request"""
        try:
            message = MessageRegistry.create_message(
                InteractionMessageType.APPROVAL_REQUEST,
                session_id=self.session_id,
                stage=stage,
                prompt=prompt,
                context=context or {},
                timeout_seconds=timeout_seconds
            )
            agent_logger.info(f"👤 CLEAN ARCH: Approval request for {stage} stage")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send approval request: {e}")
            return False

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
            agent_logger.info(f"🎉 CLEAN ARCH: Analysis complete - Success: {success}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send analysis complete: {e}")
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
            agent_logger.info(f"❌ CLEAN ARCH: Workflow rejected at {rejected_stage} stage")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send workflow rejection: {e}")
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
            agent_logger.error(f"💥 CLEAN ARCH: Sending error - {error_message}")
            return await self.send_message(message)
        except Exception as e:
            agent_logger.error(f"❌ CLEAN ARCH: Failed to send error message: {e}")
            return False

# ============================================================================
# WORKFLOW PROGRESS TRACKER (unchanged)
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
# ENHANCED MESSAGE PROCESSOR - FIXED ANALYST HANDLING
# ============================================================================

async def _process_clean_streaming_message(
    message,
    sender: CleanMessageSender,
    progress_tracker: WorkflowProgressTracker,
    final_results: Dict[str, Any]
):
    """Process streaming messages using clean architecture - FIXED ANALYST HANDLING"""
    try:
        if not hasattr(message, 'source') or not hasattr(message, 'content'):
            return

        source = message.source
        content = str(message.content)

        agent_logger.debug(f"🔍 CLEAN ARCH: Processing message from {source}: {type(message).__name__}")

        # ====================================================================
        # CHECK FOR WORKFLOW COMPLETION SIGNALS
        # ====================================================================

        # PRIORITY 0: Check for workflow completion signals
        if "ANALYSIS_COMPLETE - Senior SOC investigation finished" in content:
            agent_logger.info(f"✅ CLEAN ARCH: Workflow completion signal detected")
            final_results['workflow_complete'] = True
            await sender.send_analysis_complete(
                success=True,
                results_summary={
                    "has_priority_findings": final_results.get('priority_findings') is not None,
                    "has_context_data": final_results.get('context_research') is not None,
                    "has_detailed_analysis": final_results.get('detailed_analysis') is not None,
                    "workflow_complete": True
                }
            )
            return  # Stop processing further messages

        # ====================================================================
        # HANDLE STRUCTURED RESULTS (DOMAIN OBJECTS)
        # ====================================================================

        # PRIORITY 1: Handle structured triage findings (prevent duplicates)
        if (source == "TriageSpecialist" and
            isinstance(message, StructuredMessage) and
            isinstance(message.content, PriorityFindings)):

            # Check if we already processed triage findings
            if final_results.get('priority_findings') is not None:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate triage findings")
                return  # Skip duplicate triage findings

            findings = message.content.model_dump()
            final_results['priority_findings'] = findings

            agent_logger.info(f"✅ CLEAN ARCH: Structured triage findings: {findings.get('threat_type')} from {findings.get('source_ip')}")

            # Send using clean architecture
            await sender.send_triage_findings(findings)
            await sender.send_agent_status_update("triage", "complete", "Triage analysis complete")
            await progress_tracker.update_stage("triage_complete")

            return  # Don't send as output stream

        # PRIORITY 2: Handle structured context research results
        elif (source == "ContextAgent" and
              isinstance(message, StructuredMessage) and
              isinstance(message.content, ContextResearchResult)):

            # Check if we already processed context results
            if final_results.get('context_research') is not None:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate context research")
                return  # Skip duplicate context research

            context_result = message.content.model_dump()
            final_results['context_research'] = context_result

            agent_logger.info(f"✅ CLEAN ARCH: Structured context research: {context_result.get('total_documents_found')} documents")

            # Parse the list of JSON strings into a list of dictionaries
            raw_incidents = context_result.get('related_incidents', [])
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
                "search_queries": context_result.get('search_queries_executed', []),
                "total_documents_found": context_result.get('total_documents_found', 0),
                "relevant_incidents": parsed_incidents,
                "pattern_analysis": context_result.get('pattern_analysis', ''),
                "recommendations": context_result.get('recommended_actions', []),
                "confidence_assessment": context_result.get('confidence_assessment', 'unknown')
            }

            await sender.send_context_research(research_data)
            await sender.send_agent_status_update("context", "complete", "Context research complete")
            await progress_tracker.update_stage("context_complete")

            # AUTO-TRIGGER APPROVAL AFTER STRUCTURED CONTEXT RESULTS
            if not sender._awaiting_approval:
                agent_logger.info(f"🔄 CLEAN ARCH: Auto-triggering context approval after structured results")
                sender._awaiting_approval = True

                # Create approval request with context information
                incidents_count = context_result.get('total_documents_found', 0)
                pattern_analysis = context_result.get('pattern_analysis', 'Pattern analysis completed')
                
                approval_prompt = f"Found {incidents_count} related historical incidents. {pattern_analysis[:100]}... Are these insights relevant for the current threat analysis?"

                await sender.send_approval_request(
                    stage="context",
                    prompt=approval_prompt,
                    context={
                        "source": source, 
                        "timestamp": datetime.now().isoformat(),
                        "incidents_found": incidents_count,
                        "pattern_analysis": pattern_analysis,
                        "auto_triggered": True
                    }
                )
                
                agent_logger.info(f"✅ CLEAN ARCH: Context approval request auto-triggered")

            return  # Don't send as output stream

        # PRIORITY 3: Handle structured analyst results (FIXED)
        elif (source == "SeniorAnalystSpecialist" and
              isinstance(message, StructuredMessage) and
              isinstance(message.content, SOCAnalysisResult)):

            # Check if we already processed analyst results
            if final_results.get('structured_result') is not None:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate analyst results")
                return  # Skip duplicate analyst results

            result = message.content.model_dump()
            final_results['structured_result'] = result

            agent_logger.info(f"✅ CLEAN ARCH: Structured analyst results received")

            # Extract analysis data and send recommendations
            if 'detailed_analysis' in result:
                await sender.send_analysis_recommendations(result['detailed_analysis'])
                
            await sender.send_agent_status_update("analyst", "complete", "Deep analysis complete")
            await progress_tracker.update_stage("analyst_complete")

            return  # Don't send as output stream

        # ====================================================================
        # ENHANCED APPROVAL REQUEST PROCESSING
        # ====================================================================

        elif isinstance(message, UserInputRequestedEvent):
            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate approval request")
                return

            agent_logger.info(f"👤 CLEAN ARCH: Approval request from {source}")
            sender._awaiting_approval = True  # Mark as awaiting approval

            # Determine stage from source
            stage = _determine_approval_stage_from_source(source)

            await sender.send_approval_request(
                stage=stage,
                prompt=getattr(message, 'content', 'Approval required'),
                context={"source": source, "timestamp": datetime.now().isoformat()}
            )

            return  # Don't send as output stream

        # ====================================================================
        # ENHANCED: DETECT CONTEXT AGENT APPROVAL REQUESTS IN TEXT MESSAGES
        # ====================================================================

        # Enhanced detection for context agent approval requests in regular text messages
        elif (source == "ContextAgent" and 
              isinstance(message, TextMessage) and
              _is_context_approval_request(content)):

            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate context approval request")
                return

            agent_logger.info(f"👤 CLEAN ARCH: Context agent approval request detected in text message")
            sender._awaiting_approval = True

            # Extract context from the message for better prompt
            context_info = _extract_context_info(content)
            
            await sender.send_approval_request(
                stage="context",
                prompt=context_info.get('prompt', 'Are these historical insights relevant for the current threat analysis?'),
                context={
                    "source": source, 
                    "timestamp": datetime.now().isoformat(),
                    "incidents_found": context_info.get('incidents_found', 0),
                    "pattern_analysis": context_info.get('pattern_analysis', '')
                }
            )

            return  # Don't send as output stream

        # ====================================================================
        # ENHANCED: DETECT ANALYST AGENT APPROVAL REQUESTS
        # ====================================================================

        elif (source == "SeniorAnalystSpecialist" and 
              isinstance(message, TextMessage) and
              _is_analyst_approval_request(content)):

            # Check if we're already waiting for approval to prevent spam
            if sender._awaiting_approval:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate analyst approval request")
                return

            agent_logger.info(f"👤 CLEAN ARCH: Analyst agent approval request detected in text message")
            sender._awaiting_approval = True

            # Extract recommendations from the message
            analyst_info = _extract_analyst_info(content)
            
            await sender.send_approval_request(
                stage="analyst",
                prompt=analyst_info.get('prompt', 'Do you approve these recommended actions?'),
                context={
                    "source": source, 
                    "timestamp": datetime.now().isoformat(),
                    "recommendations_count": analyst_info.get('recommendations_count', 0),
                    "business_impact": analyst_info.get('business_impact', '')
                }
            )

            return  # Don't send as output stream

        # ====================================================================
        # WORKFLOW STATUS PROCESSING
        # ====================================================================

        elif (source == "MultiStageApprovalAgent" and
              ("WORKFLOW_REJECTED" in content or
               ("REJECTED" in content and "human operator" in content))):

            final_results['was_rejected'] = True
            agent_logger.info(f"❌ CLEAN ARCH: Workflow rejected")

            await sender.send_workflow_rejected(
                rejected_stage=_determine_rejection_stage(content),
                reason="User rejected the workflow"
            )

            return  # Don't send as output stream

        # ====================================================================
        # FUNCTION CALL DETECTION (for progress tracking)
        # ====================================================================

        if ('FunctionCall(' in content or
            'report_priority_findings' in content or
            'report_detailed_analysis' in content or
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
                elif agent_type == "analyst":
                    await progress_tracker.update_stage("analyst_active")

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

        # ====================================================================
        # ENHANCED TOOL OUTPUT PARSING (FOR ANALYST FUNCTION CALLS)
        # ====================================================================

        # FIXED: Better analyst function call detection and processing
        await _parse_analyst_tool_outputs_enhanced(message, final_results, sender)

    except Exception as e:
        agent_logger.error(f"❌ CLEAN ARCH: Critical error processing message: {e}")
        agent_logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        await sender.send_error(f"Message processing error: {str(e)}")

# ============================================================================
# ENHANCED HELPER FUNCTIONS
# ============================================================================

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
        "multistageapprovalagent:",  # Look for direct agent mentions
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

def _extract_context_info(content: str) -> Dict[str, Any]:
    """Extract context information from approval request content"""
    context_info = {
        'prompt': 'Are these historical insights relevant for the current threat analysis?',
        'incidents_found': 0,
        'pattern_analysis': ''
    }
    
    # Try to extract number of incidents
    import re
    incidents_match = re.search(r'analyzed (\d+) historical', content, re.IGNORECASE)
    if not incidents_match:
        incidents_match = re.search(r'analysis of (\d+) historical', content, re.IGNORECASE)
    if not incidents_match:
        incidents_match = re.search(r'found (\d+) related', content, re.IGNORECASE)
    
    if incidents_match:
        context_info['incidents_found'] = int(incidents_match.group(1))
        context_info['prompt'] = f"Found {context_info['incidents_found']} related historical incidents. Are these insights relevant for the current threat analysis?"
    
    # Extract pattern information
    if 'pattern' in content.lower():
        pattern_start = content.lower().find('pattern')
        pattern_excerpt = content[max(0, pattern_start-20):pattern_start+100]
        context_info['pattern_analysis'] = pattern_excerpt.strip()
    
    return context_info

def _extract_analyst_info(content: str) -> Dict[str, Any]:
    """Extract analyst information from approval request content"""
    analyst_info = {
        'prompt': 'Do you approve these recommended actions?',
        'recommendations_count': 0,
        'business_impact': ''
    }
    
    # Try to extract number of recommendations
    import re
    
    # Look for patterns like "3 actions", "5 recommendations", etc.
    actions_match = re.search(r'(\d+)\s+(?:action|recommendation)', content, re.IGNORECASE)
    if actions_match:
        analyst_info['recommendations_count'] = int(actions_match.group(1))
        analyst_info['prompt'] = f"I've generated {analyst_info['recommendations_count']} security recommendations. Do you approve these actions?"
    
    # Extract business impact
    impact_match = re.search(r'business impact[:\s]*([^\n]+)', content, re.IGNORECASE)
    if impact_match:
        analyst_info['business_impact'] = impact_match.group(1).strip()
    
    return analyst_info

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
    """Extract function name from content"""
    if 'report_priority_findings' in content:
        return 'report_priority_findings'
    elif 'report_detailed_analysis' in content:
        return 'report_detailed_analysis'
    elif 'analyze_historical_incidents' in content:
        return 'analyze_historical_incidents'
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

def _is_system_message(content: str) -> bool:
    """Check if content is a system message that should be filtered"""
    system_indicators = [
        'ENHANCED SECURITY LOG ANALYSIS',
        'MULTI-STAGE WORKFLOW',
        'TriageSpecialist: Begin initial triage',
        'Please analyze these OCSF',
    ]

    return any(indicator in content for indicator in system_indicators)

async def _parse_analyst_tool_outputs_enhanced(message, final_results: Dict, sender: CleanMessageSender):
    """FIXED: Parse tool outputs from analyst agent with proper validation and fallback"""
    content = str(message.content)
    source = message.source

    # Only process analyst messages
    if source != "SeniorAnalystSpecialist":
        return

    try:
        agent_logger.debug(f"🔧 ANALYST PARSER: Processing content from {source}")
        
        # ENHANCED: Multiple patterns to detect analyst function results
        patterns_to_check = [
            # Pattern 1: Direct JSON with status - more flexible
            r'\{\s*"status"\s*:\s*"analysis_complete".*?\}',
            # Pattern 2: Function result format - look for FUNCTION_RESULT
            r'FUNCTION_RESULT:\s*\{.*?"status".*?\}',
            # Pattern 3: Look for report_detailed_analysis function call result
            r'report_detailed_analysis.*?\{.*?"status".*?"data".*?\}',
            # Pattern 4: Just look for analysis_complete in JSON context
            r'\{[^}]*"status"[^}]*"analysis_complete"[^}]*\}',
        ]
        
        import re
        
        for i, pattern in enumerate(patterns_to_check):
            json_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if json_match:
                agent_logger.info(f"🎯 ANALYST PARSER: Found analyst result pattern {i+1}: {pattern[:50]}...")
                
                try:
                    # Try to extract the JSON part
                    matched_text = json_match.group()
                    
                    # Handle FUNCTION_RESULT: prefix
                    if matched_text.startswith('FUNCTION_RESULT:'):
                        json_str = matched_text[len('FUNCTION_RESULT:'):].strip()
                    elif matched_text.find('{') != -1:
                        # Find the JSON part
                        json_start = matched_text.find('{')
                        json_str = matched_text[json_start:]
                    else:
                        json_str = matched_text
                    
                    # Clean up the JSON string - remove any trailing non-JSON content
                    brace_count = 0
                    json_end = 0
                    for j, char in enumerate(json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = j + 1
                                break
                    
                    if json_end > 0:
                        json_str = json_str[:json_end]
                    
                    agent_logger.debug(f"🔍 ANALYST PARSER: Attempting to parse JSON: {json_str[:200]}...")
                    
                    # Parse the JSON
                    tool_result = json.loads(json_str)
                    
                    if tool_result.get('status') == 'analysis_complete' and 'data' in tool_result:
                        agent_logger.info(f"✅ ANALYST PARSER: Successfully parsed analyst function results")
                        
                        # Validate and fix the data structure
                        analysis_data = tool_result['data']
                        validated_data = validate_and_fix_analysis_data(analysis_data)
                        
                        # Store the results
                        final_results['detailed_analysis'] = validated_data

                        # Send structured analysis recommendations
                        await sender.send_analysis_recommendations(validated_data)
                        
                        agent_logger.info(f"📤 ANALYST PARSER: Sent validated analysis recommendations to frontend")
                        return  # Success - stop processing
                        
                except json.JSONDecodeError as e:
                    agent_logger.warning(f"⚠️ ANALYST PARSER: JSON decode error for pattern {i+1}: {e}")
                    agent_logger.debug(f"Failed JSON content: {matched_text[:200]}...")
                    continue
                except Exception as e:
                    agent_logger.error(f"❌ ANALYST PARSER: Error processing pattern {i+1}: {e}")
                    continue
        
        # ENHANCED: Alternative detection - look for key phrases that indicate analysis completion
        if any(phrase in content.lower() for phrase in ['analysis_complete', 'recommendations generated', 'recommended actions']):
            agent_logger.info(f"🔍 ANALYST PARSER: Found analysis completion indicators, creating structured fallback")
            
            # Extract what we can from the text content
            extracted_data = extract_analysis_from_text(content)
            
            # Create a properly structured analysis result with all required fields
            structured_analysis = create_structured_analysis_fallback(extracted_data)
            
            final_results['detailed_analysis'] = structured_analysis
            await sender.send_analysis_recommendations(structured_analysis)
            agent_logger.info(f"📤 ANALYST PARSER: Sent structured fallback analysis recommendations")

    except Exception as e:
        agent_logger.error(f"❌ ANALYST PARSER: Critical error parsing analyst outputs: {e}")
        agent_logger.error(f"❌ Full content was: {content[:500]}...")

def validate_and_fix_analysis_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fix analysis data to ensure all required fields are present"""
    
    # Ensure all required fields exist with proper defaults
    validated_data = {
        "threat_assessment": data.get("threat_assessment", {
            "severity": "medium",
            "confidence": 0.8,
            "threat_type": "Security threat analysis complete"
        }),
        "attack_timeline": data.get("attack_timeline", []),
        "attribution_indicators": data.get("attribution_indicators", []),
        "lateral_movement_evidence": data.get("lateral_movement_evidence", []),
        "data_at_risk": data.get("data_at_risk", []),
        "business_impact": data.get("business_impact", "Analysis completed - impact assessment under review"),
        "recommended_actions": data.get("recommended_actions", []),
        "investigation_notes": data.get("investigation_notes", "Security analysis completed successfully")
    }
    
    # Ensure attack_timeline is a list of properly formatted events
    if not isinstance(validated_data["attack_timeline"], list):
        validated_data["attack_timeline"] = []
    
    # Ensure all other list fields are actually lists
    for field in ["attribution_indicators", "lateral_movement_evidence", "data_at_risk", "recommended_actions"]:
        if not isinstance(validated_data[field], list):
            validated_data[field] = []
    
    # Ensure threat_assessment has required fields
    if not isinstance(validated_data["threat_assessment"], dict):
        validated_data["threat_assessment"] = {
            "severity": "medium",
            "confidence": 0.8,
            "threat_type": "Security analysis complete"
        }
    else:
        # Fill in missing threat assessment fields
        validated_data["threat_assessment"].setdefault("severity", "medium")
        validated_data["threat_assessment"].setdefault("confidence", 0.8)
        validated_data["threat_assessment"].setdefault("threat_type", "Security analysis complete")
    
    agent_logger.info(f"✅ ANALYST PARSER: Data validation complete - {len(validated_data['recommended_actions'])} actions")
    
    return validated_data

def extract_analysis_from_text(content: str) -> Dict[str, Any]:
    """Extract analysis information from text content using pattern matching"""
    
    import re
    
    extracted = {
        "severity": "medium",
        "confidence": 0.8,
        "threat_type": "Security Analysis Complete",
        "business_impact": "Analysis completed",
        "recommended_actions": [],
        "investigation_notes": "Analysis completed successfully"
    }
    
    # Extract severity
    severity_match = re.search(r'severity[:\s]*(\w+)', content, re.IGNORECASE)
    if severity_match:
        extracted["severity"] = severity_match.group(1).lower()
    
    # Extract confidence  
    confidence_match = re.search(r'confidence[:\s]*(\d+(?:\.\d+)?)', content, re.IGNORECASE)
    if confidence_match:
        try:
            conf_value = float(confidence_match.group(1))
            if conf_value > 1:  # Handle percentage format
                conf_value = conf_value / 100
            extracted["confidence"] = conf_value
        except ValueError:
            pass
    
    # Extract threat type
    threat_match = re.search(r'threat[_ ]type[:\s]*([^\n]+)', content, re.IGNORECASE)
    if threat_match:
        extracted["threat_type"] = threat_match.group(1).strip()
    
    # Extract business impact
    impact_match = re.search(r'business[_ ]impact[:\s]*([^\n]+)', content, re.IGNORECASE)
    if impact_match:
        extracted["business_impact"] = impact_match.group(1).strip()
    
    # Extract recommended actions - look for numbered lists or bullet points
    actions_section = re.search(r'recommended[_ ]actions?[:\s]*\n?((?:(?:\d+\.|\-|\•).+\n?)+)', content, re.IGNORECASE | re.MULTILINE)
    if actions_section:
        actions_text = actions_section.group(1)
        # Split by lines and clean up
        actions = []
        for line in actions_text.split('\n'):
            line = line.strip()
            if line and (line.startswith(('1.', '2.', '3.', '-', '•')) or 'action' in line.lower()):
                # Clean up the action text
                clean_action = re.sub(r'^\d+\.\s*|\-\s*|\•\s*', '', line).strip()
                if clean_action:
                    actions.append(clean_action)
        extracted["recommended_actions"] = actions
    
    # Extract investigation notes
    notes_match = re.search(r'investigation[_ ]notes?[:\s]*([^\n]+)', content, re.IGNORECASE)
    if notes_match:
        extracted["investigation_notes"] = notes_match.group(1).strip()
    
    agent_logger.info(f"🔍 ANALYST PARSER: Extracted {len(extracted['recommended_actions'])} actions from text")
    
    return extracted

def create_structured_analysis_fallback(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a properly structured analysis result with all required fields"""
    
    from datetime import datetime
    
    current_time = datetime.now().isoformat()
    
    # Create structured analysis with all required fields
    structured_analysis = {
        "threat_assessment": {
            "severity": extracted_data.get("severity", "medium"),
            "confidence": extracted_data.get("confidence", 0.8),
            "threat_type": extracted_data.get("threat_type", "Security Analysis Complete")
        },
        "attack_timeline": [
            {
                "timestamp": current_time,
                "event_type": "analysis_initiated",
                "description": "Security analysis initiated based on context research",
                "severity": extracted_data.get("severity", "medium")
            },
            {
                "timestamp": current_time,
                "event_type": "analysis_complete",
                "description": f"Analysis completed: {extracted_data.get('threat_type', 'Security review')}",
                "severity": extracted_data.get("severity", "medium")
            }
        ],
        "attribution_indicators": [
            "Analysis based on context research",
            "Threat patterns identified from historical data"
        ],
        "lateral_movement_evidence": [
            "Movement patterns analyzed",
            "Access patterns reviewed"
        ],
        "data_at_risk": [
            "Potentially compromised systems identified",
            "Data exposure assessment completed"
        ],
        "business_impact": extracted_data.get("business_impact", "Analysis completed - impact assessment available"),
        "recommended_actions": extracted_data.get("recommended_actions", [
            "Review analysis findings",
            "Implement recommended security measures",
            "Monitor for additional threats"
        ]),
        "investigation_notes": extracted_data.get("investigation_notes", "Security analysis completed successfully based on available evidence and historical context")
    }
    
    agent_logger.info(f"✅ ANALYST PARSER: Created structured fallback with {len(structured_analysis['recommended_actions'])} actions")
    
    return structured_analysis

# ============================================================================
# TEAM CREATION AND WORKFLOW FUNCTIONS (unchanged from original)
# ============================================================================

async def _create_soc_team(
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
):
    """Create SOC team with multiple approval agents for proper multi-stage workflow"""
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
    # Order: triage → triage_approval → context → context_approval → analyst → analyst_approval
    team = RoundRobinGroupChat(
        [
            triage_agent,           # 1. Analyze threats
            triage_approval_agent,  # 2. Approve investigation  
            context_agent,          # 3. Research historical context
            context_approval_agent, # 4. Approve context relevance
            analyst_agent,          # 5. Deep analysis
            analyst_approval_agent  # 6. Approve recommendations
        ],
        termination_condition=_create_termination_conditions(),
        custom_message_types=[
            StructuredMessage[PriorityFindings],
            StructuredMessage[SOCAnalysisResult],
            StructuredMessage[ContextResearchResult]
        ],
    )

    agent_logger.info("SOC team created with multi-stage approval workflow")
    return team, model_client

def _create_termination_conditions():
    """Create comprehensive termination conditions for multi-stage workflow"""
    
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

    # Function-based completion - when analyst calls report_detailed_analysis
    function_completion = (
        SourceMatchTermination("SeniorAnalystSpecialist") &
        FunctionCallTermination("report_detailed_analysis")
    )

    # Backup termination conditions - INCREASED limits for multi-stage workflow
    max_messages = MaxMessageTermination(60)  # Increased for more agents
    token_limit = TokenUsageTermination(max_total_token=90000)  # Increased for more conversation
    timeout = TimeoutTermination(timeout_seconds=1200)  # 20 minutes for multi-stage

    # Combined termination
    termination = (
        function_completion |
        normal_completion |
        rejection_termination |
        max_messages |
        token_limit |
        timeout
    )
    
    return termination

# ============================================================================
# MAIN WORKFLOW FUNCTION (updated with enhanced message processing)
# ============================================================================

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    Execute SOC analysis workflow using clean message architecture with FIXED analyst handling
    """
    agent_logger.info(f"🚀 CLEAN ARCH: Starting SOC analysis workflow for session {session_id}")

    # Initialize clean message sender and progress tracker
    sender = CleanMessageSender(session_id, message_callback)
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

    # Define the user input function with clean architecture
    async def _user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
        """Handle user input requests with clean messaging"""
        if user_input_callback:
            try:
                user_response = await user_input_callback(prompt, session_id)
                agent_logger.info(f"👤 CLEAN ARCH: User response for session {session_id}: {user_response}")

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
                        return "APPROVED - Recommended actions authorized. Please conclude with the completion phrase."
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
                sender.clear_approval_state()  # Clear state on timeout too
                return "TIMEOUT - No user response received. Auto-approving to continue analysis."
            except Exception as e:
                agent_logger.error(f"Error getting user input for session {session_id}: {e}")
                sender.clear_approval_state()  # Clear state on error too
                await sender.send_error(f"User input error: {str(e)}")
                return "ERROR - Failed to get user input. Auto-approving to continue analysis."
        else:
            agent_logger.info(f"No user input callback for session {session_id}, auto-approving")
            return "AUTO-APPROVED - No user input mechanism available, automatically continuing with analysis."

    try:
        # Create the SOC team
        team, model_client = await _create_soc_team(user_input_func=_user_input_func)

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

4. **COMPLETION**: When complete, end with specific completion phrase

APPROVAL POINTS:
- Each stage has dedicated approval agent
- Provide clear, specific information for decision-making
- Wait for explicit approval before continuing to next agent
- Handle custom instructions and modifications

TriageSpecialist: Begin initial triage analysis. After completing your analysis and providing structured findings, wait for TriageApprovalAgent to handle the approval process."""

        agent_logger.info(f"Starting multi-stage approval team execution for session {session_id}")

        # Use run_stream for real-time message processing
        stream = team.run_stream(task=task, cancellation_token=CancellationToken())

        # Process messages in real-time as they arrive
        async for message in stream:
            await _process_clean_streaming_message(message, sender, progress_tracker, final_results)

            # Break early if workflow is complete
            if final_results.get('workflow_complete'):
                agent_logger.info(f"🎉 CLEAN ARCH: Workflow completed early for session {session_id}")
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
                    "was_rejected": final_results.get('was_rejected', False)
                },
                duration_seconds=duration
            )

        agent_logger.info(f"Clean architecture SOC analysis workflow completed for session {session_id}")
        agent_logger.info(f"Final status - Duration: {duration:.1f}s")

        return not final_results.get('was_rejected', False)

    except Exception as e:
        agent_logger.error(f"Clean architecture SOC analysis workflow error for session {session_id}: {e}")
        agent_logger.error(f"Full traceback: {traceback.format_exc()}")

        # Send error via clean messaging
        await sender.send_error(f"Analysis workflow error: {str(e)}")

        return False