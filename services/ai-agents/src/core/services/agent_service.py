# services/ai-agents/src/core/services/agent_service.py - COMPLETE FIXED VERSION
"""
Agent Service with Clean Message Architecture
Uses the new message registry for type-safe, structured messaging
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
from core.models.analysis import SOCAnalysisResult, PriorityFindings
from utils.serialization import sanitize_chroma_results

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
# CLEAN MESSAGE SENDER
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
    
    # ========================================================================
    # STRUCTURED RESULTS
    # ========================================================================
    
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
    
    # ========================================================================
    # STATUS UPDATES
    # ========================================================================
    
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
    
    # ========================================================================
    # INTERACTION MESSAGES
    # ========================================================================
    
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
    
    # ========================================================================
    # CONTROL MESSAGES  
    # ========================================================================
    
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
# ENHANCED MESSAGE PROCESSOR
# ============================================================================

async def _process_clean_streaming_message(
    message, 
    sender: CleanMessageSender,
    progress_tracker: WorkflowProgressTracker,
    final_results: Dict[str, Any]
):
    """Process streaming messages using clean architecture"""
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
                    "has_context_data": bool(final_results.get('chroma_context')),
                    "has_detailed_analysis": final_results.get('detailed_analysis') is not None,
                    "workflow_complete": True
                }
            )
            return  # Stop processing further messages
        
        # ====================================================================
        # PREVENT DUPLICATE STRUCTURED RESULTS
        # ====================================================================
        
        # PRIORITY 1: Handle structured triage findings (but prevent duplicates)
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
        
        # PRIORITY 2: Handle structured analyst results (but prevent duplicates)
        elif (source == "SeniorAnalyst" and 
              isinstance(message, StructuredMessage) and
              isinstance(message.content, SOCAnalysisResult)):
            
            # Check if we already processed analyst results
            if final_results.get('structured_result') is not None:
                agent_logger.warning(f"⚠️ CLEAN ARCH: Ignoring duplicate analyst results")
                return  # Skip duplicate analyst results
            
            result = message.content.model_dump()
            final_results['structured_result'] = result
            
            agent_logger.info(f"✅ CLEAN ARCH: Structured analyst results received")
            
            # Extract analysis data
            if 'detailed_analysis' in result:
                await sender.send_analysis_recommendations(result['detailed_analysis'])
            
            await sender.send_agent_status_update("analyst", "complete", "Deep analysis complete")
            await progress_tracker.update_stage("analyst_complete")
            
            return  # Don't send as output stream
        
        # ====================================================================
        # APPROVAL REQUEST PROCESSING (prevent duplicates)
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
        # FUNCTION CALL DETECTION
        # ====================================================================
        
        if ('FunctionCall(' in content or 
            'report_priority_findings' in content or 
            'report_detailed_analysis' in content or
            'search_historical_incidents' in content):
            
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
        # AGENT OUTPUT STREAMING
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
        # TOOL OUTPUT PARSING
        # ====================================================================
        
        await _parse_clean_tool_outputs(message, final_results, sender)
                
    except Exception as e:
        agent_logger.error(f"❌ CLEAN ARCH: Critical error processing message: {e}")
        agent_logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        await sender.send_error(f"Message processing error: {str(e)}")

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
    elif 'search_historical_incidents' in content:
        return 'search_historical_incidents'
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

async def _parse_clean_tool_outputs(message, final_results: Dict, sender: CleanMessageSender):
    """Parse and handle tool outputs using clean architecture"""
    content = str(message.content)
    
    try:
        # Extract context search results
        if "status" in content and "search_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'search_complete' and 'results' in tool_result:
                    sanitized_results = sanitize_chroma_results(tool_result['results'])
                    final_results['chroma_context'] = sanitized_results
                    
                    # Send structured context research results
                    research_data = {
                        "search_queries": ["historical incidents"],
                        "total_documents_found": len(tool_result['results'].get('documents', [])),
                        "relevant_incidents": tool_result['results'].get('documents', []),
                        "pattern_analysis": "Historical pattern analysis from ChromaDB search",
                        "recommendations": ["Consider historical context in analysis"],
                        "confidence_assessment": "High confidence in historical correlation"
                    }
                    
                    await sender.send_context_research(research_data)
                    await sender.send_agent_status_update("context", "complete", "Context research complete")
        
        # Extract detailed analysis from analyst agent tools
        elif "status" in content and "analysis_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'analysis_complete' and 'data' in tool_result:
                    final_results['detailed_analysis'] = tool_result['data']
                    
                    # Send structured analysis recommendations
                    await sender.send_analysis_recommendations(tool_result['data'])
                        
    except Exception as e:
        agent_logger.error(f"❌ CLEAN ARCH: Error parsing tool outputs: {e}")

# ============================================================================
# TEAM CREATION WITH FIXED TERMINATION
# ============================================================================

async def _create_soc_team(
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
):
    """Create SOC team with proper termination conditions"""
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    # Create agents
    triage_agent = TriageAgent(model_client)
    
    # Single approval agent that handles all stages
    approval_agent = UserProxyAgent(
        name="MultiStageApprovalAgent",
        input_func=user_input_func
    )
    
    context_agent = ContextAgent(model_client)
    analyst_agent = AnalystAgent(model_client)
    
    # FIXED: More specific termination conditions
    
    # Normal completion when analyst finishes with specific phrase
    normal_completion = (
        SourceMatchTermination("SeniorAnalyst") & 
        TextMentionTermination("ANALYSIS_COMPLETE - Senior SOC investigation finished")
    )

    # Rejection termination
    rejection_termination = (
        SourceMatchTermination("MultiStageApprovalAgent") & 
        TextMentionTermination("WORKFLOW_REJECTED")
    )
    
    # Function-based completion - when analyst calls report_detailed_analysis
    function_completion = (
        SourceMatchTermination("SeniorAnalyst") & 
        FunctionCallTermination("report_detailed_analysis")
    )
    
    # Backup termination conditions - REDUCED limits
    max_messages = MaxMessageTermination(30)  # REDUCED from 50
    token_limit = TokenUsageTermination(max_total_token=60000)  # REDUCED from 80000
    timeout = TimeoutTermination(timeout_seconds=600)  # REDUCED from 900 (10 minutes)
    
    # FIXED: Combined termination - should stop after analyst function call OR normal completion
    termination = (
        function_completion |
        normal_completion |
        rejection_termination |
        max_messages |
        token_limit |
        timeout
    )
    
    # Create team
    team = RoundRobinGroupChat(
        [triage_agent, approval_agent, context_agent, analyst_agent],
        termination_condition=termination,
        custom_message_types=[
            StructuredMessage[PriorityFindings],
            StructuredMessage[SOCAnalysisResult],
        ],
    )
    
    agent_logger.info("SOC team created with improved termination conditions")
    
    return team, model_client

# ============================================================================
# MAIN WORKFLOW FUNCTION
# ============================================================================

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    Execute SOC analysis workflow using clean message architecture
    """
    agent_logger.info(f"🚀 CLEAN ARCH: Starting SOC analysis workflow for session {session_id}")
    
    # Initialize clean message sender and progress tracker
    sender = CleanMessageSender(session_id, message_callback)
    progress_tracker = WorkflowProgressTracker(sender)
    
    # Initialize results tracking
    final_results = {
        'priority_findings': None,
        'chroma_context': {},
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
                        return "APPROVED - Historical context validated as relevant. SeniorAnalyst, please perform deep analysis."
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
        task = f"""ENHANCED SECURITY LOG ANALYSIS WITH CLEAN ARCHITECTURE

Please analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

MULTI-STAGE WORKFLOW:
1. **TRIAGE STAGE**: TriageSpecialist performs initial threat identification
   - After findings: Request approval with clear threat summary
   - Wait for user decision on investigation

2. **CONTEXT STAGE**: ContextAgent searches historical incidents (if approved)
   - After research: Request validation with historical findings summary  
   - Wait for user validation of context relevance

3. **ANALYSIS STAGE**: SeniorAnalyst performs deep analysis (if context approved)
   - After recommendations: Request authorization for proposed actions
   - Wait for user authorization of recommended actions

4. **COMPLETION**: When complete, end with specific completion phrase

APPROVAL POINTS:
- Each stage MUST request human approval before proceeding
- Provide clear, specific information for decision-making
- Wait for explicit approval before continuing
- Handle custom instructions and modifications

TriageSpecialist: Begin initial triage analysis. After completing your analysis and providing structured findings, request approval to proceed with the investigation."""
        
        agent_logger.info(f"Starting clean architecture team execution for session {session_id}")
        
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
                    "has_context_data": bool(final_results.get('chroma_context')),
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