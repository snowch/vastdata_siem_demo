import asyncio
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseAgentEvent, ToolCallRequestEvent, ToolCallExecutionEvent, StructuredMessage
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
import json
import logging
import traceback
from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME
from vectordb_utils import search_chroma
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field

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

# Structured output models
class Timeline(BaseModel):
    start: str = Field(description="Timeline start time")
    end: str = Field(description="Timeline end time")

class ThreatAssessment(BaseModel):
    severity: Literal["critical", "high", "medium", "low"] = Field(description="Threat severity level")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    threat_type: str = Field(description="Type of threat identified")

class AttackEvent(BaseModel):
    timestamp: str = Field(description="Event timestamp")
    event_type: str = Field(description="Type of attack event")
    description: str = Field(description="Event description")
    severity: Literal["critical", "high", "medium", "low"] = Field(description="Event severity")

class PriorityFindings(BaseModel):
    priority: Literal["critical", "high", "medium", "low"] = Field(description="Priority level")
    threat_type: str = Field(description="Type of threat")
    source_ip: str = Field(description="Source IP address")
    target_hosts: List[str] = Field(default_factory=list, description="List of target hosts")
    attack_pattern: str = Field(description="Observed attack pattern")
    timeline: Timeline = Field(description="Attack timeline")
    indicators: List[str] = Field(default_factory=list, description="List of indicators")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score")
    event_count: int = Field(ge=1, description="Number of events")
    affected_services: List[str] = Field(default_factory=list, description="List of affected services")
    brief_summary: str = Field(description="Brief summary of findings")

class DetailedAnalysis(BaseModel):
    threat_assessment: ThreatAssessment = Field(description="Detailed threat assessment")
    attack_timeline: List[AttackEvent] = Field(default_factory=list, description="Chronological attack timeline")
    attribution_indicators: List[str] = Field(default_factory=list, description="Attribution indicators")
    lateral_movement_evidence: List[str] = Field(default_factory=list, description="Evidence of lateral movement")
    data_at_risk: List[str] = Field(default_factory=list, description="Data at risk")
    business_impact: str = Field(description="Business impact assessment")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")
    investigation_notes: str = Field(description="Investigation notes")

class SOCAnalysisResult(BaseModel):
    """Final structured output for SOC analysis"""
    executive_summary: str = Field(description="Executive summary of the analysis")
    priority_findings: PriorityFindings = Field(description="Priority threat findings")
    detailed_analysis: DetailedAnalysis = Field(description="Detailed analysis results")
    historical_context: str = Field(description="Historical context from similar incidents")
    confidence_level: Literal["high", "medium", "low"] = Field(description="Overall confidence in analysis")
    analyst_notes: str = Field(description="Additional analyst notes and observations")

# Enhanced tool functions with strict mode compatibility
def _report_priority_findings(
    priority: Literal["critical", "high", "medium", "low"],
    threat_type: str,
    source_ip: str,
    target_hosts: List[str],
    attack_pattern: str,
    timeline_start: str,
    timeline_end: str,
    indicators: List[str],
    confidence_score: float,
    event_count: int,
    affected_services: List[str],
    brief_summary: str
) -> Dict[str, Any]:
    """Function for initial triage to report the highest priority threat found."""
    
    # Validate and convert data to proper types
    try:        
        # Validate using Pydantic model
        timeline = Timeline(start=timeline_start, end=timeline_end)
        validated_findings = PriorityFindings(
            priority=priority,
            threat_type=threat_type,
            source_ip=source_ip,
            target_hosts=target_hosts,
            attack_pattern=attack_pattern,
            timeline=timeline,
            indicators=indicators,
            confidence_score=confidence_score,
            event_count=event_count,
            affected_services=affected_services,
            brief_summary=brief_summary
        )
        
        if agent_logger:
            agent_logger.info(f"Priority findings validated: {validated_findings.threat_type} from {validated_findings.source_ip}")
        
        return {"status": "priority_identified", "data": validated_findings.model_dump()}
    
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"Priority findings validation error: {e}")
        return {"status": "validation_error", "error": str(e)}

def _search_historical_incidents(search_query: str, max_results: int) -> Dict[str, Any]:
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

