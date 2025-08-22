# services/ai-agents/src/core/services/agent_service.py - REFACTORED VERSION
"""
Agent Service - Main workflow coordinator (simplified)
Complex logic moved to dedicated modules
"""

import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable

from .workflow_orchestrator import WorkflowOrchestrator
from .message_processor import MessageProcessor  
from .state_manager import WorkflowStateManager
from .team_builder import TeamBuilder

agent_logger = logging.getLogger("agent_diagnostics")

async def run_analysis_workflow(
    log_batch: str,
    session_id: str,
    user_input_callback: Optional[Callable] = None,
    message_callback: Optional[Callable] = None
) -> bool:
    """
    Main entry point for SOC analysis workflow
    Now simplified with delegation to specialized components
    """
    agent_logger.info(f"🚀 Starting SOC analysis workflow for session {session_id}")
    
    # Initialize components
    state_manager = WorkflowStateManager(session_id)
    message_processor = MessageProcessor(session_id, state_manager, message_callback)
    team_builder = TeamBuilder()
    orchestrator = WorkflowOrchestrator(
        state_manager, 
        message_processor, 
        user_input_callback
    )
    
    try:
        # Create the analysis team
        team, model_client = await team_builder.create_soc_team(
            user_input_func=orchestrator.get_user_input_func(),
            external_termination=orchestrator.get_termination_controller()
        )
        
        # Build analysis task
        task = orchestrator.build_analysis_task(log_batch)
        
        # Execute workflow
        success = await orchestrator.execute_workflow(team, task)
        
        # Cleanup
        await model_client.close()
        
        agent_logger.info(f"✅ Workflow completed for {session_id}: {success}")
        return success
        
    except Exception as e:
        agent_logger.error(f"❌ Workflow error for {session_id}: {e}")
        
        if message_callback:
            await message_callback({
                "type": "error",
                "session_id": session_id,
                "message": f"Analysis workflow error: {str(e)}",
                "error_code": "ANALYSIS_ERROR"
            })
        
        return False