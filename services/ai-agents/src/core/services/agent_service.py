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
from autogen_agentchat.messages import StructuredMessage, UserInputRequestedEvent
from autogen_agentchat.conditions import (
    TextMentionTermination, 
    MaxMessageTermination, 
    TokenUsageTermination,
    TimeoutTermination,
    SourceMatchTermination,
    FunctionCallTermination
)
from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool
from core.services.analysis_service import report_priority_findings, search_historical_incidents, report_detailed_analysis
from core.models.analysis import SOCAnalysisResult

agent_logger = logging.getLogger("agent_diagnostics")

async def _create_soc_team(
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
    use_structured_output: bool = False
):
    """Create SOC team with proper UserProxyAgent integration following AutoGen reference pattern"""
    model_client = OpenAIChatCompletionClient(model="gpt-4o", parallel_tool_calls=False)
    
    if use_structured_output:
        search_tool = FunctionTool(
            search_historical_incidents,
            description="Search historical incidents in ChromaDB",
            strict=True
        )
        analysis_tool = FunctionTool(
            report_detailed_analysis,
            description="Report detailed analysis results",
            strict=True
        )
        context_tools = [search_tool] 
        analysis_tools = [analysis_tool]
        analyst_output_type = SOCAnalysisResult
    else:
        context_tools = [search_historical_incidents]
        analysis_tools = [report_detailed_analysis]
        analyst_output_type = None
    
    # Create agents
    triage_agent = TriageAgent(model_client)
    
    # Add UserProxyAgent for approval after triage - following reference pattern
    approval_agent = UserProxyAgent(
        name="ApprovalAgent",
        input_func=user_input_func  # Direct function reference like in the example
    )
    
    context_agent = ContextAgent(model_client)
    
    analyst_kwargs = {
        "tools": analysis_tools,
        "model_client": model_client,
        "analyst_output_type": analyst_output_type
    }
    
    analyst_agent = AnalystAgent(**analyst_kwargs)
    
    # Termination conditions
    normal_completion = TextMentionTermination("ANALYSIS_COMPLETE")
    rejection_termination = TextMentionTermination("WORKFLOW_REJECTED")  # Changed to be more specific
    max_messages = MaxMessageTermination(30)
    token_limit = TokenUsageTermination(max_total_token=60000)
    timeout = TimeoutTermination(timeout_seconds=600)
    analyst_completion = SourceMatchTermination("SeniorAnalyst") & FunctionCallTermination("report_detailed_analysis")
    
    termination = (
        normal_completion |
        rejection_termination |
        analyst_completion |
        max_messages |
        token_limit |
        timeout
    )
    
    # Create team with approval agent included
    team = RoundRobinGroupChat(
        [triage_agent, approval_agent, context_agent, analyst_agent],
        termination_condition=termination
    )
    
    # Clean logging without accessing private attributes
    agent_logger.info("SOC team created with 4 agents: TriageSpecialist, ApprovalAgent, ContextAgent, SeniorAnalyst")
    
    return team, model_client