def _report_detailed_analysis(
    threat_severity: Literal["critical", "high", "medium", "low"],
    threat_confidence: float,
    threat_type_detailed: str,
    attack_timeline: List[Dict[str, str]],  # More specific typing
    attribution_indicators: List[str],
    lateral_movement_evidence: List[str],
    data_at_risk: List[str],
    business_impact: str,
    recommended_actions: List[str],
    investigation_notes: str
) -> Dict[str, Any]:
    """Function for detailed analysis after ChromaDB context enrichment."""
    try:
        # Validate and convert attack timeline
        timeline_events = []
        for event in attack_timeline:
            if isinstance(event, dict):
                # Ensure required fields exist with defaults
                timeline_event = AttackEvent(
                    timestamp=event.get("timestamp", "unknown"),
                    event_type=event.get("event_type", "unknown"),
                    description=event.get("description", "No description"),
                    severity=event.get("severity", "medium")
                )
                timeline_events.append(timeline_event)
        
        # Create threat assessment
        threat_assessment = ThreatAssessment(
            severity=threat_severity,
            confidence=float(threat_confidence),
            threat_type=threat_type_detailed
        )
        
        # Validate using Pydantic model
        validated_analysis = DetailedAnalysis(
            threat_assessment=threat_assessment,
            attack_timeline=timeline_events,
            attribution_indicators=attribution_indicators,
            lateral_movement_evidence=lateral_movement_evidence,
            data_at_risk=data_at_risk,
            business_impact=business_impact,
            recommended_actions=recommended_actions,
            investigation_notes=investigation_notes
        )
        
        if agent_logger:
            agent_logger.info(f"Detailed analysis validated: {len(recommended_actions)} recommendations generated")
        
        return {"status": "analysis_complete", "data": validated_analysis.model_dump()}
    
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"Detailed analysis validation error: {e}")
        return {"status": "validation_error", "error": str(e)}

async def _create_soc_team(use_structured_output: bool = False):
    """Create the SOC analysis team with specialized agents."""
    model_client = OpenAIChatCompletionClient(model="gpt-4o", parallel_tool_calls=False)
    
    if use_structured_output:
        # Create strict function tools - required when using structured output
        # priority_tool = FunctionTool(
        #     report_priority_findings, 
        #     description="Report priority threat findings from initial triage",
        #     strict=True
        # )
        
        search_tool = FunctionTool(
            _search_historical_incidents,
            description="Search historical incidents in ChromaDB",
            strict=True
        )
        
        analysis_tool = FunctionTool(
            _report_detailed_analysis,
            description="Report detailed analysis results",
            strict=True
        )
        
        # triage_tools = [priority_tool]
        context_tools = [search_tool] 
        analysis_tools = [analysis_tool]
        analyst_output_type = SOCAnalysisResult
    else:
        # Use regular function tools for better reliability
        # triage_tools = [report_priority_findings]
        context_tools = [_search_historical_incidents]
        analysis_tools = [_report_detailed_analysis]
        analyst_output_type = None

    priority_tool = FunctionTool(
        _report_priority_findings, 
        description="Report priority threat findings from initial triage",
        strict=True
    )
    triage_tools = [priority_tool]
    
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

5. **CALL FUNCTION**: Use report_priority_findings() with EXACT parameter types:
   - priority: MUST be one of: "critical", "high", "medium", "low"
   - target_hosts: List[str] - e.g., ["192.168.1.100", "server01"]
   - indicators: List[str] - e.g., ["failed_logins", "privilege_escalation"]
   - affected_services: List[str] - e.g., ["ssh", "rdp", "web_server"]
   - confidence_score: float - e.g., 0.85 (between 0.0 and 1.0)
   - event_count: int - e.g., 15

6. **HAND OFF**: After successfully calling the function, say "CONTEXT_AGENT please search for similar historical incidents" and provide the key search terms.

Focus ONLY on initial triage. Don't do deep analysis - that's for later agents.""",
        tools=[triage_tools[0]]
    )
    
    # Agent 2: Context Research Specialist  
    context_agent = AssistantAgent(
        name="ContextAgent", 
        model_client=model_client,
        system_message="""You are a SOC Context Research Specialist. Your role is to:

