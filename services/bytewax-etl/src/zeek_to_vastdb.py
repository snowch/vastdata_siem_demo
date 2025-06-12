#!/usr/bin/env python3
"""
Zeek Log Processing Pipeline using Bytewax
Processes Zeek logs from Kafka and writes them to VastDB
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

import pyarrow as pa
from bytewax import operators as op
from bytewax.connectors.kafka import operators as kop
from bytewax.connectors.stdio import StdOutSink
from bytewax.dataflow import Dataflow
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .pydantic_utils import pydantic_to_arrow_table
from .vastdb_utils import connect_to_vastdb, write_to_vastdb
from .zeek_models import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Kafka settings
    kafka_broker: str
    kafka_zeek_topic: str
    kafka_group_id: str = "zeek-consumer-group"
    
    # VastDB settings
    vastdb_endpoint: str
    vastdb_access_key: str
    vastdb_secret_key: str
    vastdb_zeek_bucket: str
    vastdb_zeek_schema: str
    
    # Processing settings
    batch_size: int = 100
    auto_commit_interval_ms: int = 1000
    vastdb_zeek_table_prefix: str = ""

    class Config:
        env_prefix = ""
        case_sensitive = False

    def validate_required_fields(self) -> None:
        """Validate that all required environment variables are set."""
        required_fields = [
            'kafka_broker', 'kafka_zeek_topic', 
            'vastdb_endpoint', 'vastdb_access_key', 'vastdb_secret_key',
            'vastdb_zeek_bucket', 'vastdb_zeek_schema'
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

class ZeekLogProcessor:
    """Processes Zeek logs and writes them to VastDB."""
    
    # Supported Zeek log types
    SUPPORTED_LOG_TYPES = {
        'analyzer': ("ZeekAnalyzerLog", "Analyzer Log"),
        'conn': ("ZeekConnLog", "Connection Log"),
        'http': ("ZeekHttpLog", "HTTP Log"),
        'dns': ("ZeekDnsLog", "DNS Log"),
        'ssl': ("ZeekSslLog", "SSL Log"),
        'weird': ("ZeekWeirdLog", "Weird Log"),
        'ftp': ("ZeekFtpLog", "FTP Log"),
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
    
    def parse_and_validate_zeek_log(self, raw_data: dict) -> tuple[Optional[BaseModel], str]:
        """
        Parse and validate Zeek log data using Pydantic models.
        
        Returns:
            Tuple of (validated_log_model, log_type)
        """
        try:
            # Get the top-level key (log type)
            if not raw_data or not isinstance(raw_data, dict):
                return None, "unknown"
            
            log_type = list(raw_data.keys())[0]
            log_data = raw_data[log_type]
            
            if not isinstance(log_data, dict):
                return None, log_type
            
            # Check if we have a supported log type
            if log_type not in self.SUPPORTED_LOG_TYPES:
                logger.warning(f"Unsupported log type: {log_type}")
                return None, log_type
            
            # Get the appropriate Pydantic model
            model_cls, model_name = self.SUPPORTED_LOG_TYPES[log_type]
            
            # Convert timestamp if present
            if 'ts' in log_data:
                ts_datetime = self.convert_timestamp(log_data['ts'])
                if ts_datetime:
                    log_data['ts'] = ts_datetime
            
            # Validate using Pydantic model
            try:
                validated_log = globals()[model_cls](**log_data)
                return validated_log, log_type
            except Exception as validation_error:
                logger.error(f"Failed to validate {model_name}: {validation_error}")
                return None, log_type
            
        except Exception as e:
            logger.error(f"Failed to parse Zeek log: {e}")
            return None, "unknown"
    
    def convert_timestamp(self, ts_value: Any) -> Optional[datetime]:
        """Convert timestamp value to datetime object."""
        if ts_value is None:
            return None
        
        try:
            if isinstance(ts_value, str):
                # Try parsing as ISO format first
                try:
                    return datetime.fromisoformat(ts_value.replace('Z', '+00:00'))
                except:
                    # Try parsing as float string
                    ts_float = float(ts_value)
                    return datetime.fromtimestamp(ts_float)
            elif isinstance(ts_value, (int, float)):
                return datetime.fromtimestamp(ts_value)
            else:
                return None
        except Exception as e:
            logger.warning(f"Failed to convert timestamp {ts_value}: {e}")
            return None
    
    def write_log_to_vastdb(self, validated_log: BaseModel, log_type: str) -> bool:
        """
        Write validated Zeek log to VastDB using pydantic_utils.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the model class
            model_cls = type(validated_log).__name__
            
            # Convert to Arrow table using pydantic_utils
            pa_table = pydantic_to_arrow_table(globals()[model_cls], validated_log)
            
            if pa_table is None or pa_table.num_rows == 0:
                logger.warning(f"No data to write for log type: {log_type}")
                return False
            
            # Create table name
            clean_log_type = log_type.replace("-", "_").replace(".", "_")
            table_name = f"{self.settings.vastdb_zeek_table_prefix}{clean_log_type}"
            
            # Write to VastDB
            write_to_vastdb(
                self.session,
                self.settings.vastdb_zeek_bucket,
                self.settings.vastdb_zeek_schema,
                table_name,
                pa_table
            )
            
            logger.info(f"Successfully wrote {log_type} log to VastDB table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write {log_type} log to VastDB: {e}")
            return False
    
    def process_kafka_message(self, kafka_message) -> str:
        """
        Process a single Kafka message containing Zeek log data.
        
        Returns:
            Processing result message
        """
        try:
            # Parse JSON payload
            try:
                zeek_data = json.loads(kafka_message.value)
            except json.JSONDecodeError as e:
                return f"[ERROR] Invalid JSON: {e}"
            
            # Parse and validate Zeek log using Pydantic models
            validated_log, log_type = self.parse_and_validate_zeek_log(zeek_data)
            
            if validated_log is None:
                return f"[SKIPPED] Invalid or unsupported log data for type: {log_type}"
            
            # Write to VastDB
            success = self.write_log_to_vastdb(validated_log, log_type)
            
            if success:
                return f"[SUCCESS] Processed {log_type} log"
            else:
                return f"[ERROR] Failed to write {log_type} log to VastDB"
                
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            return f"[ERROR] Unexpected error: {e}"


def create_dataflow(settings: Settings) -> Dataflow:
    """Create and configure the Bytewax dataflow."""
    
    # Initialize log processor
    processor = ZeekLogProcessor(settings)
    
    # Create dataflow
    flow = Dataflow("zeek_dataflow")
    
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
        topics=[settings.kafka_zeek_topic],
        add_config=kafka_config
    )
    
    # Process logs
    processed_logs = op.map(
        "process_logs", 
        kafka_input.oks, 
        processor.process_kafka_message
    )
    
    # Inspect results for monitoring
    op.inspect("inspect_results", processed_logs)
    
    return flow


# Initialize application and create flow at module level for Bytewax
try:
    # Load and validate configuration
    settings = Settings()
    settings.validate_required_fields()
    
    logger.info("=== Zeek Dataflow Configuration ===")
    logger.info(f"\n{settings}")
    logger.info("=" * 35)
    
    # Create dataflow - this must be at module level for Bytewax to find it
    flow = create_dataflow(settings)
    logger.info("Zeek dataflow created successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    raise
