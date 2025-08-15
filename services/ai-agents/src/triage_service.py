import asyncio
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseAgentEvent, ToolCallRequestEvent, ToolCallExecutionEvent
from autogen_agentchat.conditions import (
    TextMentionTermination, 
    MaxMessageTermination, 
    TokenUsageTermination,
    TimeoutTermination,
    SourceMatchTermination,
    FunctionCallTermination
)
from autogen_core import CancellationToken
import json
import logging
import traceback
from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME
from vectordb_utils import search_chroma

# Global logger instances (initialized by init_logging)
trace_logger = None
event_logger = None
agent_logger = None

def init_logging():
    """Initializes logging for the triage service."""
    global trace_logger, event_logger, agent_logger

    # Prevent re-initialization if already configured (e.g., due to Flask reloader)
    if agent_logger and agent_logger.handlers:
        return

    # Configure root logger only if not already configured
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Create specific loggers and set their levels
    trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
    trace_logger.setLevel(logging.DEBUG)

    event_logger = logging.getLogger(EVENT_LOGGER_NAME)
    event_logger.setLevel(logging.DEBUG)

    # Create a custom logger for our agent diagnostics
    agent_logger = logging.getLogger("agent_diagnostics")
    agent_logger.setLevel(logging.DEBUG)

    # Add a file handler for agent diagnostics
    handler = logging.FileHandler('agent_diagnostics.log')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    agent_logger.addHandler(handler)

# Tool functions for agents to use
def report_priority_findings(
    priority: str,
    threat_type: str,
    source_ip: str,
    target_hosts: list,
    attack_pattern: str,
    timeline_start: str,
    timeline_end: str,
    indicators: list,
    confidence_score: float,
    event_count: int,
    affected_services: list,
    brief_summary: str
) -> dict:
    """Function for initial triage to report the highest priority threat found."""
    findings = {
        "priority": priority,
        "threat_type": threat_type,
        "source_ip": source_ip,
        "target_hosts": target_hosts,
        "attack_pattern": attack_pattern,
        "timeline": {
            "start": timeline_start,
            "end": timeline_end
        },
        "indicators": indicators,
        "confidence_score": confidence_score,
        "event_count": event_count,
        "affected_services": affected_services,
        "brief_summary": brief_summary
    }
    
    if agent_logger:
        agent_logger.info(f"Priority findings recorded: {findings['threat_type']} from {findings['source_ip']}")
    
    return {"status": "priority_identified", "data": findings}

def search_historical_incidents(search_query: str, max_results: int = 10) -> dict:
    """Function for context agent to search ChromaDB for historical incidents."""
    try:
        if agent_logger:
            agent_logger.info(f"Searching ChromaDB with query: {search_query}")
        
        results = search_chroma(search_query, n_results=max_results)
        
        if agent_logger:
            agent_logger.info(f"ChromaDB returned {len(results.get('documents', []))} results")
        
        return {"status": "search_complete", "results": results}
    
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"ChromaDB search error: {e}")
        return {"status": "search_failed", "error": str(e)}

def report_detailed_analysis(
    threat_assessment: dict,
    attack_timeline: list,
    attribution_indicators: list,
    lateral_movement_evidence: list,
    data_at_risk: list,
    business_impact: str,
    recommended_actions: list,
    investigation_notes: str
) -> dict:
    """Function for detailed analysis after ChromaDB context enrichment."""
    analysis = {
        "threat_assessment": threat_assessment,
        "attack_timeline": attack_timeline,
        "attribution_indicators": attribution_indicators,
        "lateral_movement_evidence": lateral_movement_evidence,
        "data_at_risk": data_at_risk,
        "business_impact": business_impact,
        "recommended_actions": recommended_actions,
        "investigation_notes": investigation_notes
    }
    
    if agent_logger:
        agent_logger.info(f"Detailed analysis completed: {len(recommended_actions)} recommendations generated")
    
    return {"status": "analysis_complete", "data": analysis}