1. **RECEIVE HANDOFF**: Wait for TriageSpecialist to identify priority threat
2. **SEARCH HISTORICAL DATA**: Use search_historical_incidents() to find similar past incidents
   - search_query: string describing what to search for
   - max_results: integer (must provide - no default, recommend 5-10)

3. **BUILD SEARCH QUERIES**: Create effective searches using:
   - Threat type (brute_force_attack, lateral_movement, etc.)
   - Attack patterns (ssh_login_failure, privilege_escalation, etc.) 
   - Source IPs, affected services
   - Priority levels

4. **MULTIPLE SEARCHES**: Perform 2-3 different searches to get comprehensive context:
   - Search by threat type (max_results: 5)
   - Search by attack pattern (max_results: 5)
   - Search by affected services (max_results: 5)

5. **SUMMARIZE CONTEXT**: Provide a clear summary of historical patterns:
   - How similar attacks progressed
   - What indicators were present
   - How they were resolved
   - What worked/didn't work

6. **HAND OFF**: After completing searches, say "ANALYST_AGENT please perform deep analysis with this context" and provide both original findings and historical context.

You are the bridge between initial triage and deep analysis.""",
        tools=[context_tools[0]]
    )
    
    # Agent 3: Senior Analyst with conditional structured output
    analyst_kwargs = {
        "name": "SeniorAnalyst",
        "model_client": model_client,
        "system_message": """You are a Senior SOC Analyst. Your role is to:

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

5. **CALL FUNCTION**: Use report_detailed_analysis() with EXACT parameter types:
   - threat_severity: MUST be one of: "critical", "high", "medium", "low"
   - threat_confidence: float between 0.0 and 1.0
   - attack_timeline: List[Dict[str, str]] where each dict has keys: "timestamp", "event_type", "description", "severity"
   - attribution_indicators: List[str]
   - lateral_movement_evidence: List[str]
   - data_at_risk: List[str]
   - recommended_actions: List[str]

6. **CONCLUDE**: After calling the function, end with "ANALYSIS_COMPLETE - Senior SOC investigation finished"

CRITICAL: You must call report_detailed_analysis() before concluding.""",
        "tools": analysis_tools
    }
    
    # Add structured output only if requested and available
    if analyst_output_type:
        analyst_kwargs["output_content_type"] = analyst_output_type
    
    analyst_agent = AssistantAgent(**analyst_kwargs)
    
    # Create multi-layered failsafe termination conditions
    normal_completion = TextMentionTermination("ANALYSIS_COMPLETE")
    max_messages = MaxMessageTermination(25)  # Increased for structured output
    token_limit = TokenUsageTermination(max_total_token=60000)
    timeout = TimeoutTermination(timeout_seconds=400)  # Increased for structured output
    analyst_completion = SourceMatchTermination("SeniorAnalyst") & FunctionCallTermination("report_detailed_analysis")
    
    termination = (
        normal_completion |
        analyst_completion |
        max_messages |
        token_limit |
        timeout
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
    
    Note: structured_result is embedded in structured_findings if available
    """
    if agent_logger:
        agent_logger.info("Starting SOC team analysis")
    
    try:
        # Create the team
        team, model_client = await _create_soc_team(use_structured_output=False)  # Start with reliable mode
        
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
        structured_result = None
        
        if result.messages:
            conversation_parts = []
            
            for msg in result.messages:
                if hasattr(msg, 'source') and hasattr(msg, 'content'):
                    conversation_parts.append(f"[{msg.source}]: {msg.content}")
                    
                    # Extract structured output from SeniorAnalyst
                    if (msg.source == "SeniorAnalyst" and 
                        isinstance(msg, StructuredMessage) and
                        isinstance(msg.content, SOCAnalysisResult)):
                        structured_result = msg.content
                    
                    # Look for tool call results in the conversation
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        # Check for tool call results patterns
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
        
        # Close model client
        await model_client.close()
        
        if agent_logger:
            agent_logger.info("SOC team analysis completed successfully")
            agent_logger.debug(f"Structured result available: {structured_result is not None}")
        
        # Combine findings for return - include structured result if available
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