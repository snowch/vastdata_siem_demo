#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import operators as kop
from bytewax import operators as op
import pyarrow as pa
from bytewax.connectors.stdio import StdOutSink
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from py_ocsf_models.events.base_event import BaseEvent
from py_ocsf_models.events.findings.finding import Finding
from py_ocsf_models.events.findings.compliance_finding import ComplianceFinding
from py_ocsf_models.events.findings.detection_finding import DetectionFinding

from .pydantic_utils import get_model_data, get_model_fields, pydantic_to_arrow_schema, pydantic_to_arrow_table
from .vastdb_utils import connect_to_vastdb, write_to_vastdb, get_columns_to_add
from .ocsf_mapping import OCSF_CLASS_MAPPING


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Environment configuration with Pydantic
class Settings(BaseSettings):
    kafka_broker: str = os.environ.get("KAFKA_BROKER")
    kafka_event_log_topic: str = os.environ.get("KAFKA_EVENT_LOG_TOPIC")
    kafka_group_id: str = "ocsf-console-logger"
    vastdb_endpoint: str = os.environ.get("VASTDB_ENDPOINT")
    vastdb_data_endpoints: str = os.environ.get("VASTDB_DATA_ENDPOINTS")
    vastdb_access_key: str = os.environ.get("VASTDB_ACCESS_KEY")
    vastdb_secret_key: str = os.environ.get("VASTDB_SECRET_KEY")
    vastdb_fluentd_bucket: str = os.environ.get("VASTDB_FLUENTD_BUCKET")
    vastdb_fluentd_schema: str = os.environ.get("VASTDB_FLUENTD_SCHEMA")

    def __str__(self):
        """Custom string representation to print each setting on a new line."""
        # Use model_dump() to get a dictionary of the settings
        settings_dict = self.model_dump()
        
        # Format each key-value pair and join them with a newline character ('\n')
        return '\n'.join(
            f"{key}='{value}'" for key, value in settings_dict.items()
        )

# Load settings
try:
    settings = Settings()
    print("--- Settings Loaded ---")
    print(settings) # ✨ Simply print the object
    print("-----------------------")

    if not all([
        settings.kafka_broker,
        settings.kafka_event_log_topic,
        settings.vastdb_endpoint,
        settings.vastdb_data_endpoints,
        settings.vastdb_access_key,
        settings.vastdb_secret_key,
        settings.vastdb_fluentd_bucket,
        settings.vastdb_fluentd_schema,
    ]):
        raise ValueError("All environment variables must be set")
except Exception as e:
    print(f"ERROR: Failed to load configuration: {e}")
    print("Make sure all environment variables are set")
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
            if class_uid == 2003:  # Compliance Finding
                event = ComplianceFinding(**ocsf_data)
                event_class = "Compliance Finding"
                event_cls = ComplianceFinding
            elif class_uid == 2004:  # Detection Finding  
                event = DetectionFinding(**ocsf_data)
                event_class = "Detection Finding"
                event_cls = DetectionFinding
            else:
                return f"[ERROR] Unsupported class_uid: {class_uid}"

        except Exception as e:
            # If all validation fails, extract class info from raw data
            event_class = class_name
            logger.warning(f"Could not validate OCSF event: {e}")

        # Write ComplianceFinding or DetectionFinding to VastDB
        if isinstance(event, (ComplianceFinding, DetectionFinding)):

            # FIXME: session should be created once and reused
            session = connect_to_vastdb(settings.vastdb_endpoint, settings.vastdb_access_key, settings.vastdb_secret_key)

            try:
                pa_table = pydantic_to_arrow_table(event_cls, event)
            except Exception as e:
                import traceback
                return f"[ERROR] Failed to convert Pydantic model to Arrow table: {event_cls} {event} {e} {traceback.format_exc()}"

            try:
                # FIXME: should write batches of events instead of one by one
                write_to_vastdb(session, settings.vastdb_fluentd_bucket, settings.vastdb_fluentd_schema, event_class.lower().replace(" ", "_"), pa_table)
                print(f"Successfully wrote {event_class} to VastDB")
                logger.info(f"Successfully wrote {event_class} to VastDB")
            except Exception as e:
                print(f"Failed to write {event_class} to VastDB: {e} {pa_table}")
                logger.error(f"Failed to write {event_class} to VastDB: {e}")

    except json.JSONDecodeError as e:
        return f"[ERROR] Failed to parse JSON: {e}"
    except Exception as e:
        import traceback
        return f"[ERROR] Error processing event: {e} {traceback.format_exc()} \n\n{kafka_message.value}"

# Apply processing to the successful messages stream
processed_events = op.map("process_events", kafka_input.oks, process_event)

# Inspect processed events
op.inspect("inspect", processed_events)
