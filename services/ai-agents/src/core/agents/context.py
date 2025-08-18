from core.agents.base import BaseAgent
from autogen_core.tools import FunctionTool
from core.services.analysis_service import search_historical_incidents

class ContextAgent(BaseAgent):
    def __init__(self, model_client):
        context_tool = FunctionTool(
            search_historical_incidents,
            description="Search historical incidents in ChromaDB",
            strict=True
        )
        context_tools = [context_tool]

        system_message = """You are a SOC Context Research Specialist. Your role is to:

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

You are the bridge between initial triage and deep analysis."""

        super().__init__(
            name="ContextAgent",
            model_client=model_client,
            system_message=system_message,
            tools=context_tools
        )
