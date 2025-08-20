# services/ai-agents/src/core/services/agent_service.py - DEBUG VERSION
# Add extensive logging to debug callback issues

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

agent_logger = logging.getLogger("agent_diagnostics")

async def _create_soc_team(
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
):
    """Create SOC team with single multi-stage approval agent"""
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
    
    # Termination conditions
    normal_completion = (
        SourceMatchTermination("SeniorAnalyst") & 
        TextMentionTermination("ANALYSIS_COMPLETE - Senior SOC investigation finished")
    )

    rejection_termination = (
        SourceMatchTermination("MultiStageApprovalAgent") & 
        TextMentionTermination("WORKFLOW_REJECTED")
    )
    
    max_messages = MaxMessageTermination(50)
    token_limit = TokenUsageTermination(max_total_token=80000)
    timeout = TimeoutTermination(timeout_seconds=900)  # 15 minutes
    
    analyst_completion = (
        SourceMatchTermination("SeniorAnalyst") & 
        FunctionCallTermination("report_detailed_analysis")
    )
    
    termination = (
        normal_completion |
        rejection_termination |
        analyst_completion |
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
    
    agent_logger.info("SOC team created for simplified streaming")
    
    return team, model_client

async def _process_streaming_message(
    message, 
    message_callback: Optional[Callable],
    session_id: str,
    final_results: Dict[str, Any]
):
    """Process a streaming message and send real-time updates - DEBUG VERSION"""
    try:
        if hasattr(message, 'source') and hasattr(message, 'content'):
            source = message.source
            content = str(message.content)
            
            agent_logger.debug(f"Processing streaming message from {source}: Type={type(message).__name__}")
            agent_logger.debug(f"Message callback available: {message_callback is not None}")
            
            # PRIORITY 1: Handle structured output from triage agent
            if (source == "TriageSpecialist" and 
                isinstance(message, StructuredMessage) and
                isinstance(message.content, PriorityFindings)):
                
                # Store structured findings
                priority_findings = message.content.model_dump()
                final_results['priority_findings'] = priority_findings
                agent_logger.info(f"✅ STRUCTURED TRIAGE: {priority_findings.get('threat_type')} from {priority_findings.get('source_ip')}")
                
                # Send priority findings update via callback - DEBUG VERSION
                if message_callback:
                    try:
                        agent_logger.info(f"🚀 ATTEMPTING to send priority_findings_update via callback for session {session_id}")
                        
                        callback_data = {
                            'type': 'priority_findings_update',
                            'data': priority_findings,
                            'session_id': session_id
                        }
                        
                        agent_logger.info(f"📤 Callback data prepared: type={callback_data['type']}, session={session_id}")
                        agent_logger.debug(f"📋 Full callback data: {json.dumps(callback_data, indent=2)}")
                        
                        await message_callback(callback_data)
                        
                        agent_logger.info(f"✅ SUCCESSFULLY SENT priority_findings_update for session {session_id}")
                        
                    except Exception as e:
                        agent_logger.error(f"❌ ERROR sending priority_findings_update: {e}")
                        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
                else:
                    agent_logger.warning(f"⚠️ NO MESSAGE CALLBACK available for session {session_id} - cannot send priority_findings_update")
                
                # EARLY RETURN: Don't send this as real_time_agent_output since we sent structured version
                agent_logger.debug(f"⏭️ Early return for structured triage message - session {session_id}")
                return
            
            # PRIORITY 2: Handle structured results from analyst
            elif (source == "SeniorAnalyst" and 
                  isinstance(message, StructuredMessage) and
                  isinstance(message.content, SOCAnalysisResult)):
                
                final_results['structured_result'] = message.content.model_dump()
                agent_logger.info(f"✅ STRUCTURED ANALYST: Analysis complete")
                
                # Send structured analysis results
                if message_callback:
                    try:
                        agent_logger.info(f"🚀 ATTEMPTING to send detailed_analysis_update via callback for session {session_id}")
                        
                        await message_callback({
                            'type': 'detailed_analysis_update',
                            'data': message.content.model_dump(),
                            'session_id': session_id
                        })
                        
                        agent_logger.info(f"✅ SUCCESSFULLY SENT detailed_analysis_update for session {session_id}")
                        
                    except Exception as e:
                        agent_logger.error(f"❌ ERROR sending detailed_analysis_update: {e}")
                        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
                else:
                    agent_logger.warning(f"⚠️ NO MESSAGE CALLBACK available for session {session_id} - cannot send detailed_analysis_update")
                
                # EARLY RETURN: Don't send this as real_time_agent_output since we sent structured version
                agent_logger.debug(f"⏭️ Early return for structured analyst message - session {session_id}")
                return
            
            # PRIORITY 3: Handle approval requests
            elif isinstance(message, UserInputRequestedEvent):
                agent_logger.info(f"👤 APPROVAL REQUEST: session {session_id}")
                
                if message_callback:
                    try:
                        agent_logger.info(f"🚀 ATTEMPTING to send UserInputRequestedEvent via callback for session {session_id}")
                        
                        await message_callback({
                            'type': 'UserInputRequestedEvent',
                            'content': getattr(message, 'content', 'Approval required'),
                            'source': source,
                            'session_id': session_id
                        })
                        
                        agent_logger.info(f"✅ SUCCESSFULLY SENT UserInputRequestedEvent for session {session_id}")
                        
                    except Exception as e:
                        agent_logger.error(f"❌ ERROR sending UserInputRequestedEvent: {e}")
                        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
                else:
                    agent_logger.warning(f"⚠️ NO MESSAGE CALLBACK available for session {session_id} - cannot send UserInputRequestedEvent")
                
                # EARLY RETURN: Don't send approval requests as real_time_agent_output
                agent_logger.debug(f"⏭️ Early return for approval request - session {session_id}")
                return
            
            # PRIORITY 4: Handle workflow rejection
            elif (source == "MultiStageApprovalAgent" and 
                  ("WORKFLOW_REJECTED" in content or 
                   ("REJECTED" in content and "human operator" in content))):
                
                final_results['was_rejected'] = True
                agent_logger.info(f"❌ WORKFLOW REJECTED: session {session_id}")
                
                if message_callback:
                    try:
                        agent_logger.info(f"🚀 ATTEMPTING to send workflow_rejected via callback for session {session_id}")
                        
                        await message_callback({
                            'type': 'workflow_rejected',
                            'content': 'Analysis workflow was rejected by user',
                            'session_id': session_id
                        })
                        
                        agent_logger.info(f"✅ SUCCESSFULLY SENT workflow_rejected for session {session_id}")
                        
                    except Exception as e:
                        agent_logger.error(f"❌ ERROR sending workflow_rejected: {e}")
                        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
                else:
                    agent_logger.warning(f"⚠️ NO MESSAGE CALLBACK available for session {session_id} - cannot send workflow_rejected")
                
                # EARLY RETURN: Don't send rejection as real_time_agent_output
                agent_logger.debug(f"⏭️ Early return for workflow rejection - session {session_id}")
                return
            
            # DEFAULT: Send ALL OTHER messages as real_time_agent_output
            # This includes triage intermediate work, context outputs, analyst work, etc.
            if (message_callback and 
                source not in ['user', 'system']):
                try:
                    agent_type = determine_agent_type(source)
                    if agent_type:
                        agent_logger.debug(f"💬 SENDING real_time_agent_output: {agent_type} - {content[:50]}...")
                        
                        await message_callback({
                            'type': 'real_time_agent_output',
                            'agent': agent_type,
                            'content': content,
                            'source': source,
                            'timestamp': datetime.now().isoformat(),
                            'session_id': session_id
                        })
                        
                        agent_logger.debug(f"✅ SENT real_time_agent_output for {agent_type}")
                    else:
                        agent_logger.debug(f"⚠️ Could not determine agent type for source: {source}")
                except Exception as e:
                    agent_logger.error(f"❌ ERROR sending real_time_agent_output: {e}")
                    agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
            elif not message_callback:
                agent_logger.debug(f"⚠️ No callback available for real_time_agent_output from {source}")
            
            # Parse tool outputs for context and analyst agents
            await _parse_tool_outputs(message, final_results, message_callback, session_id)
                
    except Exception as e:
        agent_logger.error(f"❌ CRITICAL ERROR processing streaming message: {e}")
        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")

def determine_agent_type(agent_source: str) -> str:
    """Enhanced agent type determination"""
    agent_source_lower = agent_source.lower()
    
    # Enhanced mapping with more variations
    agent_mappings = {
        'triagespecialist': 'triage',
        'triage': 'triage',
        'contextAgent': 'context',
        'context': 'context', 
        'senioranalystspecialist': 'analyst',
        'senioranalyst': 'analyst',
        'analyst': 'analyst',
        'multistageapprovalagent': 'approval',
        'approval': 'approval'
    }
    
    for source_key, agent_type in agent_mappings.items():
        if source_key in agent_source_lower:
            return agent_type
    
    return None

async def _parse_tool_outputs(message, final_results: Dict, message_callback: Optional[Callable], session_id: str):
    """Parse and handle tool outputs from agent messages"""
    content = str(message.content)
    
    try:
        # Extract context search results
        if "status" in content and "search_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'search_complete' and 'results' in tool_result:
                    final_results['chroma_context'] = sanitize_chroma_results(tool_result['results'])
                    
                    # Send context update
                    if message_callback:
                        try:
                            agent_logger.info(f"🚀 ATTEMPTING to send context_results_update via callback for session {session_id}")
                            
                            await message_callback({
                                'type': 'context_results_update',
                                'data': tool_result['results'],
                                'session_id': session_id
                            })
                            
                            agent_logger.info(f"✅ SUCCESSFULLY SENT context_results_update for session {session_id}")
                            
                        except Exception as e:
                            agent_logger.error(f"❌ ERROR sending context_results_update: {e}")
                            agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
        
        # Extract detailed analysis from analyst agent tools
        elif "status" in content and "analysis_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'analysis_complete' and 'data' in tool_result:
                    final_results['detailed_analysis'] = tool_result['data']
                    
                    # Send analysis complete update
                    if message_callback:
                        try:
                            agent_logger.info(f"🚀 ATTEMPTING to send detailed_analysis_update (tool) via callback for session {session_id}")
                            
                            await message_callback({
                                'type': 'detailed_analysis_update',
                                'data': tool_result['data'],
                                'session_id': session_id
                            })
                            
                            agent_logger.info(f"✅ SUCCESSFULLY SENT detailed_analysis_update (tool) for session {session_id}")
                            
                        except Exception as e:
                            agent_logger.error(f"❌ ERROR sending detailed_analysis_update (tool): {e}")
                            agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
        
        # Detect function calls
        if ('FunctionCall(' in content or 
            'report_priority_findings' in content or 
            'report_detailed_analysis' in content):
            
            agent_logger.info(f"🔧 FUNCTION CALL: {message.source}")
            
            if message_callback:
                try:
                    agent_type = determine_agent_type(message.source)
                    function_name = "priority_findings" if 'priority' in content else "detailed_analysis"
                    
                    agent_logger.info(f"🚀 ATTEMPTING to send function_call_detected via callback for session {session_id}")
                    
                    await message_callback({
                        'type': 'function_call_detected',
                        'agent': agent_type,
                        'function': function_name,
                        'content': content,
                        'timestamp': datetime.now().isoformat(),
                        'session_id': session_id
                    })
                    
                    agent_logger.info(f"✅ SUCCESSFULLY SENT function_call_detected for session {session_id}")
                    
                except Exception as e:
                    agent_logger.error(f"❌ ERROR sending function_call_detected: {e}")
                    agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
                        
    except Exception as e:
        agent_logger.error(f"❌ ERROR parsing tool outputs: {e}")
        agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    SIMPLIFIED: Execute SOC analysis workflow without progress parameter.
    
    Args:
        log_batch: Security logs to analyze
        session_id: WebSocket session ID
        user_input_callback: Function to handle user input requests
        message_callback: Function to handle real-time agent messages
    
    Returns:
        bool: True if analysis completed successfully, False otherwise
    """
    agent_logger.info(f"Starting simplified SOC analysis workflow for session {session_id}")
    agent_logger.info(f"Callbacks available - user_input: {user_input_callback is not None}, message: {message_callback is not None}")
    
    # Initialize simple results tracking
    final_results = {
        'priority_findings': None,
        'chroma_context': {},
        'detailed_analysis': None,
        'structured_result': None,
        'was_rejected': False
    }
    
    # Define the user input function
    async def _user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
        """Handle user input requests for multi-stage approval."""
        if user_input_callback:
            try:
                user_response = await user_input_callback(prompt, session_id)
                agent_logger.info(f"User input received for session {session_id}: {user_response}")
                
                # Process the response based on content
                if user_response.lower() in ['approve', 'approved', 'yes', 'continue']:
                    if 'triage' in prompt.lower() or 'priority threat' in prompt.lower():
                        return "APPROVED - Triage findings approved. ContextAgent, please search for similar historical incidents."
                    elif 'historical' in prompt.lower() or 'context' in prompt.lower():
                        return "APPROVED - Historical context validated as relevant. SeniorAnalyst, please perform deep analysis."
                    elif 'recommend' in prompt.lower() or 'action' in prompt.lower():
                        return "APPROVED - Recommended actions authorized. Please proceed with implementation."
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
                return "TIMEOUT - No user response received. Auto-approving to continue analysis."
            except Exception as e:
                agent_logger.error(f"Error getting user input for session {session_id}: {e}")
                return "ERROR - Failed to get user input. Auto-approving to continue analysis."
        else:
            agent_logger.info(f"No user input callback for session {session_id}, auto-approving")
            return "AUTO-APPROVED - No user input mechanism available, automatically continuing with analysis."
    
    try:
        team, model_client = await _create_soc_team(user_input_func=_user_input_func)
        
        # Create the analysis task
        task = f"""ENHANCED SECURITY LOG ANALYSIS WITH MULTI-STAGE APPROVAL WORKFLOW

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
        
        agent_logger.info(f"Starting team execution for session {session_id}")
        
        # Use run_stream for real-time message processing
        stream = team.run_stream(task=task, cancellation_token=CancellationToken())
        
        # Process messages in real-time as they arrive
        async for message in stream:
            await _process_streaming_message(message, message_callback, session_id, final_results)
        
        await model_client.close()
        
        # Send final completion update
        if message_callback:
            try:
                agent_logger.info(f"🚀 ATTEMPTING to send analysis_complete_final via callback for session {session_id}")
                
                await message_callback({
                    'type': 'analysis_complete_final',
                    'was_rejected': final_results.get('was_rejected', False),
                    'results': final_results,
                    'session_id': session_id
                })
                
                agent_logger.info(f"✅ SUCCESSFULLY SENT analysis_complete_final for session {session_id}")
                
            except Exception as e:
                agent_logger.error(f"❌ ERROR sending analysis_complete_final: {e}")
                agent_logger.error(f"❌ Full error traceback: {traceback.format_exc()}")
        
        success = not final_results.get('was_rejected', False)
        
        agent_logger.info(f"Simplified SOC analysis workflow completed for session {session_id}")
        agent_logger.info(f"Final status - Was rejected: {final_results.get('was_rejected', False)}")
        
        return success
        
    except Exception as e:
        agent_logger.error(f"Simplified SOC analysis workflow error for session {session_id}: {e}")
        agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Send error via callback
        if message_callback:
            try:
                await message_callback({
                    'type': 'error',
                    'content': f"Analysis error: {str(e)}",
                    'session_id': session_id
                })
            except Exception as callback_error:
                agent_logger.error(f"❌ ERROR sending error via callback: {callback_error}")
        
        return False