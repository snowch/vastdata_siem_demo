# Updated context.py - Only responds after approval
from core.agents.base import BaseAgent
from autogen_core.tools import FunctionTool
from infrastructure.vectordb_utils import search_chroma
import logging
from typing import List, Dict, Any, Literal

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


class ContextAgent(BaseAgent):
   def __init__(self, model_client):

      context_tool = FunctionTool(
         search_historical_incidents,
         description="Search historical incidents in ChromaDB",
         strict=True
      )

      system_message = """You are a SOC Context Research Specialist. Your role is to:

1. **WAIT FOR HANDOFF**: Only begin when you receive approval from TriageSpecialist findings
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
   - Timeline patterns and escalation paths

6. **REQUEST VALIDATION**: After completing searches, present findings:
   - "I found {count} similar incidents from the past {timeframe}"
   - "Key patterns include: {summarized patterns}"
   - "These incidents typically: {common outcomes}"
   - "MultiStageApprovalAgent: Are these historical incidents relevant to the current analysis? Should we proceed with deep analysis using this context?"

7. **WAIT FOR RESPONSE**: Stop and wait for validation before any further action

IMPORTANT: Do not start until you see an approved triage finding. Look for messages indicating approval to proceed."""

      super().__init__(
         name="ContextAgent",
         model_client=model_client,
         system_message=system_message,
         tools=[context_tool]
      )
