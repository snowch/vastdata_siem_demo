import logging
import logging.config
import os

# Import AutoGen's official logger names
try:
    from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME
    AUTOGEN_AVAILABLE = True
except ImportError:
    # Fallback if autogen_core not available
    TRACE_LOGGER_NAME = "autogen_core.trace"
    EVENT_LOGGER_NAME = "autogen_core.event"
    AUTOGEN_AVAILABLE = False

# Your custom loggers
trace_logger = None
event_logger = None
agent_logger = None

def init_logging(autogen_debug_mode=False):
    """Initialize logging with proper AutoGen support"""
    global trace_logger, event_logger, agent_logger

    if agent_logger and agent_logger.handlers:
        return

    # Set base logging level
    base_level = logging.WARN
    
    if not logging.root.handlers:
        logging.basicConfig(
            level=base_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    # ============================================================================
    # AUTOGEN LOGGERS
    # ============================================================================

    autogen_debug_mode = False
    
    # AutoGen Trace Logger (human-readable debug messages)
    trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
    if not trace_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '🔍 [AUTOGEN-TRACE] %(asctime)s - %(name)s - %(message)s'
        ))
        trace_logger.addHandler(handler)
    trace_logger.setLevel(logging.DEBUG if autogen_debug_mode else logging.WARN)
    trace_logger.propagate = False  # Prevent duplicate messages

    # AutoGen Event Logger (structured events)  
    event_logger = logging.getLogger(EVENT_LOGGER_NAME)
    if not event_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '📊 [AUTOGEN-EVENT] %(asctime)s - %(name)s - %(message)s'
        ))
        event_logger.addHandler(handler)
    event_logger.setLevel(logging.INFO if autogen_debug_mode else logging.WARN)
    event_logger.propagate = False

    # ============================================================================
    # AUTOGEN CHILD LOGGERS - Capture specific components
    # ============================================================================
    
    # Common AutoGen child loggers that you might want to see
    autogen_child_loggers = [
        "autogen_agentchat",
        "autogen_agentchat.teams", 
        "autogen_agentchat.agents",
        "autogen_agentchat.messages",
        "autogen_ext.models",
        "autogen_ext.models.openai",
    ]
    
    for logger_name in autogen_child_loggers:
        child_logger = logging.getLogger(logger_name)
        if not child_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                f'🤖 [AUTOGEN-{logger_name.upper()}] %(asctime)s - %(levelname)s - %(message)s'
            ))
            child_logger.addHandler(handler)
        child_logger.setLevel(logging.INFO if autogen_debug_mode else logging.WARN)
        child_logger.propagate = False

    # ============================================================================
    # YOUR CUSTOM LOGGERS
    # ============================================================================
    
    # Your existing agent diagnostics logger
    agent_logger = logging.getLogger("agent_diagnostics")
    agent_logger.setLevel(logging.INFO)

    # WebSocket logger with better visibility
    ws_logger = logging.getLogger("websocket_server")
    ws_logger.setLevel(logging.INFO if autogen_debug_mode else logging.WARNING)
    
    # Log successful initialization
    print(f"✅ Logging initialized - AutoGen available: {AUTOGEN_AVAILABLE}")
    print(f"🔍 Trace logger: {TRACE_LOGGER_NAME} (level: {logging.getLevelName(trace_logger.level)})")
    print(f"📊 Event logger: {EVENT_LOGGER_NAME} (level: {logging.getLevelName(event_logger.level)})")

