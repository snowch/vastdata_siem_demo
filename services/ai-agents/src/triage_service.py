import asyncio
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseAgentEvent, ToolCallRequestEvent, ToolCallExecutionEvent
from autogen_core import CancellationToken
import json
import logging
from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME

# Global logger instances (initialized by init_logging)
trace_logger = None
event_logger = None
agent_logger = None

# TODO: @/services/ai-agents/src/triage_service.py  ... 
#       Agent should call the LLM chroma_search tool → Fetches top matching docs 
#       from Chroma and pass the matchng docs along with..

def init_logging():
    """Initializes logging for the triage service."""
    global trace_logger, event_logger, agent_logger

    # Prevent re-initialization if already configured (e.g., due to Flask reloader)
    if agent_logger and agent_logger.handlers:
        return

    # Configure root logger only if not already configured
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Create specific loggers and set their levels
    trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
    trace_logger.setLevel(logging.DEBUG)

    event_logger = logging.getLogger(EVENT_LOGGER_NAME)
    event_logger.setLevel(logging.DEBUG)

    # Create a custom logger for our agent diagnostics
    agent_logger = logging.getLogger("agent_diagnostics")
    agent_logger.setLevel(logging.DEBUG)

    # Add a file handler for agent diagnostics
    handler = logging.FileHandler('agent_diagnostics.log')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    agent_logger.addHandler(handler)

def log_all_messages(messages, context="Unknown"):
    """Log all messages with context and debugging."""
    if agent_logger:
        agent_logger.info(f"=== {context} - Total Messages: {len(messages)} ===")
        for i, msg in enumerate(messages):
            try:
                formatted_json = msg.model_dump_json(indent=2)
                agent_logger.info(f"Message: {formatted_json}")
            except Exception as e:
                agent_logger.error('Error at %s', exc_info=e)

async def get_prioritized_task(log_batch: str) -> tuple[str, list]:
    if agent_logger:
        agent_logger.info("Starting prioritized task analysis")
    
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    planner_system_message = """You are an expert SOC analyst responsible for initial event triage. 
    Your task is to review a batch of raw security logs in JSON format. Analyze these logs to identify the single most suspicious or anomalous activity that requires immediate investigation.
    Focus on identifying patterns like multiple 'ssh_login_failure' events from a single IP followed by a 'ssh_login_success'.
    Show your thinking step-by-step.
    """
    # Based on your findings, formulate a single, concise task for the investigation team. For example: 'High priority: Investigate IP 198.51.100.10 due to a suspected brute-force attack against the admin account on db-server-01.'
    # Your output must be ONLY the task string, nothing else.
    triage_planner_agent = AssistantAgent(
        name="Triage_Planner_Agent",
        model_client=model_client,
        system_message=planner_system_message
    )
    
    planner_proxy = UserProxyAgent(name="Planner_Proxy")
    
    if agent_logger:
        agent_logger.info("Running triage planner with task")
    planner_result = await triage_planner_agent.run(task=log_batch, cancellation_token=CancellationToken())
    
    # Extract the final task from the last message
    if planner_result.messages:
        # Get the last assistant message
        assistant_messages = [msg for msg in planner_result.messages if hasattr(msg, 'source') and msg.source == 'assistant']
        if assistant_messages:
            prioritized_task = assistant_messages[-1].content
        else:
            # Fallback to last message content
            prioritized_task = planner_result.messages[-1].content
    else:
        prioritized_task = "No task generated"
    
    if agent_logger:
        agent_logger.info(f"Triage planner completed. Task: {prioritized_task}")
    
    await model_client.close()
    
    # Enhanced message collection - now we get the full thought process!
    planner_diagnostics = []
    
    # Log all messages from the run result
    if planner_result.messages:
        if agent_logger:
            agent_logger.info(f"Planner messages count: {len(planner_result.messages)}")
        log_all_messages(planner_result.messages, "Planner Full Messages")
        for msg in planner_result.messages:
            planner_diagnostics.append(json.loads(msg.model_dump_json()))
    else:
        if agent_logger:
            agent_logger.warning("No messages found in planner result")
    
    if agent_logger:
        agent_logger.info(f"Planner diagnostics collected: {len(planner_diagnostics)} messages")
    return prioritized_task, planner_diagnostics






# async def run_investigation_team(prioritized_task: str) -> tuple[str, list]:
#     if agent_logger:
#         agent_logger.info(f"Starting investigation team with task: {prioritized_task}")
    
#     model_client = OpenAIChatCompletionClient(model="gpt-4o")
        
#     enrichment_agent = AssistantAgent(
#         name="Alert_Enrichment_Agent", 
#         model_client=model_client, 
#         system_message="Your task is to enrich the primary indicator (e.g., IP address) from the task description. Use your tools and pass the JSON output to the next agent.", 
#         tools=[enrich_indicator]
#     )
    
#     correlation_agent = AssistantAgent(
#         name="Log_Correlation_Agent", 
#         model_client=model_client, 
#         system_message="Your task is to take the enriched indicators and search for them in the SIEM. Pass the raw JSON log findings to the next agent.", 
#         tools=[run_siem_query]
#     )
    
#     assessment_agent = AssistantAgent(
#         name="Impact_Assessment_Agent", 
#         model_client=model_client, 
#         system_message="Synthesize all JSON data. Analyze logs for patterns. Create a final summary including: 1. Threat intel summary. 2. Internal activity found. 3. Impact/severity assessment. 4. Recommendation. End with 'TERMINATE'.", 
#         tools=[]
#     )
    
#     investigation_initiator = UserProxyAgent(name="SOC_Manager")
    
#     triage_team = RoundRobinGroupChat(
#         participants=[investigation_initiator, enrichment_agent, correlation_agent, assessment_agent],
#     )
    
#     if agent_logger:
#         agent_logger.info("Running investigation team")
#     team_result = await triage_team.run(task=prioritized_task, cancellation_token=CancellationToken())
    
#     await model_client.close()
    
#     investigation_diagnostics = []
    
#     # Enhanced message collection for team result - now we get the full conversation!
#     if team_result.messages:
#         if agent_logger:
#             agent_logger.info(f"Team result messages count: {len(team_result.messages)}")
#         # log_all_messages(team_result.messages, "Team Result Messages")
#         # for msg in team_result.messages:
#         #     investigation_diagnostics.append(format_message_for_diagnostics(msg))
#     else:
#         if agent_logger:
#             agent_logger.warning("No messages found in team result")
    
#     # Find the final assessment message - look for the last assistant message
#     final_assessment = "No final assessment found."
#     if team_result.messages:
#         # Look for the last message that contains an assessment
#         for msg in reversed(team_result.messages):
#             if hasattr(msg, 'content') and isinstance(msg.content, str):
#                 if "TERMINATE" in msg.content or len(msg.content) > 100:  # Likely the final assessment
#                     final_assessment = msg.content
#                     break
    
#     if agent_logger:
#         agent_logger.info(f"Investigation diagnostics collected: {len(investigation_diagnostics)} messages")
#         agent_logger.info(f"Final assessment length: {len(final_assessment)} characters")
    
#     return final_assessment, investigation_diagnostics
