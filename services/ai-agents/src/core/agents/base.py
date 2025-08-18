from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

class BaseAgent(AssistantAgent):
    def __init__(self, name: str, model_client: OpenAIChatCompletionClient, system_message: str, tools: list):
        super().__init__(
            name=name,
            model_client=model_client,
            system_message=system_message,
            tools=tools
        )
