#!/usr/bin/env python3
"""
OCSF Event Processing Pipeline using Bytewax
Processes OCSF events from Kafka and writes them to VastDB
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Union

import pyarrow as pa
from bytewax import operators as op
from bytewax.connectors.kafka import operators as kop
from bytewax.connectors.stdio import StdOutSink
from bytewax.dataflow import Dataflow
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from py_ocsf_models.events.findings.compliance_finding import ComplianceFinding
from py_ocsf_models.events.findings.detection_finding import DetectionFinding
from py_ocsf_models.events.iam.authentication import Authentication
from py_ocsf_models.events.file_system.file_system_activity import FileSystemActivity

from .pydantic_utils import pydantic_to_arrow_table
from .vastdb_utils import connect_to_vastdb, write_to_vastdb
from . import vectordb_utils

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Kafka settings
    kafka_broker: str
    kafka_event_log_topic: str
    kafka_group_id: str = "ocsf-console-logger"
    
    # VastDB settings
    vastdb_endpoint: str
    vastdb_data_endpoints: str
    vastdb_access_key: str
    vastdb_secret_key: str
    vastdb_fluentd_bucket: str
    vastdb_fluentd_schema: str
    
    # Processing settings
    batch_size: int = 100
    auto_commit_interval_ms: int = 1000
    vastdb_fluentd_table_prefix: str = ""
    enable_raw_kafka_inspector: bool = False

    class Config:
        env_prefix = ""
        case_sensitive = False

    def validate_required_fields(self) -> None:
        """Validate that all required environment variables are set."""
        required_fields = [
            'kafka_broker', 'kafka_event_log_topic', 
            'vastdb_endpoint', 'vastdb_data_endpoints',
            'vastdb_access_key', 'vastdb_secret_key',
            'vastdb_fluentd_bucket', 'vastdb_fluentd_schema'
        ]
        
        missing_fields = [
            field for field in required_fields 
            if not getattr(self, field, None)
        ]
        
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {missing_fields}")

    def __str__(self) -> str:
        """String representation showing all settings."""
        settings_dict = self.model_dump()
        # Mask sensitive values
        masked_keys = ['vastdb_access_key', 'vastdb_secret_key']
        for key in masked_keys:
            if key in settings_dict and settings_dict[key]:
                settings_dict[key] = "*" * 8
        
        return '\n'.join(f"{key}={value}" for key, value in settings_dict.items())


class OCSFEventProcessor:
    """Processes OCSF events and writes them to VastDB."""
    
    # Supported OCSF event types
    SUPPORTED_EVENT_TYPES = {
        1001: (FileSystemActivity, "File System Activity"),
        2003: (ComplianceFinding, "Compliance Finding"),
        2004: (DetectionFinding, "Detection Finding"),
        3002: (Authentication, "Authentication"),
    }
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = None
        self._connect_to_vastdb()
    
    def _connect_to_vastdb(self) -> None:
        """Establish VastDB connection."""
        try:
            self.session = connect_to_vastdb(
                self.settings.vastdb_endpoint,
                self.settings.vastdb_access_key,
                self.settings.vastdb_secret_key
            )
            logger.info("Successfully connected to VastDB")
        except Exception as e:
            logger.error(f"Failed to connect to VastDB: {e}")
            raise
    
    def parse_ocsf_event(self, raw_data: dict) -> tuple[Optional[Union[ComplianceFinding, DetectionFinding, Authentication]], str]:
        """
        Parse and validate OCSF event data.
        
        Returns:
            Tuple of (validated_event, event_class_name)
        """
        class_uid = raw_data.get('class_uid')
        class_name = raw_data.get('class_name', 'Unknown')
        
        if class_uid not in self.SUPPORTED_EVENT_TYPES:
            # logger.warning(f"Unsupported class_uid: {class_uid}")
            return None, class_name
        
        event_cls, event_class_name = self.SUPPORTED_EVENT_TYPES[class_uid]
        
        try:
            validated_event = event_cls(**raw_data)
            return validated_event, event_class_name
        except Exception as e:
            if event_class_name == "Authentication":
                logger.warning(f"Failed to validate {event_class_name}: {e}")
                logger.warning(f"Sample data keys: {list(raw_data.keys())[:10]}")
            else:
                logger.error(f"Failed to validate {event_class_name}: {e}")
            return None, event_class_name
    
    def write_event_to_vastdb(self, event: Union[ComplianceFinding, DetectionFinding, Authentication], 
                             event_class_name: str) -> bool:
        """
        Write validated event to VastDB and ChromaDB.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert to Arrow table
            event_cls = type(event)
            pa_table = pydantic_to_arrow_table(event_cls, event)
            
            # Write to VastDB
            table_name = f"{self.settings.vastdb_fluentd_table_prefix}{event_class_name.lower().replace(' ', '_')}"
            write_to_vastdb(
                self.session,
                self.settings.vastdb_fluentd_bucket,
                self.settings.vastdb_fluentd_schema,
                table_name,
                pa_table
            )
            
            # Write to ChromaDB
            try:
                event_text = event.json()
                embedding_raw = vectordb_utils.embed_text(event_text)
                embedding_norm = vectordb_utils.normalize_embedding(embedding_raw)
                vectordb_utils.insert_event(event_text, embedding_raw, embedding_norm)
                logger.info(f"Successfully wrote {event_class_name} to ChromaDB")
            except Exception as chroma_exc:
                logger.error(f"Failed to write {event_class_name} to ChromaDB: {chroma_exc}")
            
            logger.info(f"Successfully wrote {event_class_name} to VastDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write {event_class_name} to VastDB: {e}")
            return False
    
    def process_kafka_message(self, kafka_message) -> str:
        """
        Process a single Kafka message containing OCSF event data.
        
        Returns:
            Processing result message
        """
        try:
            # Parse JSON payload
            try:
                ocsf_data = json.loads(kafka_message.value)
            except json.JSONDecodeError as e:
                return f"[ERROR] Invalid JSON: {e}"
            
            # Parse and validate OCSF event
            event, event_class_name = self.parse_ocsf_event(ocsf_data)
            
            if event is None:
                logger.debug(f"Skipping unsupported or invalid event type: {event_class_name} {kafka_message.value}")
                return f"[SKIPPED] Unsupported or invalid event type: {event_class_name}"
            
            # Write to VastDB
            success = self.write_event_to_vastdb(event, event_class_name)
            
            if success:
                return f"[SUCCESS] Processed {event_class_name}"
            else:
                return f"[ERROR] Failed to write {event_class_name} to VastDB"
                
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            return f"[ERROR] Unexpected error: {e}"