async def create_soc_team():
    """Create the SOC analysis team with specialized agents."""
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    # Agent 1: Triage Specialist
    triage_agent = AssistantAgent(
        name="TriageSpecialist",
        model_client=model_client,
        system_message="""You are a SOC Triage Specialist. Your role is to:

1. **ANALYZE OCSF LOGS**: Review the provided security log events
2. **IDENTIFY TOP PRIORITY**: Find the SINGLE most critical threat requiring immediate attention
3. **PRIORITIZE BY IMPACT**: 
   - Critical: Active attacks, privilege escalation
   - High: Lateral movement, data access
   - Medium: Failed attacks, reconnaissance
   - Low: Anomalies requiring monitoring

4. **LOOK FOR PATTERNS**:
   - Multiple failed auth → success (brute force)
   - Unusual process execution
   - Suspicious network connections
   - File access anomalies
   - Privilege escalation attempts

5. **CALL FUNCTION**: Use report_priority_findings() to structure your findings with proper data types:
   - target_hosts: must be a list (e.g., ["host1", "host2"])
   - indicators: must be a list (e.g., ["indicator1", "indicator2"]) 
   - affected_services: must be a list (e.g., ["ssh", "rdp"])
   - confidence_score: must be a float (e.g., 0.85)
   - event_count: must be an integer

6. **HAND OFF**: After successfully calling the function, say "CONTEXT_AGENT please search for similar historical incidents" and provide the key search terms.

Focus ONLY on initial triage. Don't do deep analysis - that's for later agents.""",
        tools=[report_priority_findings]
    )
    
    # Agent 2: Context Research Specialist  
    context_agent = AssistantAgent(
        name="ContextAgent", 
        model_client=model_client,
        system_message="""You are a SOC Context Research Specialist. Your role is to:

1. **RECEIVE HANDOFF**: Wait for TriageSpecialist to identify priority threat
2. **SEARCH HISTORICAL DATA**: Use search_historical_incidents() to find similar past incidents
3. **BUILD SEARCH QUERIES**: Create effective searches using:
   - Threat type (brute_force_attack, lateral_movement, etc.)
   - Attack patterns (ssh_login_failure, privilege_escalation, etc.) 
   - Source IPs, affected services
   - Priority levels

4. **MULTIPLE SEARCHES**: Perform 2-3 different searches to get comprehensive context:
   - Search by threat type
   - Search by attack pattern  
   - Search by affected services

5. **SUMMARIZE CONTEXT**: Provide a clear summary of historical patterns:
   - How similar attacks progressed
   - What indicators were present
   - How they were resolved
   - What worked/didn't work

6. **HAND OFF**: After completing searches, say "ANALYST_AGENT please perform deep analysis with this context" and provide both original findings and historical context.

You are the bridge between initial triage and deep analysis.""",
        tools=[search_historical_incidents]
    )
    
    # Agent 3: Senior Analyst
    analyst_agent = AssistantAgent(
        name="SeniorAnalyst",
        model_client=model_client, 
        system_message="""You are a Senior SOC Analyst. Your role is to:

1. **RECEIVE CONTEXT**: Get priority threat + historical context from previous agents
2. **DEEP ANALYSIS**: Perform comprehensive investigation:
   - Timeline reconstruction
   - Attack progression analysis
   - Lateral movement assessment
   - Data impact evaluation
   - Attribution indicators

3. **CORRELATE WITH HISTORY**: Use historical context to:
   - Identify similar attack patterns
   - Apply lessons learned
   - Avoid previous mistakes
   - Leverage successful responses

4. **BUSINESS IMPACT**: Assess:
   - Systems at risk
   - Data potentially compromised
   - Business operations impact
   - Compliance implications

5. **ACTIONABLE RECOMMENDATIONS**: Provide specific, prioritized actions:
   - Immediate containment steps
   - Investigation procedures
   - Evidence preservation
   - Communication requirements

6. **STRUCTURE FINDINGS**: Use report_detailed_analysis() with proper data types:
   - threat_assessment: must be a dict (e.g., {"severity": "critical", "confidence": 0.9})
   - attack_timeline: must be a list of events
   - attribution_indicators: must be a list
   - lateral_movement_evidence: must be a list
   - data_at_risk: must be a list
   - business_impact: must be a string
   - recommended_actions: must be a list
   - investigation_notes: must be a string

7. **CONCLUDE**: After successfully calling the function, end with "ANALYSIS_COMPLETE - Senior SOC investigation finished"

CRITICAL: You must call report_detailed_analysis() with the correct parameter types before concluding.""",
        tools=[report_detailed_analysis]
    )
    
    # Create multi-layered failsafe termination conditions
    # Primary termination: Normal completion
    normal_completion = TextMentionTermination("ANALYSIS_COMPLETE")
    
    # Failsafe 1: Maximum messages (prevents infinite loops)
    max_messages = MaxMessageTermination(20)  # Increased to allow for tool call retries
    
    # Failsafe 2: Token usage limit (prevents excessive API costs)
    token_limit = TokenUsageTermination(max_total_token=50000)
    
    # Failsafe 3: Timeout (prevents hanging processes)
    timeout = TimeoutTermination(timeout_seconds=300)  # 5 minutes max
    
    # Failsafe 4: Final analyst completion (alternative success condition)
    analyst_completion = SourceMatchTermination("SeniorAnalyst") & FunctionCallTermination("report_detailed_analysis")
    
    # Combine all termination conditions with OR logic
    # Process terminates when ANY condition is met
    termination = (
        normal_completion |           # Best case: normal completion
        analyst_completion |          # Alternative: analyst completes function call
        max_messages |               # Failsafe: too many messages
        token_limit |                # Failsafe: too many tokens
        timeout                      # Failsafe: too much time
    )
    
    # Create team with round-robin order and robust termination
    team = RoundRobinGroupChat(
        [triage_agent, context_agent, analyst_agent],
        termination_condition=termination
    )
    
    return team, model_client

