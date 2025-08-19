# services/ai-agents/src/core/agents/analyst.py - COMPLETE FIXED VERSION
from core.agents.base import BaseAgent
from core.models.analysis import SOCAnalysisResult
from autogen_core.tools import FunctionTool
from core.models.analysis import Timeline, DetailedAnalysis, AttackEvent, ThreatAssessment
from typing import List, Dict, Any, Literal
import logging
from datetime import datetime

agent_logger = logging.getLogger("agent_diagnostics")

def report_detailed_analysis(
    threat_severity: Literal["critical", "high", "medium", "low"],
    threat_confidence: float,
    threat_type_detailed: str,
    attribution_indicators: List[str],
    lateral_movement_evidence: List[str],
    data_at_risk: List[str],
    business_impact: str,
    recommended_actions: List[str],
    investigation_notes: str
) -> Dict[str, Any]:
    """Report detailed analysis results - FIXED: Removed problematic attack_timeline parameter"""
    try:
        # Create timeline events from the analysis
        current_time = datetime.now().isoformat()
        timeline_events = [
            AttackEvent(
                timestamp=current_time,
                event_type="analysis_initiated",
                description="Deep security analysis initiated",
                severity=threat_severity
            ),
            AttackEvent(
                timestamp=current_time,
                event_type="threat_assessment_complete",
                description=f"Threat assessment completed: {threat_type_detailed}",
                severity=threat_severity
            ),
            AttackEvent(
                timestamp=current_time,
                event_type="recommendations_generated",
                description=f"Generated {len(recommended_actions)} actionable recommendations",
                severity="medium"
            )
        ]
        
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
        
        agent_logger.info(f"✅ ANALYST FUNCTION CALLED - Detailed analysis validated: {len(recommended_actions)} recommendations generated")
        print(f"🔧 ANALYST FUNCTION EXECUTED: {threat_type_detailed} - Severity: {threat_severity} - Actions: {len(recommended_actions)}")
        return {"status": "analysis_complete", "data": validated_analysis.model_dump()}
    except Exception as e:
        agent_logger.error(f"Detailed analysis validation error: {e}")
        print(f"❌ ANALYST FUNCTION ERROR: {e}")
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

5. **CALL FUNCTION IMMEDIATELY**: When analysis is complete, you MUST actually invoke report_detailed_analysis():

report_detailed_analysis(
    threat_severity="critical/high/medium/low",
    threat_confidence=0.95,  # float between 0.0-1.0
    threat_type_detailed="detailed_threat_description",
    attribution_indicators=["indicator1", "indicator2", "indicator3"],
    lateral_movement_evidence=["evidence1", "evidence2"],
    data_at_risk=["sensitive_data1", "system2", "database3"],
    business_impact="clear_business_impact_description",
    recommended_actions=["immediate_action1", "short_term_action2", "long_term_action3"],
    investigation_notes="additional_analysis_notes_and_observations"
)

6. **REQUEST AUTHORIZATION**: After calling the function, present recommendations:
   - "Based on my analysis, I recommend the following actions:"
   - "IMMEDIATE (within 1 hour): {immediate actions}"
   - "SHORT-TERM (within 24 hours): {short-term actions}"  
   - "LONG-TERM (within 1 week): {long-term actions}"
   - "MultiStageApprovalAgent: Do you authorize these recommendations? Any modifications needed?"

7. **WAIT FOR RESPONSE**: Stop and wait for authorization before concluding

8. **CONCLUDE**: After receiving authorization, end with "SOC investigation completed with authorized actions"

⚠️ CRITICAL REQUIREMENTS:
- DO NOT start until you see approved context research
- You MUST CALL report_detailed_analysis() function - do not just describe it
- CALL the function FIRST, then request authorization
- Look for messages indicating context validation before beginning"""

         super().__init__(
            name="SeniorAnalystSpecialist",
            model_client=model_client,
            system_message=system_message,
            tools=[analysis_tool],
            output_content_type=SOCAnalysisResult
         )
         
         print(f"🔧 Analyst agent initialized with {len([analysis_tool])} tools")
         agent_logger.info(f"Analyst agent created with tools: {[analysis_tool.name]}")