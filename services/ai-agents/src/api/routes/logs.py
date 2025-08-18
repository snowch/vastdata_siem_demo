from fastapi import APIRouter, HTTPException
from log_retriever import get_logs
import logging

router = APIRouter()
ws_logger = logging.getLogger("websocket_server")

@router.get("/retrieve_logs")
async def retrieve_logs():
    ws_logger.info("Retrieve logs endpoint accessed")
    try:
        logs = get_logs()
        ws_logger.info(f"Successfully retrieved {len(logs)} logs")
        return logs
    except Exception as e:
        ws_logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")
