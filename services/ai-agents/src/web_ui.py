import logging
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from triage_service import init_logging

# Initialize logging for the triage service
init_logging()

# Create a dedicated logger for websocket server
ws_logger = logging.getLogger("websocket_server")
ws_logger.setLevel(logging.INFO)

app = FastAPI(title="SOC Agent Analysis WebSocket Server")

# Import and include middleware and routes
from api.middleware.cors import add_cors_middleware
from api.routes.websocket import router as websocket_router
from api.routes.logs import router as logs_router
from api.routes.health import router as health_router

# Add CORS middleware
add_cors_middleware(app)

# Include routers
app.include_router(websocket_router)
app.include_router(logs_router)
app.include_router(health_router)

# Serve static files and dashboard
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Root endpoint redirects to /static/dashboard.html
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/static/dashboard.html")

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 5000))
    ws_logger.info(f"Starting WebSocket SOC Analysis Server on port {port}")
    uvicorn.run(app, host='0.0.0.0', port=port)