def raw_kafka_inspector(step_id, item):
    print(f"RAW KAFKA MESSAGE: {step_id} - {item}")

def count_inspector(step_id, item):
    if not hasattr(count_inspector, 'counts'):
        count_inspector.counts = {
            'total': 0,
            'success': 0,
            'error': 0,
            'skipped': 0,
            'by_event_class': {}
        }
    
    count_inspector.counts['total'] += 1
    
    # Parse the result message to categorize
    if isinstance(item, str):
        if item.startswith('[SUCCESS]'):
            count_inspector.counts['success'] += 1
            # Extract event class for detailed tracking
            if 'Processed ' in item:
                event_class = item.split('Processed ')[1]
                if event_class not in count_inspector.counts['by_event_class']:
                    count_inspector.counts['by_event_class'][event_class] = {'success': 0, 'error': 0, 'skipped': 0}
                count_inspector.counts['by_event_class'][event_class]['success'] += 1
                
        elif item.startswith('[ERROR]'):
            count_inspector.counts['error'] += 1
            
        elif item.startswith('[SKIPPED]'):
            count_inspector.counts['skipped'] += 1
            # Extract event class for skipped items too
            if 'event type: ' in item:
                event_class = item.split('event type: ')[1]
                if event_class not in count_inspector.counts['by_event_class']:
                    count_inspector.counts['by_event_class'][event_class] = {'success': 0, 'error': 0, 'skipped': 0}
                count_inspector.counts['by_event_class'][event_class]['skipped'] += 1
    
    # Print summary every 100 items
    if count_inspector.counts['total'] % 100 == 0:
        total = count_inspector.counts['total']
        success = count_inspector.counts['success']
        error = count_inspector.counts['error']
        skipped = count_inspector.counts['skipped']
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        print(f"\n=== {step_id} Summary (Total: {total}) ===")
        print(f"✅ SUCCESS: {success} ({success_rate:.1f}%)")
        print(f"❌ ERROR:   {error} ({error/total*100:.1f}%)" if total > 0 else "❌ ERROR:   0")
        print(f"⏭️  SKIPPED: {skipped} ({skipped/total*100:.1f}%)" if total > 0 else "⏭️  SKIPPED: 0")
        
        # Show breakdown by event class if we have data
        if count_inspector.counts['by_event_class']:
            print("📊 By Event Class:")
            for event_class, counts in count_inspector.counts['by_event_class'].items():
                type_total = counts['success'] + counts['error'] + counts['skipped']
                if type_total > 0:
                    print(f"   {event_class}: {counts['success']}✅ {counts['error']}❌ {counts['skipped']}⏭️")
        print("=" * 50)

def create_dataflow(settings: Settings) -> Dataflow:
    """Create and configure the Bytewax dataflow."""
    
    # Initialize event processor
    processor = OCSFEventProcessor(settings)
    
    # Create dataflow
    flow = Dataflow("ocsf_dataflow")
    
    # Kafka consumer configuration
    kafka_config = {
        "group.id": settings.kafka_group_id,
        "enable.auto.commit": "true",
        "auto.commit.interval.ms": str(settings.auto_commit_interval_ms)
    }
    
    # Kafka input stream
    kafka_input = kop.input(
        "kafka_input",
        flow,
        brokers=[settings.kafka_broker],
        topics=[settings.kafka_event_log_topic],
        add_config=kafka_config
    )
    
    if settings.enable_raw_kafka_inspector:
        op.inspect("raw_kafka", kafka_input.oks, raw_kafka_inspector)
    
    # Process events
    processed_events = op.map(
        "process_events", 
        kafka_input.oks, 
        processor.process_kafka_message
    )

    op.inspect("summary", processed_events, count_inspector)

    return flow


# Initialize application and create flow at module level for Bytewax
try:
    # Load and validate configuration
    settings = Settings()
    settings.validate_required_fields()
    
    logger.info("=== OCSF Dataflow Configuration ===")
    logger.info(f"\n{settings}")
    logger.info("=" * 35)
    
    # Create dataflow - this must be at module level for Bytewax to find it
    flow = create_dataflow(settings)
    logger.info("OCSF dataflow created successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    raise
