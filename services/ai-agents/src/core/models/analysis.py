from typing import List, Literal, Optional
from pydantic import BaseModel, Field

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

class SearchEffectiveness(BaseModel):
    query: str = Field(description="Search query executed")
    results_count: int = Field(description="Number of results returned")
    avg_relevance: float = Field(description="Average relevance score")

class ContextResearchResult(BaseModel):
    """Structured domain result for historical security context analysis"""
    total_documents_found: int = Field(description="Total number of historical documents analyzed")
    search_queries_executed: List[str] = Field(description="List of search queries that were executed")
    search_effectiveness: List[SearchEffectiveness] = Field(description="Effectiveness metrics for each search")
    pattern_analysis: str = Field(description="Summary of security patterns identified in historical data")
    threat_correlations: List[str] = Field(description="List of threat correlations found across incidents")
    attack_progression_insights: List[str] = Field(description="Insights about how similar attacks typically progress")
    recommended_actions: List[str] = Field(description="Recommended actions based on historical incident outcomes")
    confidence_assessment: Literal["high", "medium", "low"] = Field(description="Confidence level in the analysis")
    historical_timeline: str = Field(description="Timeline insights from historical incidents")
    related_incidents: List[str] = Field(description="Most relevant historical incident summaries")
    analysis_timestamp: str = Field(description="When this analysis was performed")

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
    context_research: Optional[ContextResearchResult] = Field(None, description="Historical context research results")
    detailed_analysis: DetailedAnalysis = Field(description="Detailed analysis results")
    historical_context: str = Field(description="Historical context from similar incidents")
    confidence_level: Literal["high", "medium", "low"] = Field(description="Overall confidence in analysis")
    analyst_notes: str = Field(description="Additional analyst notes and observations")
    
    # NEW: Explicit workflow completion flags for robust detection
    workflow_complete: bool = Field(
        default=False, 
        description="True when the entire SOC analysis workflow is complete and ready for final review"
    )
    
    completion_timestamp: Optional[str] = Field(
        None, 
        description="ISO timestamp when analysis was completed"
    )
    
    analysis_status: Literal["in_progress", "awaiting_approval", "complete", "requires_review"] = Field(
        default="in_progress",
        description="Current status of the analysis workflow"
    )