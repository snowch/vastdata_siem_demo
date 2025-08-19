# Fixed core/agents/base.py
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from typing import List, Optional, Any

class BaseAgent(AssistantAgent):
    def __init__(self, name: str, model_client: OpenAIChatCompletionClient, system_message: str, tools: Optional[List[Any]] = None, **kwargs):
        # Prepare the initialization arguments
        init_args = {
            "name": name,
            "model_client": model_client,
            "system_message": system_message
        }
        
        # Add tools if provided
        if tools:
            init_args["tools"] = tools
            
        # Add any additional keyword arguments
        init_args.update(kwargs)
        
        super().__init__(**init_args)