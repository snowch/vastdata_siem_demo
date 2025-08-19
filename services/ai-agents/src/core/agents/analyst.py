# Updated analyst.py - Only responds after context approval
from core.agents.base import BaseAgent
from core.models.analysis import SOCAnalysisResult
from autogen_core.tools import FunctionTool
from core.models.analysis import Timeline, DetailedAnalysis, AttackEvent, ThreatAssessment
from typing import List, Dict, Any, Literal
import logging

agent_logger = logging.getLogger("agent_diagnostics")

def report_detailed_analysis(
    threat_severity: Literal["critical", "high", "medium", "low"],
    threat_confidence: float,
    threat_type_detailed: str,
    attack_timeline: List[Dict[str, str]],
    attribution_indicators: List[str],
    lateral_movement_evidence: List[str],
    data_at_risk: List[str],
    business_impact: str,
    recommended_actions: List[str],
    investigation_notes: str
) -> Dict[str, Any]:
    try:
        timeline_events = []
        for event in attack_timeline:
            if isinstance(event, dict):
                timeline_event = AttackEvent(
                    timestamp=event.get("timestamp", "unknown"),
                    event_type=event.get("event_type", "unknown"),
                    description=event.get("description", "No description"),
                    severity=event.get("severity", "medium")
                )
                timeline_events.append(timeline_event)
        threat_assessment = ThreatAssessment(
            severity=threat_severity,
            confidence=float(threat_confidence),
            threat_type=threat_type_detailed
        )
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
        agent_logger.info(f"Detailed analysis validated: {len(recommended_actions)} recommendations generated")
        return {"status": "analysis_complete", "data": validated_analysis.model_dump()}
    except Exception as e:
        agent_logger.error(f"Detailed analysis validation error: {e}")
        return {"status": "validation_error", "error": str(e)}


class AnalystAgent(BaseAgent):
    def __init__(self, model_client):
        
         analysis_tool = FunctionTool(
            report_detailed_analysis,
            description="Report detailed analysis results",
            strict=True
         )

         system_message = """You are a Senior SOC Analyst. Your role is to:

1. **WAIT FOR CONTEXT**: Only begin when you receive approved context from ContextAgent
2. **DEEP ANALYSIS**: Perform comprehensive investigation:
   - Timeline reconstruction with specific timestamps
   - Attack progression analysis step-by-step
   - Lateral movement assessment and potential paths
   - Data impact evaluation and risk assessment
   - Attribution indicators and TTPs

3. **CORRELATE WITH HISTORY**: Use validated historical context to:
   - Identify similar attack patterns and outcomes
   - Apply lessons learned from past incidents
   - Avoid previous mistakes and blind spots
   - Leverage successful response strategies

4. **BUSINESS IMPACT**: Assess:
   - Systems at risk and criticality levels
   - Data potentially compromised and sensitivity
   - Business operations impact and downtime risk
   - Compliance implications and reporting requirements

5. **CALL FUNCTION**: Use report_detailed_analysis() with EXACT parameter types:
   - threat_severity: MUST be one of: "critical", "high", "medium", "low"
   - threat_confidence: float between 0.0 and 1.0
   - threat_type_detailed: string describing the threat type
   - attack_timeline: List[Dict[str, str]] where each dict has keys: "timestamp", "event_type", "description", "severity"
   - attribution_indicators: List[str]
   - lateral_movement_evidence: List[str]
   - data_at_risk: List[str]
   - business_impact: string describing business impact
   - recommended_actions: List[str] - specific, actionable steps
   - investigation_notes: string with additional notes

6. **REQUEST AUTHORIZATION**: After analysis, present recommendations:
   - "Based on my analysis, I recommend the following actions:"
   - "IMMEDIATE (within 1 hour): {immediate actions}"
   - "SHORT-TERM (within 24 hours): {short-term actions}"  
   - "LONG-TERM (within 1 week): {long-term actions}"
   - "MultiStageApprovalAgent: Do you authorize these recommendations? Any modifications needed?"

7. **WAIT FOR RESPONSE**: Stop and wait for authorization before concluding

8. **CONCLUDE**: After receiving authorization, end with "SOC investigation completed with authorized actions"

IMPORTANT: Do not start until you see approved context research. Look for messages indicating context validation.

CRITICAL: You must call report_detailed_analysis() and request authorization before concluding."""

         super().__init__(
            name="SeniorAnalystSpecialist",
            model_client=model_client,
            system_message=system_message,
            tools=[analysis_tool],
            output_content_type=SOCAnalysisResult
         )