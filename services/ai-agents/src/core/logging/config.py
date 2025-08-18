import logging
import logging.config
import os

TRACE_LOGGER_NAME = "trace_logger"
EVENT_LOGGER_NAME = "event_logger"

trace_logger = None
event_logger = None
agent_logger = None

def init_logging():
    global trace_logger, event_logger, agent_logger

    if agent_logger and agent_logger.handlers:
        return

    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
    trace_logger.setLevel(logging.DEBUG)

    event_logger = logging.getLogger(EVENT_LOGGER_NAME)
    event_logger.setLevel(logging.DEBUG)

    agent_logger = logging.getLogger("agent_diagnostics")
    agent_logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler('agent_diagnostics.log')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    agent_logger.addHandler(handler)
