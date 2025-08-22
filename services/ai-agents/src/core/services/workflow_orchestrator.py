# services/ai-agents/src/core/services/workflow_orchestrator.py
"""
Workflow Orchestrator - Manages the high-level workflow execution
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
from autogen_core import CancellationToken
from autogen_agentchat.conditions import ExternalTermination

from .state_manager import WorkflowStateManager
from .message_processor import MessageProcessor
import logging

agent_logger = logging.getLogger("agent_diagnostics")

class WorkflowOrchestrator:
    """Orchestrates the high-level workflow execution"""
    
    def __init__(
        self,
        state_manager: WorkflowStateManager,
        message_processor: MessageProcessor,
        user_input_callback: Optional[Callable] = None
    ):
        self.state_manager = state_manager
        self.message_processor = message_processor
        self.user_input_callback = user_input_callback
        self.external_termination = ExternalTermination()
    
    def get_termination_controller(self) -> ExternalTermination:
        """Get the external termination controller"""
        return self.external_termination
    
    def get_user_input_func(self):
        """Get the user input function for the team"""
        return self._create_user_input_function()
    
    def build_analysis_task(self, log_batch: str) -> str:
        """Build the analysis task prompt"""
        return f"""SOC SECURITY ANALYSIS WORKFLOW

Analyze these OCSF security log events for threats requiring immediate attention:

{log_batch}

WORKFLOW STAGES:
1. **TRIAGE**: TriageSpecialist performs threat identification
2. **CONTEXT**: ContextAgent searches historical incidents  
3. **ANALYSIS**: SeniorAnalystSpecialist performs deep analysis

COMPLETION REQUIREMENTS:
- Use structured output formats for all results
- Set workflow_complete=True in SOCAnalysisResult when done
- Wait for approval between stages
- Provide clear, actionable recommendations

TriageSpecialist: Begin initial threat analysis."""
    
    async def execute_workflow(self, team, task: str) -> bool:
        """Execute the analysis workflow"""
        start_time = datetime.now()
        
        try:
            # Set initial progress
            await self.message_processor.send_progress_update(5, "Initializing agents...")
            
            # Execute the team workflow
            stream = team.run_stream(task=task, cancellation_token=CancellationToken())
            
            # Process messages as they arrive
            async for message in stream:
                await self.message_processor.process_message(
                    message, 
                    self.external_termination
                )
                
                # Check for completion
                if (self.state_manager.is_workflow_complete() or 
                    self.external_termination.terminated):
                    break
            
            # Calculate final results
            duration = (datetime.now() - start_time).total_seconds()
            success = not self.state_manager.was_rejected()
            
            # Send completion message
            await self.message_processor.send_completion_message(success, duration)
            
            agent_logger.info(f"Workflow execution completed: {success}")
            return success
            
        except Exception as e:
            agent_logger.error(f"Workflow execution error: {e}")
            await self.message_processor.send_error(f"Workflow execution error: {str(e)}")
            return False
    
    def _create_user_input_function(self):
        """Create the user input function for the team"""
        async def user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
            if not self.user_input_callback:
                agent_logger.info("No user input callback, auto-approving")
                return "AUTO-APPROVED - No user input mechanism available"
            
            try:
                # Determine stage from prompt
                stage = self._determine_stage_from_prompt(prompt)
                
                # Request user input
                user_response = await self.user_input_callback(prompt, self.state_manager.session_id)
                
                # Process response
                return self._process_user_response(user_response, stage)
                
            except asyncio.TimeoutError:
                agent_logger.warning("User input timeout, auto-approving")
                return "TIMEOUT - Auto-approving to continue analysis"
            except Exception as e:
                agent_logger.error(f"Error getting user input: {e}")
                return "ERROR - Auto-approving due to input error"
        
        return user_input_func
    
    def _determine_stage_from_prompt(self, prompt: str) -> str:
        """Determine workflow stage from prompt content"""
        prompt_lower = prompt.lower()
        
        if any(keyword in prompt_lower for keyword in [
            "priority threat", "investigate", "brute force", "attack detected"
        ]):
            return "triage"
        elif any(keyword in prompt_lower for keyword in [
            "historical", "context", "incidents", "pattern"
        ]):
            return "context"
        elif any(keyword in prompt_lower for keyword in [
            "recommend", "action", "authorize", "implement"
        ]):
            return "analyst"
        
        return "unknown"
    
    def _process_user_response(self, response: str, stage: str) -> str:
        """Process user response based on stage"""
        response_lower = response.lower().strip()
        
        if response_lower in ['approve', 'approved', 'yes', 'continue']:
            self.state_manager.record_approval(stage, True)
            return f"APPROVED - {stage.title()} stage approved. Proceeding to next stage."
        elif response_lower in ['reject', 'rejected', 'no', 'stop', 'cancel']:
            self.state_manager.record_approval(stage, False)
            return f"REJECTED - {stage.title()} stage rejected. WORKFLOW_REJECTED"
        else:
            self.state_manager.record_approval(stage, True, response)
            return f"CUSTOM - User instructions for {stage}: {response}"