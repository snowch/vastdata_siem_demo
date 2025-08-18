import json
import logging
import traceback
from typing import List, Dict, Any
from core.agents.triage import TriageAgent
from core.agents.context import ContextAgent
from core.agents.analyst import AnalystAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import StructuredMessage
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

async def _create_soc_team(use_structured_output: bool = False):
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


    
    triage_agent = TriageAgent(model_client)
    
    context_agent = ContextAgent(model_client)
    
    analyst_kwargs = {
        "tools": analysis_tools,
        "model_client": model_client,
        "analyst_output_type": analyst_output_type
    }
    
    analyst_agent = AnalystAgent(**analyst_kwargs)
    
    normal_completion = TextMentionTermination("ANALYSIS_COMPLETE")
    max_messages = MaxMessageTermination(25)
    token_limit = TokenUsageTermination(max_total_token=60000)
    timeout = TimeoutTermination(timeout_seconds=400)
    analyst_completion = SourceMatchTermination("SeniorAnalyst") & FunctionCallTermination("report_detailed_analysis")
    
    termination = (
        normal_completion |
        analyst_completion |
        max_messages |
        token_limit |
        timeout
    )
    
    team = RoundRobinGroupChat(
        [triage_agent, context_agent, analyst_agent],
        termination_condition=termination
    )
    
    return team, model_client

async def get_prioritized_task(log_batch: str) -> tuple[str, dict, dict]:
    if agent_logger:
        agent_logger.info("Starting SOC team analysis")
    
    try:
        team, model_client = await _create_soc_team(use_structured_output=False)
        
        task = f"""SECURITY LOG ANALYSIS REQUEST

Please analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

TriageSpecialist: Begin initial triage analysis. Remember to use proper data types in your function calls."""
        
        result = await team.run(task=task, cancellation_token=CancellationToken())
        
        full_conversation = ""
        priority_findings = {}
        detailed_analysis = {}
        chroma_context = {}
        structured_result = None
        
        if result.messages:
            conversation_parts = []
            
            for msg in result.messages:
                if hasattr(msg, 'source') and hasattr(msg, 'content'):
                    conversation_parts.append(f"[{msg.source}]: {msg.content}")
                    
                    if (msg.source == "SeniorAnalyst" and 
                        isinstance(msg, StructuredMessage) and
                        isinstance(msg.content, SOCAnalysisResult)):
                        structured_result = msg.content
                    
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
        
        await model_client.close()
        
        if agent_logger:
            agent_logger.info("SOC team analysis completed successfully")
            agent_logger.debug(f"Structured result available: {structured_result is not None}")
        
        combined_findings = {
            "priority_threat": priority_findings,
            "detailed_analysis": detailed_analysis,
            "team_conversation": full_conversation,
            "structured_result": structured_result.model_dump() if structured_result else None
        }
        
        return full_conversation, combined_findings, chroma_context
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"SOC team analysis error: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        error_msg = f"Team analysis error: {str(e)}"
        return error_msg, {}, {"error": str(e)}
