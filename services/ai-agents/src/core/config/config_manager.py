# services/ai-agents/src/core/config/config_manager.py
"""
Configuration Manager - Centralized configuration handling
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    user: str
    catalog: str
    database: str
    schema: str

@dataclass
class ChromaConfig:
    """ChromaDB configuration"""
    host: str
    port: int
    collection_name: str

@dataclass
class ModelConfig:
    """AI Model configuration"""
    model_name: str = "gpt-4o"
    max_tokens: int = 90000
    temperature: float = 0.7
    timeout_seconds: int = 1200

@dataclass
class WorkflowConfig:
    """Workflow configuration"""
    max_agents: int = 6
    approval_timeout: int = 300
    max_messages: int = 60
    enable_structured_output: bool = True

@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    cors_origins: list = None
    log_level: str = "INFO"

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self._database_config: Optional[DatabaseConfig] = None
        self._chroma_config: Optional[ChromaConfig] = None
        self._model_config: Optional[ModelConfig] = None
        self._workflow_config: Optional[WorkflowConfig] = None
        self._server_config: Optional[ServerConfig] = None
        
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all configuration sections"""
        self._database_config = self._load_database_config()
        self._chroma_config = self._load_chroma_config()
        self._model_config = self._load_model_config()
        self._workflow_config = self._load_workflow_config()
        self._server_config = self._load_server_config()
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment"""
        return DatabaseConfig(
            host=os.getenv('TRINO_HOST', 'trino'),
            port=int(os.getenv('TRINO_PORT', '8080')),
            user=os.getenv('TRINO_USER', 'admin'),
            catalog=os.getenv('TRINO_CATALOG', 'vast'),
            database=os.getenv('VASTDB_FLUENTD_BUCKET', 'default_bucket'),
            schema=os.getenv('VASTDB_FLUENTD_SCHEMA', 'default_schema')
        )
    
    def _load_chroma_config(self) -> ChromaConfig:
        """Load ChromaDB configuration"""
        return ChromaConfig(
            host=os.getenv('CHROMA_HOST', 'chroma'),
            port=int(os.getenv('CHROMA_PORT', '8000')),
            collection_name=os.getenv('CHROMA_COLLECTION', 'security_events_dual')
        )
    
    def _load_model_config(self) -> ModelConfig:
        """Load AI model configuration"""
        return ModelConfig(
            model_name=os.getenv('AI_MODEL', 'gpt-4o'),
            max_tokens=int(os.getenv('MAX_TOKENS', '90000')),
            temperature=float(os.getenv('MODEL_TEMPERATURE', '0.7')),
            timeout_seconds=int(os.getenv('MODEL_TIMEOUT', '1200'))
        )
    
    def _load_workflow_config(self) -> WorkflowConfig:
        """Load workflow configuration"""
        return WorkflowConfig(
            max_agents=int(os.getenv('MAX_AGENTS', '6')),
            approval_timeout=int(os.getenv('APPROVAL_TIMEOUT', '300')),
            max_messages=int(os.getenv('MAX_MESSAGES', '60')),
            enable_structured_output=os.getenv('ENABLE_STRUCTURED_OUTPUT', 'true').lower() == 'true'
        )
    
    def _load_server_config(self) -> ServerConfig:
        """Load server configuration"""
        cors_origins = os.getenv('CORS_ORIGINS', '*')
        origins_list = [origins.strip() for origins in cors_origins.split(',')] if cors_origins != '*' else ["*"]
        
        return ServerConfig(
            host=os.getenv('SERVER_HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', '5000')),
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
            cors_origins=origins_list,
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration"""
        return self._database_config
    
    @property
    def chroma(self) -> ChromaConfig:
        """Get ChromaDB configuration"""
        return self._chroma_config
    
    @property
    def model(self) -> ModelConfig:
        """Get AI model configuration"""
        return self._model_config
    
    @property
    def workflow(self) -> WorkflowConfig:
        """Get workflow configuration"""
        return self._workflow_config
    
    @property
    def server(self) -> ServerConfig:
        """Get server configuration"""
        return self._server_config
    
    def get_database_url(self) -> str:
        """Get database connection URL"""
        return f"{self.database.host}:{self.database.port}"
    
    def get_chroma_url(self) -> str:
        """Get ChromaDB connection URL"""
        return f"http://{self.chroma.host}:{self.chroma.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all configs to dictionary"""
        return {
            'database': {
                'host': self.database.host,
                'port': self.database.port,
                'user': self.database.user,
                'catalog': self.database.catalog,
                'database': self.database.database,
                'schema': self.database.schema
            },
            'chroma': {
                'host': self.chroma.host,
                'port': self.chroma.port,
                'collection_name': self.chroma.collection_name
            },
            'model': {
                'model_name': self.model.model_name,
                'max_tokens': self.model.max_tokens,
                'temperature': self.model.temperature,
                'timeout_seconds': self.model.timeout_seconds
            },
            'workflow': {
                'max_agents': self.workflow.max_agents,
                'approval_timeout': self.workflow.approval_timeout,
                'max_messages': self.workflow.max_messages,
                'enable_structured_output': self.workflow.enable_structured_output
            },
            'server': {
                'host': self.server.host,
                'port': self.server.port,
                'debug': self.server.debug,
                'cors_origins': self.server.cors_origins,
                'log_level': self.server.log_level
            }
        }
    
    def validate_config(self) -> bool:
        """Validate all configuration settings"""
        issues = []
        
        # Validate database config
        if not self.database.host:
            issues.append("Database host not configured")
        
        # Validate ChromaDB config
        if not self.chroma.host:
            issues.append("ChromaDB host not configured")
        
        # Validate model config
        if self.model.max_tokens <= 0:
            issues.append("Invalid max_tokens value")
        
        # Validate workflow config
        if self.workflow.max_agents <= 0:
            issues.append("Invalid max_agents value")
        
        if issues:
            raise ValueError(f"Configuration validation failed: {'; '.join(issues)}")
        
        return True
    
    def reload_config(self):
        """Reload all configuration from environment"""
        self._load_all_configs()

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_config_manager: Optional[ConfigManager] = None

