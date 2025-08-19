from typing import List, Dict, Any, Literal
import json
import logging
from core.models.analysis import Timeline, DetailedAnalysis, AttackEvent, ThreatAssessment, SOCAnalysisResult
from infrastructure.vectordb_utils import search_chroma

agent_logger = logging.getLogger("agent_diagnostics")

def search_historical_incidents(search_query: str, max_results: int) -> Dict[str, Any]:
    try:
        agent_logger.info(f"Searching ChromaDB with query: {search_query}")
        results = search_chroma(search_query, n_results=max_results)
        agent_logger.info(f"ChromaDB returned {len(results.get('documents', []))} results")
        return {"status": "search_complete", "results": results}
    except Exception as e:
        agent_logger.error(f"ChromaDB search error: {e}")
        return {"status": "search_failed", "error": str(e)}

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
