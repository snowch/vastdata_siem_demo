#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import operators as kop
from bytewax import operators as op
from bytewax.connectors.stdio import StdOutSink
from pydantic_settings import BaseSettings
from py_ocsf_models.events.base_event import BaseEvent
from py_ocsf_models.events.findings.finding import Finding
from py_ocsf_models.events.findings.compliance_finding import ComplianceFinding
from py_ocsf_models.events.findings.detection_finding import DetectionFinding

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration with Pydantic
class Settings(BaseSettings):
    kafka_broker: str = os.environ.get("KAFKA_BROKER")
    kafka_event_log_topic: str = os.environ.get("KAFKA_EVENT_LOG_TOPIC")
    kafka_group_id: str = "ocsf-console-logger"

# Load settings
try:
    settings = Settings()
    print(
        f"""
---
KAFKA_BROKER={settings.kafka_broker}
KAFKA_TOPIC={settings.kafka_event_log_topic}
---
        """
    )
    if not settings.kafka_broker or not settings.kafka_event_log_topic:
        raise ValueError("KAFKA_BROKER and KAFKA_EVENT_LOG_TOPIC environment variables must be set")
except Exception as e:
    print(f"ERROR: Failed to load configuration: {e}")
    print("Make sure KAFKA_BROKER and KAFKA_EVENT_LOG_TOPIC environment variables are set")
    exit(1)


# Bytewax dataflow
flow = Dataflow("ocsf_dataflow")

# Kafka configuration for consumer group
# Note: You may see warnings about producer properties - these can be ignored
kafka_config = {
    "group.id": settings.kafka_group_id,
    "enable.auto.commit": "true",
    "auto.commit.interval.ms": "1000"
}

# Input from Kafka
kafka_input = kop.input(
    "kafka_input",
    flow,
    brokers=[settings.kafka_broker],
    topics=[settings.kafka_event_log_topic],
    add_config=kafka_config
)

# Process OCSF events
def process_event(kafka_message):
    try:
        # Parse OCSF JSON and validate against the Event model
        ocsf_data = json.loads(kafka_message.value)
        event_class = "Unknown"
        
        # Try to determine the event type based on class_uid or class_name
        class_uid = ocsf_data.get('class_uid')
        class_name = ocsf_data.get('class_name', 'Unknown')
        
        event = None
        event_class = class_name
        
        try:
            # Try specific finding types first based on class_uid
            if class_uid == 2001:  # Compliance Finding
                event = ComplianceFinding(**ocsf_data)
                event_class = "Compliance Finding"
            elif class_uid == 2004:  # Detection Finding  
                event = DetectionFinding(**ocsf_data)
                event_class = "Detection Finding"
            else:
                # Try generic Finding
                try:
                    event = Finding(**ocsf_data)
                    event_class = getattr(event, 'class_name', 'Finding')
                except Exception:
                    # Try BaseEvent as fallback
                    event = BaseEvent(**ocsf_data)
                    event_class = getattr(event, 'class_name', 'Base Event')
        except Exception as e:
            # If all validation fails, extract class info from raw data
            event_class = class_name
            logger.warning(f"Could not validate OCSF event: {e}")

        # Extract key fields for display
        timestamp = ocsf_data.get("time_dt", ocsf_data.get("time", ""))
        activity_name = ocsf_data.get("activity_name", "")
        severity = ocsf_data.get("severity", "")
        message_text = ocsf_data.get("message", "")
        
        # Format timestamp if it's a Unix timestamp
        if isinstance(timestamp, (int, float)):
            try:
                timestamp = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                timestamp = str(timestamp)

        # Format event info
        current_time = datetime.now().strftime("%H:%M:%S")
        formatted_event = f"[{current_time}] {event_class} | {activity_name} | {severity} | {timestamp}"
        
        if message_text:
            formatted_event += f"\n └─ {message_text}"
            
        return formatted_event
        
    except json.JSONDecodeError as e:
        return f"[ERROR] Failed to parse JSON: {e}"
    except Exception as e:
        return f"[ERROR] Error processing event: {e}"

# Apply processing to the successful messages stream
processed_events = op.map("process_events", kafka_input.oks, process_event)

# Output processed events to console using StdOutSink
op.output("console_output", processed_events, StdOutSink())
