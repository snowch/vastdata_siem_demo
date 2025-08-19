# services/ai-agents/src/core/models/websocket.py - FIFTH UPDATE
# Remove the complex AnalysisProgress class - no longer needed!

# This file is now much simpler since we removed complex progress tracking.
# The SimplifiedSession class is defined directly in the websocket route file.
# 
# We could define shared models here if needed in the future, but for now
# the simplified approach doesn't need any complex WebSocket models.

# If you need to add simple WebSocket models in the future, you can add them here.
# For example:

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel

class SimpleMessage(BaseModel):
    """Simple message model for WebSocket communication"""
    type: str
    content: str
    timestamp: str = datetime.now().isoformat()
    session_id: Optional[str] = None

class ApprovalRequest(BaseModel):
    """Model for approval requests"""
    stage: str
    prompt: str
    timestamp: str = datetime.now().isoformat()

class ApprovalResponse(BaseModel):
    """Model for approval responses"""
    stage: str
    response: str
    timestamp: str = datetime.now().isoformat()
