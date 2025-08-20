# services/ai-agents/src/core/agents/context.py - COMPLETE UPDATED VERSION
from core.agents.base import BaseAgent
from core.models.analysis import ContextResearchResult
from autogen_core.tools import FunctionTool
from infrastructure.vectordb_utils import search_chroma
import logging
from typing import List, Dict, Any
from datetime import datetime

agent_logger = logging.getLogger("agent_diagnostics")

def analyze_historical_incidents(
    primary_search_query: str,
    max_results_per_search: int,
    threat_type: str,
    source_ip: str
) -> Dict[str, Any]:
    """
    Analyze historical security incidents and return structured domain results.
    This function handles the ChromaDB search internally and processes results.
    """
    try:
        agent_logger.info(f"Starting historical incident analysis for: {primary_search_query}")
        
        # Perform multiple targeted searches for comprehensive analysis
        search_queries = [primary_search_query]
        
        # Add specific searches based on threat context (checks for non-empty strings)
        if threat_type and threat_type.strip():
            search_queries.append(f"threat type {threat_type}")
        if source_ip and source_ip.strip():
            search_queries.append(f"source ip {source_ip}")
        
        # Additional common security search patterns
        search_queries.extend([
            "brute force attack patterns",
            "lateral movement indicators", 
            "privilege escalation"
        ])
        
        all_documents = []
        all_distances = []
        search_results_summary = []
        
        # Execute searches and collect results
        for query in search_queries[:3]:  # Limit to 3 searches to avoid overload
            try:
                agent_logger.info(f"Executing search: {query}")
                results = search_chroma(query, n_results=max_results_per_search)
                
                documents = results.get('documents', [[]])[0]  # ChromaDB returns nested lists
                distances = results.get('distances', [[]])[0]
                
                if documents:
                    all_documents.extend(documents)
                    all_distances.extend(distances)
                    search_results_summary.append({
                        "query": query,
                        "results_count": len(documents),
                        "avg_relevance": sum(distances) / len(distances) if distances else 0
                    })
                    agent_logger.info(f"Search '{query}' returned {len(documents)} documents")
                else:
                    agent_logger.info(f"Search '{query}' returned no results")
                    
            except Exception as search_error:
                agent_logger.error(f"Search failed for query '{query}': {search_error}")
                continue
        
        # Analyze the collected documents for security patterns
        analysis_result = _analyze_security_patterns(all_documents, all_distances, threat_type)
        
        # Build structured domain result
        domain_result = {
            "total_documents_found": len(all_documents),
            "search_queries_executed": [summary["query"] for summary in search_results_summary],
            "search_effectiveness": search_results_summary,
            "pattern_analysis": analysis_result["pattern_summary"],
            "threat_correlations": analysis_result["correlations"],
            "attack_progression_insights": analysis_result["attack_patterns"],
            "recommended_actions": analysis_result["recommendations"],
            "confidence_assessment": analysis_result["confidence"],
            "historical_timeline": analysis_result["timeline_insights"],
            "related_incidents": all_documents[:5],  # Include top 5 most relevant
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        agent_logger.info(f"✅ Historical analysis complete: {len(all_documents)} documents analyzed")
        print(f"🔍 CONTEXT ANALYSIS: Found {len(all_documents)} related incidents")
        
        return {"status": "analysis_complete", "data": domain_result}
        
    except Exception as e:
        agent_logger.error(f"Historical incident analysis error: {e}")
        print(f"❌ CONTEXT ANALYSIS ERROR: {e}")
        return {"status": "analysis_failed", "error": str(e)}

def _analyze_security_patterns(documents: List[str], distances: List[float], threat_type: str) -> Dict[str, Any]:
    """
    Analyze historical documents for security patterns and insights.
    This is where the domain expertise lives.
    """
    if not documents:
        return {
            "pattern_summary": "No historical incidents found for analysis",
            "correlations": [],
            "attack_patterns": [],
            "recommendations": ["Treat as novel threat - implement enhanced monitoring"],
            "confidence": "low",
            "timeline_insights": "No historical timeline available"
        }
    
    # Analyze document content for security patterns
    common_indicators = []
    attack_techniques = []
    affected_systems = []
    
    for doc in documents:
        doc_lower = doc.lower()
        
        # Extract security indicators
        if 'brute force' in doc_lower or 'password attack' in doc_lower:
            common_indicators.append('credential attacks')
        if 'lateral movement' in doc_lower:
            common_indicators.append('lateral movement')
        if 'privilege escalation' in doc_lower:
            common_indicators.append('privilege escalation')
        if 'data exfiltration' in doc_lower:
            common_indicators.append('data exfiltration')
            
        # Extract attack techniques
        if 'ssh' in doc_lower:
            attack_techniques.append('SSH exploitation')
        if 'rdp' in doc_lower:
            attack_techniques.append('RDP attacks')
        if 'powershell' in doc_lower:
            attack_techniques.append('PowerShell abuse')
            
        # Extract affected systems
        if 'windows' in doc_lower:
            affected_systems.append('Windows systems')
        if 'linux' in doc_lower:
            affected_systems.append('Linux systems')
        if 'server' in doc_lower:
            affected_systems.append('Server infrastructure')
    
    # Calculate confidence based on relevance scores
    avg_distance = sum(distances) / len(distances) if distances else 1.0
    confidence = "high" if avg_distance < 0.3 else "medium" if avg_distance < 0.7 else "low"
    
    # Generate pattern summary
    if common_indicators:
        most_common = max(set(common_indicators), key=common_indicators.count)
        pattern_summary = f"Historical incidents show pattern of {most_common} with {common_indicators.count(most_common)} similar cases"
    else:
        pattern_summary = "Mixed attack patterns identified in historical incidents"
    
    # Generate correlations
    correlations = []
    if len(set(attack_techniques)) > 1:
        correlations.append(f"Multiple attack vectors observed: {', '.join(set(attack_techniques))}")
    if len(set(affected_systems)) > 1:
        correlations.append(f"Cross-platform targeting: {', '.join(set(affected_systems))}")
    
    # Generate attack progression insights
    attack_patterns = []
    if 'credential attacks' in common_indicators and 'lateral movement' in common_indicators:
        attack_patterns.append("Typical progression: Initial access → Credential harvesting → Lateral movement")
    if 'privilege escalation' in common_indicators:
        attack_patterns.append("Attackers typically attempt privilege escalation after initial compromise")
    
    # Generate recommendations based on patterns
    recommendations = []
    if 'credential attacks' in common_indicators:
        recommendations.append("Implement multi-factor authentication and account lockout policies")
    if 'lateral movement' in common_indicators:
        recommendations.append("Deploy network segmentation and lateral movement detection")
    if 'privilege escalation' in common_indicators:
        recommendations.append("Review and restrict administrative privileges")
    if not recommendations:
        recommendations.append("Monitor for indicators identified in similar historical incidents")
    
    # Timeline insights
    timeline_insights = f"Based on {len(documents)} historical incidents spanning multiple timeframes"
    
    return {
        "pattern_summary": pattern_summary,
        "correlations": correlations,
        "attack_patterns": attack_patterns,
        "recommendations": recommendations,
        "confidence": confidence,
        "timeline_insights": timeline_insights
    }

class ContextAgent(BaseAgent):
    def __init__(self, model_client):
        
        # Use the domain-focused analysis function
        context_tool = FunctionTool(
            analyze_historical_incidents,
            description="Analyze historical security incidents and return structured domain insights",
            strict=True  # Strict mode is required for auto-parsing
        )

        system_message = """You are a SOC Historical Context Research Specialist. Your role is to:

1. **WAIT FOR HANDOFF**: Only begin when you receive approval from TriageSpecialist findings.

2. **ANALYZE HISTORICAL INCIDENTS**: Use analyze_historical_incidents() to perform comprehensive security context analysis:
   - primary_search_query: Main search term based on the threat (REQUIRED)
   - max_results_per_search: Number of results per search (recommend 5-10) (REQUIRED)
   - threat_type: Specific threat type. Pass an empty string "" if not identified. (REQUIRED)
   - source_ip: Source IP. Pass an empty string "" if not available. (REQUIRED)

3. **COMPREHENSIVE ANALYSIS**: The function performs multiple searches and analyzes results for:
   - Security pattern identification
   - Threat correlations and attack progressions
   - Historical attack outcomes and lessons learned
   - Cross-incident analysis and trend identification

4. **DOMAIN EXPERTISE**: Focus on security-relevant insights:
   - How similar attacks typically progress
   - What defensive measures were effective/ineffective
   - Common attack vectors and techniques used
   - Business impact patterns from historical incidents

5. **STRUCTURED OUTPUT**: The function returns a complete ContextResearchResult with:
   - Pattern analysis and threat correlations
   - Attack progression insights from historical data
   - Actionable recommendations based on past incidents
   - Confidence assessment of the analysis

6. **MANDATORY APPROVAL REQUEST**: After completing analysis, you MUST present findings AND request validation:
   - First, summarize your findings professionally
   - Then, you MUST end with this EXACT phrase: "MultiStageApprovalAgent: Based on my analysis of {X} historical incidents, are these insights relevant for the current threat analysis? Should we proceed with deep security analysis using this context?"
   - Replace {X} with the actual number of incidents found
   - This is MANDATORY - the workflow depends on this exact request format

7. **WAIT FOR RESPONSE**: Stop and wait for validation before any further action.

CRITICAL REQUIREMENTS:
- Call analyze_historical_incidents() ONCE with comprehensive parameters
- Focus on SECURITY DOMAIN insights, not technical ChromaDB details
- Provide clear, actionable intelligence based on historical incident patterns
- ALWAYS request approval with the exact phrase format shown above
- Wait for explicit approval before concluding

Example completion format:
"I analyzed 24 historical security incidents and found patterns of credential attacks with lateral movement. Key findings include multiple attack vectors and cross-platform targeting. Based on similar incidents, I recommend implementing multi-factor authentication and network segmentation.

MultiStageApprovalAgent: Based on my analysis of 24 historical incidents, are these insights relevant for the current threat analysis? Should we proceed with deep security analysis using this context?"
"""

        super().__init__(
            name="ContextAgent",
            model_client=model_client,
            system_message=system_message,
            tools=[context_tool],
            output_content_type=ContextResearchResult
        )
        
        agent_logger.info("ContextAgent initialized with mandatory approval request")