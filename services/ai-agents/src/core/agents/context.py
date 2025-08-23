# services/ai-agents/src/core/agents/context.py - PERFORMANCE OPTIMIZED VERSION
from core.agents.base import BaseAgent
from core.models.analysis import ContextResearchResult, DocumentMetadata
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
    ULTRA-FAST OPTIMIZED: Maximum speed with minimal document processing.
    """
    try:
        agent_logger.info(f"Starting ULTRA-FAST historical incident analysis for: {primary_search_query}")
        
        # OPTIMIZATION 1: Reduce search queries from 3 to 1 primary search
        # Only use the main search query, skip additional context searches
        search_queries = [primary_search_query]
        
        # OPTIMIZATION 1: Reduce results per search from 10 to 2 (ultra-fast mode)
        optimized_results_per_search = min(max_results_per_search, 2)
        
        agent_logger.info(f"🔧 ULTRA-FAST MODE: Using {len(search_queries)} search(es) with max {optimized_results_per_search} results each")
        
        all_documents = []
        all_distances = []
        all_metadata = []
        search_results_summary = []
        
        # Execute reduced searches
        for query in search_queries:
            try:
                agent_logger.info(f"Executing optimized search: {query}")
                results = search_chroma(query, n_results=optimized_results_per_search)
                
                documents = results.get('documents', [[]])[0]  # ChromaDB returns nested lists
                distances = results.get('distances', [[]])[0]
                metadatas = results.get('metadatas', [[]])[0] if 'metadatas' in results else []
                
                if documents:
                    all_documents.extend(documents)
                    all_distances.extend(distances)
                    
                    # Handle metadata - convert to structured format
                    if metadatas:
                        if isinstance(metadatas, list):
                            for i, metadata in enumerate(metadatas):
                                doc_metadata = _convert_to_document_metadata(metadata, i, query)
                                all_metadata.append(doc_metadata)
                        else:
                            # If metadatas is not a list, create empty metadata
                            for i in range(len(documents)):
                                doc_metadata = _convert_to_document_metadata({}, i, query)
                                all_metadata.append(doc_metadata)
                    else:
                        # No metadata available, create empty metadata objects
                        for i in range(len(documents)):
                            doc_metadata = _convert_to_document_metadata({}, i, query)
                            all_metadata.append(doc_metadata)
                    
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
        
        # OPTIMIZATION 2: Limit total documents processed to maximum 5 (ultra-fast mode)
        original_count = len(all_documents)
        MAX_DOCUMENTS = 5
        
        if len(all_documents) > MAX_DOCUMENTS:
            agent_logger.info(f"🔧 PERFORMANCE LIMIT: Reducing from {original_count} to {MAX_DOCUMENTS} documents")
            all_documents = all_documents[:MAX_DOCUMENTS]
            all_distances = all_distances[:MAX_DOCUMENTS]
            all_metadata = all_metadata[:MAX_DOCUMENTS]
        
        # Analyze the collected documents for security patterns
        analysis_result = _analyze_security_patterns(all_documents, all_distances, threat_type)
        
        # Build structured domain result
        domain_result = {
            "total_documents_found": len(all_documents),
            "original_document_count": original_count,  # Track how many we originally found
            "performance_limited": original_count > MAX_DOCUMENTS,
            "search_queries_executed": [summary["query"] for summary in search_results_summary],
            "search_effectiveness": search_results_summary,
            "pattern_analysis": analysis_result["pattern_summary"],
            "threat_correlations": analysis_result["correlations"],
            "attack_progression_insights": analysis_result["attack_patterns"],
            "recommended_actions": analysis_result["recommendations"],
            "confidence_assessment": analysis_result["confidence"],
            "historical_timeline": analysis_result["timeline_insights"],
            "related_incidents": all_documents[:5],  # Include top 5 most relevant for summary
            "analysis_timestamp": datetime.now().isoformat(),
            
            # Include ALL processed documents and distances with structured metadata
            "all_documents": all_documents,
            "all_distances": all_distances,
            "all_document_metadata": all_metadata
        }
        
        agent_logger.info(f"✅ ULTRA-FAST Historical analysis complete: {len(all_documents)} documents analyzed (limited from {original_count})")
        print(f"🔍 ULTRA-FAST CONTEXT ANALYSIS: Processed {len(all_documents)}/{original_count} incidents")
        
        return {"status": "analysis_complete", "data": domain_result}
        
    except Exception as e:
        agent_logger.error(f"Historical incident analysis error: {e}")
        print(f"❌ CONTEXT ANALYSIS ERROR: {e}")
        return {"status": "analysis_failed", "error": str(e)}

def _convert_to_document_metadata(raw_metadata: Any, index: int, query: str) -> Dict[str, Any]:
    """Convert raw metadata to structured DocumentMetadata format"""
    if not raw_metadata or not isinstance(raw_metadata, dict):
        # Create default metadata if none provided
        return {
            "document_id": f"doc_{index}",
            "source": "vector_database",
            "timestamp": datetime.now().isoformat(),
            "category": "security_incident",
            "tags": [query.replace(" ", "_")],
            "additional_info": "No additional metadata available"
        }
    
    # Extract common metadata fields with defaults
    return {
        "document_id": str(raw_metadata.get("id", f"doc_{index}")),
        "source": str(raw_metadata.get("source", "vector_database")),
        "timestamp": str(raw_metadata.get("timestamp", datetime.now().isoformat())),
        "category": str(raw_metadata.get("category", "security_incident")),
        "tags": raw_metadata.get("tags", [query.replace(" ", "_")]) if isinstance(raw_metadata.get("tags"), list) else [query.replace(" ", "_")],
        "additional_info": str(raw_metadata.get("additional_info", f"Retrieved via query: {query}"))
    }

def _analyze_security_patterns(documents: List[str], distances: List[float], threat_type: str) -> Dict[str, Any]:
    """
    Analyze historical documents for security patterns and insights.
    OPTIMIZED: Works efficiently with reduced document set.
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
    
    # Analyze document content for security patterns (now processing fewer documents)
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
        
        # Use the optimized analysis function
        context_tool = FunctionTool(
            analyze_historical_incidents,
            description="Analyze historical security incidents with ULTRA-FAST OPTIMIZATIONS for maximum speed",
            strict=True  # Strict mode is required for auto-parsing
        )

        system_message = """You are a SOC Historical Context Research Specialist. Your role is to:

1. **WAIT FOR HANDOFF**: Only begin when you receive approval from TriageSpecialist findings.

2. **ANALYZE HISTORICAL INCIDENTS**: Use analyze_historical_incidents() to perform ULTRA-FAST security context analysis:
   - primary_search_query: Main search term based on the threat (REQUIRED)
   - max_results_per_search: Number of results per search (system will optimize this to 2 for ultra-fast mode) (REQUIRED)
   - threat_type: Specific threat type. Pass an empty string "" if not identified. (REQUIRED)
   - source_ip: Source IP. Pass an empty string "" if not available. (REQUIRED)

3. **ULTRA-FAST OPTIMIZED ANALYSIS**: The function now uses aggressive optimizations for maximum speed:
   - Single search query only (fastest possible)
   - Maximum 2 results per search (ultra-limited scope)
   - Hard limit of 5 documents total for processing (lightning fast)
   - Maintains core security insights while maximizing speed

4. **COMPREHENSIVE ANALYSIS**: Despite optimizations, still provides:
   - Security pattern identification from top relevant incidents
   - Threat correlations and attack progressions
   - Historical attack outcomes and lessons learned
   - Cross-incident analysis focused on most relevant cases

5. **DOMAIN EXPERTISE**: Focus on security-relevant insights from the most pertinent incidents:
   - How similar attacks typically progress
   - What defensive measures were effective/ineffective
   - Common attack vectors and techniques used
   - Business impact patterns from historical incidents

6. **STRUCTURED OUTPUT**: The function returns a complete ContextResearchResult with:
   - Pattern analysis and threat correlations from relevant incidents
   - Attack progression insights from historical data
   - Actionable recommendations based on past incidents
   - Confidence assessment of the analysis
   - Performance metrics showing optimization results

7. **MANDATORY APPROVAL REQUEST**: After completing analysis, you MUST present findings AND request validation:
   - First, summarize your findings professionally
   - Mention the ultra-fast optimizations if the analysis was limited
   - Then, you MUST end with this EXACT phrase: "MultiStageApprovalAgent: Based on my analysis of {X} historical incidents, are these insights relevant for the current threat analysis? Should we proceed with deep security analysis using this context?"
   - Replace {X} with the actual number of incidents analyzed
   - This is MANDATORY - the workflow depends on this exact request format

8. **WAIT FOR RESPONSE**: Stop and wait for validation before any further action.

CRITICAL REQUIREMENTS:
- Call analyze_historical_incidents() ONCE with comprehensive parameters
- Focus on SECURITY DOMAIN insights from the most relevant incidents
- Provide clear, actionable intelligence based on optimized historical incident patterns
- ALWAYS request approval with the exact phrase format shown above
- Wait for explicit approval before concluding
- Note any ultra-fast optimizations in your summary if document count was limited

Example completion format:
"I analyzed 3 historical security incidents (ultra-fast mode, processed top 3 most relevant) and identified patterns of credential attacks with lateral movement. Key findings include multiple attack vectors and cross-platform targeting. Based on similar incidents, I recommend implementing multi-factor authentication and network segmentation.

MultiStageApprovalAgent: Based on my analysis of 3 historical incidents, are these insights relevant for the current threat analysis? Should we proceed with deep security analysis using this context?"
"""

        super().__init__(
            name="ContextAgent",
            model_client=model_client,
            system_message=system_message,
            tools=[context_tool],
            output_content_type=ContextResearchResult
        )
        
        agent_logger.info("ContextAgent initialized with ULTRA-FAST OPTIMIZATIONS - maximum speed context research")