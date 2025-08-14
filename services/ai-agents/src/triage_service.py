import asyncio
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseAgentEvent, ToolCallRequestEvent, ToolCallExecutionEvent
from autogen_core import CancellationToken
import json
import logging
import traceback
from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME
from vectordb_utils import search_chroma

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

async def get_prioritized_task(log_batch: str) -> tuple[str, list, dict]:
    if agent_logger:
        agent_logger.info("Starting prioritized task analysis")
        agent_logger.debug(f"Input log_batch type: {type(log_batch)}, length: {len(log_batch)}")
    
    try:
        if agent_logger:
            agent_logger.debug("Creating OpenAI model client")
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        
        planner_system_message = """You are an expert SOC analyst responsible for initial event triage. 
        Your task is to review a batch of raw security logs in JSON format. Analyze these logs to identify the single most suspicious or anomalous activity that requires immediate investigation.
        Focus on identifying patterns like multiple 'ssh_login_failure' events from a single IP followed by a 'ssh_login_success'.
        Show your thinking step-by-step.
        """
        
        if agent_logger:
            agent_logger.debug("Creating triage planner agent")
        triage_planner_agent = AssistantAgent(
            name="Triage_Planner_Agent",
            model_client=model_client,
            system_message=planner_system_message
        )
        
        planner_proxy = UserProxyAgent(name="Planner_Proxy")
        
        if agent_logger:
            agent_logger.info("Running triage planner with task")
            agent_logger.debug(f"Task preview: {log_batch[:200]}...")
            
        planner_result = await triage_planner_agent.run(task=log_batch, cancellation_token=CancellationToken())
        
        if agent_logger:
            agent_logger.debug(f"Planner result type: {type(planner_result)}")
            agent_logger.debug(f"Planner result has messages: {hasattr(planner_result, 'messages')}")
        
        # Extract the final task from the last message
        prioritized_task = "No task generated"
        if planner_result.messages:
            if agent_logger:
                agent_logger.debug(f"Found {len(planner_result.messages)} messages in planner result")
            # Get the last assistant message
            assistant_messages = [msg for msg in planner_result.messages if hasattr(msg, 'source') and msg.source == 'assistant']
            if assistant_messages:
                prioritized_task = assistant_messages[-1].content
                if agent_logger:
                    agent_logger.debug("Using last assistant message for prioritized task")
            else:
                # Fallback to last message content
                prioritized_task = planner_result.messages[-1].content
                if agent_logger:
                    agent_logger.debug("Using last message content for prioritized task")
        else:
            if agent_logger:
                agent_logger.warning("No messages found in planner result")
        
        if agent_logger:
            agent_logger.info(f"Triage planner completed. Task length: {len(prioritized_task)}")
            agent_logger.debug(f"Task preview: {prioritized_task[:200]}...")
        
        # ChromaDB search for relevant context
        chroma_results = {"error": "No search performed"}
        try:
            if agent_logger:
                agent_logger.debug("Starting ChromaDB search")
            chroma_results = search_chroma(prioritized_task, n_results=5)
            if agent_logger:
                agent_logger.info(f"Chroma search returned {len(chroma_results.get('documents', []))} results")
                agent_logger.debug(f"Chroma results keys: {list(chroma_results.keys())}")
        except Exception as e:
            chroma_results = {"error": str(e)}
            if agent_logger:
                agent_logger.error(f"Chroma search failed: {e}")
                agent_logger.error(f"Chroma search traceback: {traceback.format_exc()}")

        if agent_logger:
            agent_logger.debug("Closing model client")
        await model_client.close()
        
        # Enhanced message collection - now we get the full thought process!
        planner_diagnostics = []
        
        # Log all messages from the run result
        if planner_result.messages:
            if agent_logger:
                agent_logger.info(f"Planner messages count: {len(planner_result.messages)}")
            log_all_messages(planner_result.messages, "Planner Full Messages")
            try:
                for msg in planner_result.messages:
                    planner_diagnostics.append(json.loads(msg.model_dump_json()))
            except Exception as e:
                if agent_logger:
                    agent_logger.error(f"Error processing planner messages: {e}")
                    agent_logger.error(f"Message processing traceback: {traceback.format_exc()}")
        else:
            if agent_logger:
                agent_logger.warning("No messages found in planner result")
        
        if agent_logger:
            agent_logger.info(f"Planner diagnostics collected: {len(planner_diagnostics)} messages")
            agent_logger.debug(f"Chroma results summary: {type(chroma_results)}")

        return prioritized_task, planner_diagnostics, chroma_results
        
    except Exception as e:
        if agent_logger:
            agent_logger.error(f"Critical error in get_prioritized_task: {e}")
            agent_logger.error(f"Full traceback: {traceback.format_exc()}")
        # Return safe defaults
        return f"Error during analysis: {str(e)}", [], {"error": str(e)}
