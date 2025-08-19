# Updated triage.py - More responsive to initial task
from core.agents.base import BaseAgent
from autogen_core.tools import FunctionTool
from typing import List, Dict, Any, Literal
import json
import logging
from core.models.analysis import Timeline, PriorityFindings

agent_logger = logging.getLogger("agent_diagnostics")

def report_priority_findings(
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
    try:
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
        agent_logger.info(f"Priority findings validated: {validated_findings.threat_type} from {validated_findings.source_ip}")
        return {"status": "priority_identified", "data": validated_findings.model_dump()}
    except Exception as e:
        agent_logger.error(f"Priority findings validation error: {e}")
        return {"status": "validation_error", "error": str(e)}

class TriageAgent(BaseAgent):
    def __init__(self, model_client):
        priority_tool = FunctionTool(
            report_priority_findings,
            description="Report priority threat findings from initial triage",
            strict=True
        )
        triage_tools = [priority_tool]

        system_message = """You are a SOC Triage Specialist. Your role is to:

1. **ANALYZE OCSF LOGS**: Review the provided security log events immediately when you receive them
2. **IDENTIFY TOP PRIORITY**: Find the SINGLE most critical threat requiring immediate attention
3. **PRIORITIZE BY IMPACT**: 
   - Critical: Active attacks, privilege escalation, data exfiltration
   - High: Lateral movement, persistent access, credential compromise
   - Medium: Failed attacks, reconnaissance, suspicious patterns
   - Low: Anomalies requiring monitoring

4. **LOOK FOR PATTERNS**:
   - Multiple failed auth → success (brute force)
   - Unusual process execution
   - Suspicious network connections
   - File access anomalies
   - Privilege escalation attempts

5. **CALL FUNCTION**: Use report_priority_findings() with EXACT parameter types:
   - priority: MUST be one of: "critical", "high", "medium", "low"
   - threat_type: Clear description of the threat (e.g., "brute_force_attack", "privilege_escalation")
   - source_ip: The source IP address
   - target_hosts: List[str] - e.g., ["192.168.1.100", "server01"]
   - attack_pattern: Description of the attack pattern observed
   - timeline_start: Start time of the attack
   - timeline_end: End time or "ongoing"
   - indicators: List[str] - e.g., ["failed_logins", "privilege_escalation"]
   - confidence_score: float - e.g., 0.85 (between 0.0 and 1.0)
   - event_count: int - e.g., 15
   - affected_services: List[str] - e.g., ["ssh", "rdp", "web_server"]
   - brief_summary: Clear summary of findings for approval decision

6. **REQUEST APPROVAL**: After calling the function, provide a detailed summary:
   - "I found a {priority} priority {threat_type} from {source_ip}"
   - "Evidence includes: {key indicators and patterns}"
   - "Potential impact: {business impact assessment}"
   - "MultiStageApprovalAgent: Do you want to proceed with investigating this {priority} priority {threat_type} from {source_ip}?"

7. **WAIT FOR RESPONSE**: Stop and wait for approval before any further action

IMPORTANT: When you receive the initial task with log data, immediately begin your analysis. Do not wait for other agents."""

        super().__init__(
            name="TriageSpecialist",
            model_client=model_client,
            system_message=system_message,
            tools=triage_tools
        )
