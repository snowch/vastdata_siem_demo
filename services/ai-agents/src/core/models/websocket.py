from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from fastapi import WebSocket

class AnalysisProgress:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.status = "initializing"
        self.current_agent = None
        self.agent_outputs = {
            'triage': [],
            'context': [],
            'analyst': []
        }
        self.progress_percent = 0
        self.error = None
        self.completed = False
        self.start_time = datetime.now()
        self.final_results = None
        
    async def send_update(self, status: Optional[str] = None, agent: Optional[str] = None, 
                         message: Optional[str] = None, progress: Optional[int] = None):
        """Send progress update via WebSocket"""
        try:
            if status:
                self.status = status
            if agent:
                self.current_agent = agent
            if message and agent:
                self.agent_outputs[agent].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': message
                })
            if progress is not None:
                self.progress_percent = progress

            # Create update message
            update = {
                "type": "progress_update",
                "session_id": self.session_id,
                "status": self.status,
                "current_agent": self.current_agent,
                "progress_percent": self.progress_percent,
                "agent_outputs": self.agent_outputs,
                "completed": self.completed,
                "error": self.error,
                "start_time": self.start_time.isoformat()
            }
            
            # Include final results if completed
            if self.completed and self.final_results:
                update["results"] = self.final_results

            await self.websocket.send_json(update)
            # ws_logger.debug(f"Sent update for session {self.session_id}: {status} - {progress}%") # Removed ws_logger since it's defined in web_ui.py
            
        except Exception as e:
            # ws_logger.error(f"Failed to send WebSocket update: {e}") # Removed ws_logger since it's defined in web_ui.py
            print(f"Failed to send WebSocket update: {e}") # Temporary fix since ws_logger is not available here
