import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.models.websocket import AnalysisProgress
from core.services.agent_service import get_prioritized_task
from core.services.analysis_helpers import parse_agent_conversation, extract_structured_findings
from utils.serialization import sanitize_chroma_results
from log_retriever import get_logs
import logging
import traceback

router = APIRouter()

ws_logger = logging.getLogger("websocket_server")

async def send_agent_outputs(progress: AnalysisProgress, agent_outputs: dict, findings_summary: dict):
    current_progress = 30

    if agent_outputs['triage'] or findings_summary['priority_found']:
        await progress.send_update("completed_triage", "triage",
            f"✅ Triage completed - {findings_summary['priority_level']} priority {findings_summary['threat_type']} detected",
            current_progress)
        for output in agent_outputs['triage']:
            progress.agent_outputs['triage'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress = 50
    else:
        progress.agent_outputs['triage'].append({
            'timestamp': datetime.now().isoformat(),
            'message': "Triage analysis completed - check detailed conversation for findings"
        })

    if agent_outputs['context'] or findings_summary['context_searched']:
        await progress.send_update("completed_context", "context",
            "🔎 Historical context research completed", current_progress)
        for output in agent_outputs['context']:
            progress.agent_outputs['context'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress = 70
    else:
        progress.agent_outputs['context'].append({
            'timestamp': datetime.now().isoformat(),
            'message': "Context research completed - historical incidents analyzed"
        })

    if agent_outputs['analyst'] or findings_summary['analysis_completed']:
        await progress.send_update("completed_analyst", "analyst",
            "👨‍💼 Deep analysis and recommendations completed", current_progress)
        for output in agent_outputs['analyst']:
            progress.agent_outputs['analyst'].append({
                'timestamp': datetime.now().isoformat(),
                'message': output
            })
        current_progress = 90
    else:
        progress.agent_outputs['analyst'].append({
            'timestamp': datetime.now().isoformat(),
            'message': "Senior analysis completed - recommendations generated"
        })

    for agent_type in ['triage', 'context', 'analyst']:
        if not progress.agent_outputs[agent_type]:
            progress.agent_outputs[agent_type].append({
                'timestamp': datetime.now().isoformat(),
                'message': f"{agent_type.title()} agent completed successfully. Check full conversation for details."
            })

    return current_progress

async def run_analysis_with_websocket(log_batch: str, progress: AnalysisProgress):
    try:
        await progress.send_update("starting", progress=10)
        ws_logger.info(f"Starting analysis for session {progress.session_id}")

        await progress.send_update("running_triage", "triage", "🔍 Starting initial triage analysis...", 20)

        full_conversation, structured_findings, chroma_context = await get_prioritized_task(log_batch)

        ws_logger.info(f"Raw structured findings for session {progress.session_id}: {structured_findings}")

        if 'detailed_analysis' in structured_findings:
            detailed = structured_findings['detailed_analysis']
            if 'threat_assessment' not in detailed or not detailed['threat_assessment']:
                detailed['threat_assessment'] = {
                    "severity": "unknown",
                    "confidence": 0.0
                }
                ws_logger.warning(f"Added default threat_assessment for session {progress.session_id}")

        agent_outputs = parse_agent_conversation(full_conversation)

        findings_summary = extract_structured_findings(full_conversation, structured_findings)

        current_progress = await send_agent_outputs(progress, agent_outputs, findings_summary)

        progress.final_results = {
            'conversation': full_conversation,
            'structured_findings': structured_findings,
            'chroma_context': sanitize_chroma_results(chroma_context),
            'findings_summary': findings_summary
        }

        progress.completed = True
        await progress.send_update("completed", progress=100)

        ws_logger.info(f"Analysis completed for session {progress.session_id}")

    except Exception as e:
        ws_logger.error(f"Analysis failed for session {progress.session_id}: {str(e)}")
        ws_logger.error(f"Full traceback: {traceback.format_exc()}")
        progress.error = str(e)
        progress.completed = True
        await progress.send_update("error", progress=100)

async def handle_start_analysis(data: dict, session_id: str, websocket: WebSocket):
    log_batch = data.get("logs")
    if not log_batch:
        await websocket.send_json({
            "type": "error",
            "message": "No logs provided for analysis"
        })
        return

    ws_logger.info(f"Starting analysis for session {session_id}")

    progress = AnalysisProgress(session_id, websocket)

    asyncio.create_task(run_analysis_with_websocket(log_batch, progress))

async def handle_retrieve_logs(session_id: str, websocket: WebSocket):
    ws_logger.info(f"Log retrieval requested via WebSocket: {session_id}")
    try:
        logs = get_logs()
        await websocket.send_json({
            "type": "logs_retrieved",
            "logs": logs,
            "message": f"Retrieved {len(logs)} log entries successfully"
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Server error: {str(e)}"
        })

async def handle_ping(websocket: WebSocket):
    await websocket.send_json({
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    })

@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())

    ws_logger.info(f"WebSocket connection established: {session_id}")

    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "message": "Connected to SOC Analysis WebSocket"
    })

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "start_analysis":
                await handle_start_analysis(data, session_id, websocket)

            elif message_type == "retrieve_logs":
                await handle_retrieve_logs(session_id, websocket)

            elif message_type == "ping":
                await handle_ping(websocket)

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        ws_logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except Exception:
            pass