async def get_prioritized_task_with_approval(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None
) -> tuple[str, dict, dict]:
    """
    Run SOC analysis with user approval step after triage - following AutoGen reference pattern.
    """
    if agent_logger:
        agent_logger.info(f"Starting SOC team analysis with approval for session {session_id}")
    
    # Define the user input function following the reference pattern
    async def _user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
        """Handle user input requests from the approval agent - following reference pattern."""
        if user_input_callback:
            try:
                # Send the prompt to the WebSocket callback and wait for response
                user_response = await user_input_callback(prompt, session_id)
                
                agent_logger.info(f"User input received for session {session_id}: {user_response}")
                
                # Process the response and return appropriate message
                if user_response.lower() in ['approve', 'approved', 'yes', 'continue']:
                    return "APPROVED - The human operator has approved the analysis. ContextAgent, please search for similar historical incidents based on the triage findings."
                elif user_response.lower() in ['reject', 'rejected', 'no', 'stop', 'cancel']:
                    return "REJECTED - The human operator has rejected the analysis. The workflow is now stopped. WORKFLOW_REJECTED"
                else:
                    return f"User response: {user_response}. Please respond with APPROVE or REJECT to continue."
                    
            except asyncio.TimeoutError:
                agent_logger.warning(f"User input timeout for session {session_id}")
                return "TIMEOUT - No user response received within the time limit. Auto-approving to continue. ContextAgent, please proceed with historical research."
            except Exception as e:
                agent_logger.error(f"Error getting user input for session {session_id}: {e}")
                return "ERROR - Failed to get user input. Auto-approving to continue the analysis. ContextAgent, please proceed."
        else:
            # No callback available, auto-approve
            agent_logger.info(f"No user input callback for session {session_id}, auto-approving")
            return "AUTO-APPROVED - No user input mechanism available, automatically continuing with analysis. ContextAgent, please proceed with historical research."
    
    try:
        team, model_client = await _create_soc_team(
            user_input_func=_user_input_func,
            use_structured_output=False
        )
        
        # Create the analysis task - using different termination keywords to avoid false detection
        task = f"""SECURITY LOG ANALYSIS REQUEST WITH APPROVAL WORKFLOW

Please analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

WORKFLOW:
1. TriageSpecialist: Begin initial triage analysis and identify the top priority threat
2. ApprovalAgent: After triage findings, the human operator will review and decide:
   - APPROVE to continue with full analysis
   - REJECT to stop the workflow
3. If APPROVED: ContextAgent searches for historical context
4. If APPROVED: SeniorAnalyst performs deep analysis
5. Complete with "ANALYSIS_COMPLETE" or use "WORKFLOW_REJECTED" if user rejects

TriageSpecialist: Begin initial triage analysis. Remember to use proper data types in your function calls.
After completing your analysis, hand off to ApprovalAgent for human review."""
        
        # Use run_stream for better message tracking
        full_conversation = ""
        priority_findings = {}
        detailed_analysis = {}
        chroma_context = {}
        structured_result = None
        was_rejected = False
        approval_requested = False
        
        agent_logger.info(f"Starting team execution for session {session_id}")
        
        # Use run_stream to get individual messages
        result_messages = []
        stream = team.run_stream(task=task, cancellation_token=CancellationToken())
        
        async for message in stream:
            if hasattr(message, 'source') and hasattr(message, 'content'):
                result_messages.append(message)
                agent_logger.debug(f"Received message type: {type(message).__name__} from {message.source}")
                agent_logger.debug(f"Message content preview: {str(message.content)[:100]}")
        
        agent_logger.info(f"Team stream completed for session {session_id}, processing {len(result_messages)} messages")
        
        # Process all messages
        conversation_parts = []
        for msg in result_messages:
            if hasattr(msg, 'source') and hasattr(msg, 'content'):
                conversation_parts.append(f"[{msg.source}]: {msg.content}")
                
                # Debug logging for message types
                agent_logger.debug(f"Processing message from {msg.source}: Type={type(msg).__name__}")
                
                # Check for approval request - UserInputRequestedEvent will be sent
                if isinstance(msg, UserInputRequestedEvent):
                    approval_requested = True
                    agent_logger.info(f"User input requested for session {session_id}: {getattr(msg, 'content', 'No content')}")
                elif msg.source == "ApprovalAgent":
                    if "review" in str(msg.content).lower() or "decide" in str(msg.content).lower():
                        approval_requested = True
                        agent_logger.info(f"Approval workflow triggered for session {session_id}")
                
                # More specific rejection detection - only check ApprovalAgent messages
                if (msg.source == "ApprovalAgent" and 
                    ("WORKFLOW_REJECTED" in str(msg.content) or 
                     ("REJECTED" in str(msg.content) and "human operator" in str(msg.content)))):
                    was_rejected = True
                    agent_logger.info(f"Analysis rejected by user for session {session_id}")
                
                if (msg.source == "SeniorAnalyst" and 
                    isinstance(msg, StructuredMessage) and
                    isinstance(msg.content, SOCAnalysisResult)):
                    structured_result = msg.content
                
                # Parse tool outputs
                if hasattr(msg, 'content') and isinstance(msg.content, str):
                    if "status" in msg.content and "priority_identified" in msg.content:
                        try:
                            import re
                            json_match = re.search(r'\{.*"status".*\}', msg.content, re.DOTALL)
                            if json_match:
                                tool_result = json.loads(json_match.group())
                                if tool_result.get('status') == 'priority_identified' and 'data' in tool_result:
                                    priority_findings = tool_result['data']
                        except:
                            pass
                    
                    elif "status" in msg.content and "search_complete" in msg.content:
                        try:
                            json_match = re.search(r'\{.*"status".*\}', msg.content, re.DOTALL)
                            if json_match:
                                tool_result = json.loads(json_match.group())
                                if tool_result.get('status') == 'search_complete' and 'results' in tool_result:
                                    chroma_context = tool_result['results']
                        except:
                            pass
                    
                    elif "status" in msg.content and "analysis_complete" in msg.content:
                        try:
                            json_match = re.search(r'\{.*"status".*\}', msg.content, re.DOTALL)
                            if json_match:
                                tool_result = json.loads(json_match.group())
                                if tool_result.get('status') == 'analysis_complete' and 'data' in tool_result:
                                    detailed_analysis = tool_result['data']
                        except:
                            pass
        
        full_conversation = "\n\n".join(conversation_parts)
        agent_logger.info(f"Full conversation length for session {session_id}: {len(full_conversation)} characters")
        
        await model_client.close()
        
        if agent_logger:
            agent_logger.info(f"SOC team analysis completed for session {session_id}")
            agent_logger.info(f"Final status - Was rejected: {was_rejected}, Approval requested: {approval_requested}")
        
        combined_findings = {
            "priority_threat": priority_findings,
            "detailed_analysis": detailed_analysis,
            "team_conversation": full_conversation,
            "structured_result": structured_result.model_dump() if structured_result else None,
            "was_rejected": was_rejected,
            "approval_requested": approval_requested
        }
        
        return full_conversation, combined_findings, chroma_context
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"SOC team analysis error for session {session_id}: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        error_msg = f"Team analysis error: {str(e)}"
        return error_msg, {"error": str(e)}, {"error": str(e)}

# Keep the original function for backward compatibility
async def get_prioritized_task(log_batch: str) -> tuple[str, dict, dict]:
    """
    Original function without approval workflow for backward compatibility.
    """
    # Generate a dummy session ID and run without approval callback
    import uuid
    session_id = str(uuid.uuid4())
    return await get_prioritized_task_with_approval(
        log_batch=log_batch,
        session_id=session_id,
        user_input_callback=None
    )