def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def reload_config():
    """Reload configuration"""
    global _config_manager
    if _config_manager:
        _config_manager.reload_config()

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    return get_config().database

def get_chroma_config() -> ChromaConfig:
    """Get ChromaDB configuration"""
    return get_config().chroma

def get_model_config() -> ModelConfig:
    """Get AI model configuration"""
    return get_config().model

def get_workflow_config() -> WorkflowConfig:
    """Get workflow configuration"""
    return get_config().workflow

def get_server_config() -> ServerConfig:
    """Get server configuration"""
    return get_config().server

# # ============================================================================
# # ENVIRONMENT SETUP HELPER
# # ============================================================================

# def create_env_template(output_path: str = ".env.template"):
#     """Create environment template file"""
#     template = """# SOC Agent Analysis - Environment Configuration

# # Database Configuration
# TRINO_HOST=trino
# TRINO_PORT=8080
# TRINO_USER=admin
# TRINO_CATALOG=vast
# VASTDB_FLUENTD_BUCKET=your_bucket_name
# VASTDB_FLUENTD_SCHEMA=your_schema_name

# # ChromaDB Configuration
# CHROMA_HOST=chroma
# CHROMA_PORT=8000
# CHROMA_COLLECTION=security_events_dual

# # AI Model Configuration
# AI_MODEL=gpt-4o
# MAX_TOKENS=90000
# MODEL_TEMPERATURE=0.7
# MODEL_TIMEOUT=1200

# # Workflow Configuration
# MAX_AGENTS=6
# APPROVAL_TIMEOUT=300
# MAX_MESSAGES=60
# ENABLE_STRUCTURED_OUTPUT=true

# # Server Configuration
# SERVER_HOST=0.0.0.0
# PORT=5000
# DEBUG=false
# CORS_ORIGINS=*
# LOG_LEVEL=INFO

# # OpenAI API Key (required)
# OPENAI_API_KEY=your_openai_api_key_here
# """
    
#     with open(output_path, 'w') as f:
#         f.write(template)
    
#     print(f"Environment template created at: {output_path}")

# if __name__ == "__main__":
#     # Create environment template when run directly
#     create_env_template()