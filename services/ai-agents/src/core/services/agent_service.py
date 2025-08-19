import json
import logging
import traceback
import asyncio
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
from core.models.websocket import AnalysisProgress
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
        custom_message_types=[StructuredMessage[PriorityFindings]],
    )
    
    agent_logger.info("SOC team created for real-time streaming with structured output support")
    
    return team, model_client

async def _process_streaming_message(
    message, 
    progress: AnalysisProgress, 
    message_callback: Optional[Callable],
    session_id: str
):
    """Process a streaming message and update progress incrementally"""
    try:
        if hasattr(message, 'source') and hasattr(message, 'content'):
            # Add to conversation history
            conversation_entry = f"[{message.source}]: {message.content}"
            progress.final_results['conversation_parts'].append(conversation_entry)
            
            agent_logger.debug(f"Processing streaming message from {message.source}: Type={type(message).__name__}")
            
            # Send to real-time callback if available
            if (message_callback and 
                message.source not in ['user', 'system'] and 
                not isinstance(message, UserInputRequestedEvent)):
                try:
                    await message_callback({
                        'type': 'agent_message',
                        'source': message.source,
                        'content': str(message.content),
                        'message_type': type(message).__name__,
                        'session_id': session_id
                    })
                except Exception as e:
                    agent_logger.error(f"Error in message callback: {e}")
            
            # Handle structured output from triage agent
            if (message.source == "TriageSpecialist" and 
                isinstance(message, StructuredMessage) and
                isinstance(message.content, PriorityFindings)):
                
                # Store structured findings
                priority_findings = message.content.model_dump()
                progress.final_results['structured_findings']['priority_threat'] = priority_findings
                agent_logger.info(f"Structured priority findings stored: {priority_findings.get('threat_type')} from {priority_findings.get('source_ip')}")
                
                # Send priority findings update via callback
                if message_callback:
                    await message_callback({
                        'type': 'priority_findings',
                        'data': priority_findings,
                        'session_id': session_id
                    })
            
            # Handle approval requests
            elif isinstance(message, UserInputRequestedEvent):
                agent_logger.info(f"User input requested for session {session_id}")
                
                if message_callback:
                    try:
                        await message_callback({
                            'type': 'UserInputRequestedEvent',
                            'content': getattr(message, 'content', 'Approval required'),
                            'source': message.source,
                            'session_id': session_id
                        })
                    except Exception as e:
                        agent_logger.error(f"Error sending approval request: {e}")
            
            # Check for workflow rejection
            elif (message.source == "MultiStageApprovalAgent" and 
                  ("WORKFLOW_REJECTED" in str(message.content) or 
                   ("REJECTED" in str(message.content) and "human operator" in str(message.content)))):
                
                progress.final_results['was_rejected'] = True
                progress.final_results['rejection_stage'] = 'unknown'  # Could be enhanced to track specific stage
                agent_logger.info(f"Analysis rejected by user for session {session_id}")
                
                if message_callback:
                    await message_callback({
                        'type': 'workflow_rejected',
                        'content': 'Analysis workflow was rejected by user',
                        'session_id': session_id
                    })
            
            # Handle structured results from analyst
            elif (message.source == "SeniorAnalyst" and 
                  isinstance(message, StructuredMessage) and
                  isinstance(message.content, SOCAnalysisResult)):
                
                progress.final_results['structured_result'] = message.content.model_dump()
            
            # Parse tool outputs for context and analyst agents
            elif hasattr(message, 'content') and isinstance(message.content, str):
                await _parse_tool_outputs(message, progress, message_callback, session_id)
                
    except Exception as e:
        agent_logger.error(f"Error processing streaming message: {e}")

async def _parse_tool_outputs(message, progress: AnalysisProgress, message_callback: Optional[Callable], session_id: str):
    """Parse and handle tool outputs from agent messages"""
    content = message.content
    
    try:
        # Extract context search results
        if "status" in content and "search_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'search_complete' and 'results' in tool_result:
                    progress.final_results['chroma_context'] = sanitize_chroma_results(tool_result['results'])
                    
                    # Send context update
                    if message_callback:
                        await message_callback({
                            'type': 'context_results',
                            'data': tool_result['results'],
                            'session_id': session_id
                        })
        
        # Extract detailed analysis from analyst agent tools
        elif "status" in content and "analysis_complete" in content:
            import re
            json_match = re.search(r'\{.*"status".*\}', content, re.DOTALL)
            if json_match:
                tool_result = json.loads(json_match.group())
                if tool_result.get('status') == 'analysis_complete' and 'data' in tool_result:
                    progress.final_results['structured_findings']['detailed_analysis'] = tool_result['data']
                    
                    # Send analysis complete update
                    if message_callback:
                        await message_callback({
                            'type': 'analysis_complete',
                            'data': tool_result['data'],
                            'session_id': session_id
                        })
                        
    except Exception as e:
        agent_logger.error(f"Error parsing tool outputs: {e}")

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    progress: AnalysisProgress,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    Execute SOC analysis workflow with real-time streaming.
    
    Args:
        log_batch: Security logs to analyze
        session_id: WebSocket session ID
        progress: Progress tracking object to update
        user_input_callback: Function to handle user input requests
        message_callback: Function to handle real-time agent messages
    
    Returns:
        bool: True if analysis completed successfully, False otherwise
    """
    if agent_logger:
        agent_logger.info(f"Starting SOC analysis workflow for session {session_id}")
    
    # Initialize progress.final_results
    progress.final_results = {
        'conversation_parts': [],
        'structured_findings': {},
        'chroma_context': {},
        'structured_result': None,
        'was_rejected': False,
        'approval_requested': False,
        'real_time_streaming': True
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
        await progress.send_update("starting", progress=10)
        
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
            await _process_streaming_message(message, progress, message_callback, session_id)
        
        await model_client.close()
        
        # Build final conversation from parts
        progress.final_results['team_conversation'] = "\n\n".join(progress.final_results['conversation_parts'])
        
        # Set completion status
        progress.completed = True
        
        # Send final completion update
        if message_callback:
            await message_callback({
                'type': 'analysis_complete_final',
                'was_rejected': progress.final_results.get('was_rejected', False),
                'session_id': session_id
            })
        
        if not progress.final_results.get('was_rejected', False):
            await progress.send_update("completed", progress=100)
        else:
            await progress.send_update("rejected", progress=100)
        
        if agent_logger:
            agent_logger.info(f"SOC analysis workflow completed for session {session_id}")
            agent_logger.info(f"Final status - Was rejected: {progress.final_results.get('was_rejected', False)}")
        
        return not progress.final_results.get('was_rejected', False)
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"SOC analysis workflow error for session {session_id}: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Send error via callback
        if message_callback:
            await message_callback({
                'type': 'error',
                'content': f"Analysis error: {str(e)}",
                'session_id': session_id
            })
        
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)
        
        return False
