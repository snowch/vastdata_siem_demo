from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

# A simple in-memory store for active WebSocket connections count
active_connections_count = 0

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_connections": active_connections_count,
        "timestamp": datetime.now().isoformat()
    }
