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
    """Create SOC team with single multi-stage approval agent - FIXED termination conditions"""
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
    
    # Single approval agent that handles all stages
    approval_agent = UserProxyAgent(
        name="MultiStageApprovalAgent",
        input_func=user_input_func
    )
    
    context_agent = ContextAgent(model_client)
    
    analyst_kwargs = {
        "tools": analysis_tools,
        "model_client": model_client,
        "analyst_output_type": analyst_output_type
    }
    
    analyst_agent = AnalystAgent(**analyst_kwargs)
    
    # FIXED: Enhanced termination conditions that don't trigger on instructions
    # Use more specific patterns that only match actual completion messages
    normal_completion = (
        SourceMatchTermination("SeniorAnalyst") & 
        TextMentionTermination("ANALYSIS_COMPLETE - Senior SOC investigation finished")
    )
    
    rejection_termination = (
        SourceMatchTermination("MultiStageApprovalAgent") & 
        TextMentionTermination("WORKFLOW_REJECTED")
    )
    
    max_messages = MaxMessageTermination(50)  # Increased for multi-stage
    token_limit = TokenUsageTermination(max_total_token=80000)  # Increased
    timeout = TimeoutTermination(timeout_seconds=900)  # 15 minutes
    
    # Alternative completion condition - when analyst calls the function
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
    
    # Create team with single instance of each agent (FIXED: no duplicate names)
    team = RoundRobinGroupChat(
        [triage_agent, approval_agent, context_agent, analyst_agent],
        termination_condition=termination
    )
    
    agent_logger.info("Enhanced SOC team created with fixed termination conditions (4 unique agents)")
    
    return team, model_client

async def get_prioritized_task_with_approval(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None
) -> tuple[str, dict, dict]:
    """
    Run SOC analysis with multi-stage user approval - FIXED version with better termination.
    """
    if agent_logger:
        agent_logger.info(f"Starting SOC team analysis with multi-stage approval for session {session_id}")
    
    # Define the user input function with enhanced stage detection
    async def _user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
        """Handle user input requests for multi-stage approval."""
        if user_input_callback:
            try:
                # Send the prompt to the WebSocket callback and wait for response
                user_response = await user_input_callback(prompt, session_id)
                
                agent_logger.info(f"Multi-stage user input received for session {session_id}: {user_response}")
                
                # Process the response based on content
                if user_response.lower() in ['approve', 'approved', 'yes', 'continue']:
                    # Determine next action based on current context
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
                    # Treat as custom instructions
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
        team, model_client = await _create_soc_team(
            user_input_func=_user_input_func,
            use_structured_output=False
        )
        
        # Create the enhanced analysis task - FIXED to avoid triggering termination conditions
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

TriageSpecialist: Begin initial triage analysis. After completing your analysis and calling your function, request approval to proceed with the investigation."""
        
        # Use run_stream for better message tracking
        full_conversation = ""
        priority_findings = {}
        detailed_analysis = {}
        chroma_context = {}
        structured_result = None
        was_rejected = False
        approval_requested = False
        
        agent_logger.info(f"Starting enhanced team execution for session {session_id}")
        
        # Use run_stream to get individual messages
        result_messages = []
        stream = team.run_stream(task=task, cancellation_token=CancellationToken())
        
        async for message in stream:
            if hasattr(message, 'source') and hasattr(message, 'content'):
                result_messages.append(message)
                agent_logger.debug(f"Received message type: {type(message).__name__} from {message.source}")
                agent_logger.debug(f"Message content preview: {str(message.content)[:100]}")
        
        agent_logger.info(f"Enhanced team stream completed for session {session_id}, processing {len(result_messages)} messages")
        
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
                elif msg.source == "MultiStageApprovalAgent":
                    if "review" in str(msg.content).lower() or "decide" in str(msg.content).lower():
                        approval_requested = True
                        agent_logger.info(f"Multi-stage approval workflow triggered for session {session_id}")
                
                # More specific rejection detection
                if (msg.source == "MultiStageApprovalAgent" and 
                    ("WORKFLOW_REJECTED" in str(msg.content) or 
                     ("REJECTED" in str(msg.content) and "human operator" in str(msg.content)))):
                    was_rejected = True
                    agent_logger.info(f"Analysis rejected by user for session {session_id}")
                
                if (msg.source == "SeniorAnalyst" and 
                    isinstance(msg, StructuredMessage) and
                    isinstance(msg.content, SOCAnalysisResult)):
                    structured_result = msg.content
                
                # Parse tool outputs with enhanced detection
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
            agent_logger.info(f"Enhanced SOC team analysis completed for session {session_id}")
            agent_logger.info(f"Final status - Was rejected: {was_rejected}, Approval requested: {approval_requested}")
        
        combined_findings = {
            "priority_threat": priority_findings,
            "detailed_analysis": detailed_analysis,
            "team_conversation": full_conversation,
            "structured_result": structured_result.model_dump() if structured_result else None,
            "was_rejected": was_rejected,
            "approval_requested": approval_requested,
            "multi_stage_workflow": True
        }
        
        return full_conversation, combined_findings, chroma_context
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"Enhanced SOC team analysis error for session {session_id}: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        error_msg = f"Enhanced team analysis error: {str(e)}"
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