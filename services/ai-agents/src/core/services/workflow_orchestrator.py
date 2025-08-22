"""
Workflow Orchestrator - Fixed stage detection and response processing
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
        
        # Track which agents are requesting approval
        self.current_requesting_agent = None
    
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
        """Create the user input function for the team - FIXED STAGE DETECTION"""
        async def user_input_func(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
            if not self.user_input_callback:
                agent_logger.info("No user input callback, auto-approving")
                return "AUTO-APPROVED - No user input mechanism available"
            
            try:
                # FIXED: Determine stage from current workflow state instead of just prompt
                stage = self._determine_current_stage(prompt)
                
                agent_logger.info(f"🔔 Requesting user input for {stage} stage")
                agent_logger.debug(f"Prompt: {prompt[:100]}...")
                
                # Request user input with proper stage
                user_response = await self.user_input_callback(prompt, self.state_manager.session_id)
                
                # Process response and record in state
                processed_response = self._process_user_response(user_response, stage)
                
                agent_logger.info(f"✅ User response processed for {stage}: {processed_response[:50]}...")
                
                return processed_response
                
            except asyncio.TimeoutError:
                agent_logger.warning("User input timeout, auto-approving")
                return "TIMEOUT - Auto-approving to continue analysis"
            except Exception as e:
                agent_logger.error(f"Error getting user input: {e}")
                return "ERROR - Auto-approving due to input error"
        
        return user_input_func
    
    def _determine_current_stage(self, prompt: str) -> str:
        """Determine current workflow stage - IMPROVED LOGIC"""
        
        # Check workflow state first (most reliable)
        completed_stages = self.state_manager.completed_stages
        
        # If triage is not complete, we're in triage
        if 'triage' not in completed_stages:
            return 'triage'
        
        # If triage is complete but context isn't, we're in context
        if 'context' not in completed_stages:
            return 'context'
        
        # If both triage and context are complete, we're in analyst
        if 'analyst' not in completed_stages:
            return 'analyst'
        
        # Fallback to prompt analysis if state is unclear
        return self._analyze_prompt_for_stage(prompt)
    
    def _analyze_prompt_for_stage(self, prompt: str) -> str:
        """Analyze prompt content to determine stage - IMPROVED"""
        prompt_lower = prompt.lower()
        
        # Triage indicators
        triage_keywords = [
            'priority', 'threat', 'investigate', 'brute force', 'attack',
            'sql injection', 'incident', 'malicious', 'compromise',
            'critical', 'high priority', 'security event'
        ]
        
        # Context indicators
        context_keywords = [
            'historical', 'context', 'incidents', 'pattern', 'similar',
            'documents', 'research', 'analysis', 'past', 'previous',
            'correlation', 'baseline', 'trend'
        ]
        
        # Analyst indicators
        analyst_keywords = [
            'recommend', 'action', 'authorize', 'implement', 'security',
            'business impact', 'final', 'complete', 'mitigation',
            'response', 'remediation', 'strategy'
        ]
        
        # Score each stage
        triage_score = sum(1 for keyword in triage_keywords if keyword in prompt_lower)
        context_score = sum(1 for keyword in context_keywords if keyword in prompt_lower)
        analyst_score = sum(1 for keyword in analyst_keywords if keyword in prompt_lower)
        
        # Return stage with highest score
        if triage_score >= context_score and triage_score >= analyst_score:
            return 'triage'
        elif context_score >= analyst_score:
            return 'context'
        else:
            return 'analyst'
    
    def _process_user_response(self, response: str, stage: str) -> str:
        """Process user response based on stage - IMPROVED"""
        response_lower = response.lower().strip()
        
        if response_lower in ['approve', 'approved', 'yes', 'continue']:
            self.state_manager.record_approval(stage, True)
            return f"APPROVED - {stage.title()} stage approved. Proceeding to next stage."
        elif response_lower in ['reject', 'rejected', 'no', 'stop', 'cancel']:
            self.state_manager.record_approval(stage, False)
            return f"REJECTED - {stage.title()} stage rejected. WORKFLOW_REJECTED"
        elif response_lower.startswith('custom:'):
            custom_instructions = response[7:].strip()
            self.state_manager.record_approval(stage, True, custom_instructions)
            return f"CUSTOM - User instructions for {stage}: {custom_instructions}"
        else:
            # Treat any other response as custom instructions
            self.state_manager.record_approval(stage, True, response)
            return f"CUSTOM - User response for {stage}: {response}"