import asyncio
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.ui import Console
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from event_reader import get_log_events
import json

# --- Tool Definitions (for the Triage Team) ---
def run_siem_query(query: str) -> str:
    """Executes a search query against the SIEM and returns the results as a JSON string."""
    print(f"--- EXECUTING TOOL: run_siem_query ---")
    print(f"--- QUERY: {query} ---")
    if "198.51.100.10" in query:
        # Return only the logs matching the suspicious IP from our simulated batch
        mock_siem_results = [
            {
                "timestamp": "2024-08-01T00:00:05",
                "event_type": "ssh_login_failure",
                "user_id": "root",
                "source_ip": "198.51.100.10",
                "hostname": "db-server-01"
            },
            {
                "timestamp": "2024-08-01T00:00:10",
                "event_type": "ssh_login_failure",
                "user_id": "root",
                "source_ip": "198.51.100.10",
                "hostname": "db-server-01"
            },
            {
                "timestamp": "2024-08-01T00:00:15",
                "event_type": "ssh_login_failure",
                "user_id": "root",
                "source_ip": "198.51.100.10",
                "hostname": "db-server-01"
            },
            {
                "timestamp": "2024-08-01T00:00:20",
                "event_type": "ssh_login_success",
                "user_id": "admin",
                "source_ip": "198.51.100.10",
                "hostname": "db-server-01"
            }
        ]
        return json.dumps(mock_siem_results, indent=2)
    return json.dumps([])

def enrich_indicator(indicator: str, source: str = "virustotal") -> str:
    """Enriches a given security indicator using a threat intelligence source."""
    if indicator == "198.51.100.10":
        enrichment_data = {
            "indicator": indicator,
            "source": source,
            "is_malicious": True,
            "reputation_score": 85,
            "country": "RU",
            "last_analysis_date": "2024-08-15"
        }
        return json.dumps(enrichment_data, indent=2)
    return json.dumps({"is_malicious": False})

async def get_prioritized_task(log_batch: str) -> str:
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    planner_system_message = """You are an expert SOC analyst responsible for initial event triage. 
    Your task is to review a batch of raw security logs in JSON format. Analyze these logs to identify the single most suspicious or anomalous activity that requires immediate investigation.
    Focus on identifying patterns like multiple 'ssh_login_failure' events from a single IP followed by a 'ssh_login_success'.
    Based on your findings, formulate a single, concise task for the investigation team. For example: 'High priority: Investigate IP 198.51.100.10 due to a suspected brute-force attack against the admin account on db-server-01.'
    Your output must be ONLY the task string, nothing else.
    """
    triage_planner_agent = AssistantAgent(
        name="Triage_Planner_Agent",
        model_client=model_client,
        system_message=planner_system_message,
    )
    
    planner_proxy = UserProxyAgent(name="Planner_Proxy")
        
    planner_result = await triage_planner_agent.on_messages([TextMessage(content=log_batch, source="user")], cancellation_token=CancellationToken())
    prioritized_task = planner_result.chat_message.content
        
    await model_client.close() # Close client after use in this function
    return prioritized_task

async def run_investigation_team(prioritized_task: str):
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
        
    enrichment_agent = AssistantAgent(name="Alert_Enrichment_Agent", model_client=model_client, system_message="Your task is to enrich the primary indicator (e.g., IP address) from the task description. Use your tools and pass the JSON output to the next agent.", tools=[enrich_indicator])
    correlation_agent = AssistantAgent(name="Log_Correlation_Agent", model_client=model_client, system_message="Your task is to take the enriched indicators and search for them in the SIEM. Pass the raw JSON log findings to the next agent.", tools=[run_siem_query])
    assessment_agent = AssistantAgent(name="Impact_Assessment_Agent", model_client=model_client, system_message="Synthesize all JSON data. Analyze logs for patterns. Create a final summary including: 1. Threat intel summary. 2. Internal activity found. 3. Impact/severity assessment. 4. Recommendation. End with 'TERMINATE'.", tools=[])
    
    investigation_initiator = UserProxyAgent(name="SOC_Manager", input_func=Console.input_func)
    
    triage_team = RoundRobinGroupChat(
        participants=[investigation_initiator, enrichment_agent, correlation_agent, assessment_agent],
    )
    
    await triage_team.run(task=[TextMessage(content=prioritized_task, source="user")], cancellation_token=CancellationToken())
    await model_client.close()

async def main():
    # This main function is now primarily for demonstration or direct console use
    # For web UI integration, call get_prioritized_task directly
    log_batch = get_log_events()
    
    prioritized_task = await get_prioritized_task(log_batch)
    await run_investigation_team(prioritized_task)

if __name__ == "__main__":
    asyncio.run(main())