async def get_prioritized_task(log_batch: str) -> tuple[str, dict, dict]:
    """
    Run the SOC team analysis workflow.
    Returns: (full_conversation, structured_findings, chroma_context)
    """
    if agent_logger:
        agent_logger.info("Starting SOC team analysis")
    
    try:
        # Create the team
        team, model_client = await create_soc_team()
        
        # Run the analysis
        task = f"""SECURITY LOG ANALYSIS REQUEST

Please analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

TriageSpecialist: Begin initial triage analysis. Remember to use proper data types in your function calls."""
        
        # Execute team workflow
        result = await team.run(task=task, cancellation_token=CancellationToken())
        
        # Extract results from conversation
        full_conversation = ""
        priority_findings = {}
        detailed_analysis = {}
        chroma_context = {}
        
        if result.messages:
            conversation_parts = []
            
            for msg in result.messages:
                if hasattr(msg, 'source') and hasattr(msg, 'content'):
                    conversation_parts.append(f"[{msg.source}]: {msg.content}")
                    
                    # Look for tool call results in the conversation
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        # Check for tool call results patterns
                        if "status" in msg.content and "priority_identified" in msg.content:
                            try:
                                # Try to extract structured data from tool results
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
        
        # Close model client
        await model_client.close()
        
        if agent_logger:
            agent_logger.info("SOC team analysis completed successfully")
            agent_logger.debug(f"Conversation length: {len(full_conversation)}")
            agent_logger.debug(f"Priority findings extracted: {bool(priority_findings)}")
            agent_logger.debug(f"Chroma context available: {bool(chroma_context)}")
            agent_logger.debug(f"Detailed analysis available: {bool(detailed_analysis)}")
            agent_logger.debug(f"Total messages in conversation: {len(result.messages) if result.messages else 0}")
            
            # Log termination reason for debugging
            if hasattr(result, 'stop_reason'):
                agent_logger.info(f"Team terminated due to: {result.stop_reason}")
            elif "ANALYSIS_COMPLETE" in full_conversation:
                agent_logger.info("Team terminated: Normal completion detected")
            elif len(result.messages) >= 20:
                agent_logger.warning("Team terminated: Maximum message limit reached")
            else:
                agent_logger.info("Team terminated: Unknown reason")
        
        # Combine findings for return
        combined_findings = {
            "priority_threat": priority_findings,
            "detailed_analysis": detailed_analysis,
            "team_conversation": full_conversation
        }
        
        return full_conversation, combined_findings, chroma_context
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"SOC team analysis error: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        
        error_msg = f"Team analysis error: {str(e)}"
        return error_msg, {}, {"error": str(e)}