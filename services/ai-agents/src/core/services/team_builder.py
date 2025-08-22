# services/ai-agents/src/core/services/team_builder.py
"""
Team Builder - Creates and configures agent teams
"""

from typing import Callable, Optional, Awaitable
from autogen_core import CancellationToken
from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import StructuredMessage
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    TokenUsageTermination,
    TimeoutTermination,
    SourceMatchTermination,
    ExternalTermination
)
from autogen_ext.models.openai import OpenAIChatCompletionClient

from core.agents.triage import TriageAgent
from core.agents.context import ContextAgent
from core.agents.analyst import AnalystAgent
from core.models.analysis import PriorityFindings, SOCAnalysisResult, ContextResearchResult
import logging

agent_logger = logging.getLogger("agent_diagnostics")

class TeamBuilder:
    """Builds and configures agent teams"""
    
    def __init__(self):
        self.model_client = None
    
    async def create_soc_team(
        self,
        user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
        external_termination: ExternalTermination
    ):
        """Create SOC analysis team with approval workflow"""
        
        # Create model client
        self.model_client = OpenAIChatCompletionClient(model="gpt-4o")
        
        # Create specialized agents
        triage_agent = TriageAgent(self.model_client)
        context_agent = ContextAgent(self.model_client)
        analyst_agent = AnalystAgent(self.model_client)
        
        # Create approval agents for each stage
        triage_approval_agent = UserProxyAgent(
            name="TriageApprovalAgent",
            input_func=user_input_func
        )
        
        context_approval_agent = UserProxyAgent(
            name="ContextApprovalAgent", 
            input_func=user_input_func
        )
        
        analyst_approval_agent = UserProxyAgent(
            name="AnalystApprovalAgent",
            input_func=user_input_func
        )
        
        # Create team with proper agent order
        team = RoundRobinGroupChat(
            [
                triage_agent,           # 1. Analyze threats
                triage_approval_agent,  # 2. Approve investigation  
                context_agent,          # 3. Research historical context
                context_approval_agent, # 4. Approve context relevance
                analyst_agent,          # 5. Deep analysis
                analyst_approval_agent  # 6. Approve recommendations
            ],
            termination_condition=self._create_termination_conditions(external_termination),
            custom_message_types=[
                StructuredMessage[PriorityFindings],
                StructuredMessage[SOCAnalysisResult],
                StructuredMessage[ContextResearchResult]
            ],
        )
        
        agent_logger.info("SOC team created with multi-stage approval workflow")
        return team, self.model_client
    
    def _create_termination_conditions(self, external_termination: ExternalTermination):
        """Create comprehensive termination conditions"""
        
        # Normal completion when analyst finishes
        normal_completion = (
            SourceMatchTermination("SeniorAnalystSpecialist") &
            TextMentionTermination("ANALYSIS_COMPLETE")
        )
        
        # Rejection termination from any approval agent
        rejection_termination = (
            (SourceMatchTermination("TriageApprovalAgent") |
             SourceMatchTermination("ContextApprovalAgent") |
             SourceMatchTermination("AnalystApprovalAgent")) &
            TextMentionTermination("WORKFLOW_REJECTED")
        )
        
        # Safety termination conditions
        max_messages = MaxMessageTermination(60)
        token_limit = TokenUsageTermination(max_total_token=90000)
        timeout = TimeoutTermination(timeout_seconds=1200)
        
        # Combined termination - external has highest priority
        return (
            external_termination |
            normal_completion |
            rejection_termination |
            max_messages |
            token_limit |
            timeout
        )