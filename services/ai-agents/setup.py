#!/usr/bin/env python3
"""
SOC Agent Analysis Setup Script
Automated setup and validation for the refactored codebase
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any

class SetupManager:
    """Manages setup and validation of the SOC Agent Analysis system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.issues = []
        self.warnings = []
        
    def run_setup(self):
        """Run complete setup process"""
        print("🚀 SOC Agent Analysis - Refactored Setup")
        print("=" * 50)
        
        try:
            self.validate_python_version()
            self.check_environment_file()
            self.validate_directory_structure()
            self.check_dependencies()
            self.validate_configuration()
            self.check_docker_setup()
            self.validate_static_files()
            self.run_basic_tests()
            
            self.print_summary()
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)
    
    def validate_python_version(self):
        """Check Python version compatibility"""
        print("\n🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 10):
            self.issues.append("Python 3.10+ required, found {}.{}.{}".format(
                version.major, version.minor, version.micro
            ))
        else:
            print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
    
    def check_environment_file(self):
        """Check environment configuration"""
        print("\n⚙️ Checking environment configuration...")
        
        env_file = self.project_root / ".env"
        env_template = self.project_root / ".env.template"
        
        if not env_file.exists():
            if env_template.exists():
                print("⚠️ .env file not found, but .env.template exists")
                self.warnings.append("Copy .env.template to .env and configure it")
            else:
                # Create template
                self.create_env_template()
                self.warnings.append("Created .env.template - please copy to .env and configure")
        else:
            print("✅ .env file found")
            self.validate_env_variables()
    
    def create_env_template(self):
        """Create environment template"""
        from src.core.config.config_manager import create_env_template
        create_env_template(str(self.project_root / ".env.template"))
        print("📝 Created .env.template")
    
    def validate_env_variables(self):
        """Validate environment variables"""
        required_vars = [
            "VASTDB_FLUENTD_BUCKET",
            "VASTDB_FLUENTD_SCHEMA",
            "OPENAI_API_KEY"
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            self.warnings.append(f"Missing environment variables: {', '.join(missing)}")
        else:
            print("✅ Required environment variables present")
    
    def validate_directory_structure(self):
        """Validate project directory structure"""
        print("\n📁 Validating directory structure...")
        
        required_dirs = [
            "src/api/routes",
            "src/core/agents",
            "src/core/services", 
            "src/core/models",
            "src/core/config",
            "src/infrastructure",
            "src/static/js/modules",
            "src/static/css"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)
        
        if missing_dirs:
            self.issues.append(f"Missing directories: {', '.join(missing_dirs)}")
        else:
            print("✅ Directory structure - OK")
    
    def check_dependencies(self):
        """Check Python dependencies"""
        print("\n📦 Checking dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            self.warnings.append("requirements.txt not found")
            return
        
        try:
            # Check if main dependencies are importable
            import fastapi
            import uvicorn
            import openai
            import chromadb
            print("✅ Core dependencies available")
        except ImportError as e:
            self.warnings.append(f"Missing dependency: {e.name}")
    
    def validate_configuration(self):
        """Validate configuration management"""
        print("\n⚙️ Validating configuration...")
        
        try:
            # Import config manager to test it
            sys.path.insert(0, str(self.project_root / "src"))
            from core.config.config_manager import get_config
            
            config = get_config()
            config.validate_config()
            print("✅ Configuration validation - OK")
            
        except Exception as e:
            self.warnings.append(f"Configuration validation failed: {e}")
    
    def check_docker_setup(self):
        """Check Docker configuration"""
        print("\n🐳 Checking Docker setup...")
        
        docker_files = [
            "Dockerfile",
            "../../docker-compose.yml"  # Parent directory
        ]
        
        found_docker = False
        for docker_file in docker_files:
            if (self.project_root / docker_file).exists():
                found_docker = True
                print(f"✅ Found {docker_file}")
        
        if not found_docker:
            self.warnings.append("No Docker configuration found")
    
    def validate_static_files(self):
        """Validate static files structure"""
        print("\n🎨 Validating static files...")
        
        required_files = [
            "src/static/dashboard.html",
            "src/static/css/main.css",
            "src/static/js/main.js",
            "src/static/js/modules/event-manager.js",
            "src/static/js/modules/keyboard-manager.js",
            "src/static/js/modules/ui-helper.js"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.warnings.append(f"Missing static files: {', '.join(missing_files)}")
        else:
            print("✅ Static files structure - OK")
    
    def run_basic_tests(self):
        """Run basic validation tests"""
        print("\n🧪 Running basic tests...")
        
        try:
            # Test configuration loading
            sys.path.insert(0, str(self.project_root / "src"))
            from core.config.config_manager import get_config
            config = get_config()
            
            # Test message registry
            from core.messaging.simple_registry import SimpleMessageRegistry
            registry = SimpleMessageRegistry()
            
            # Test that basic components can be imported
            from core.agents.base import BaseAgent
            
            print("✅ Basic component tests - OK")
            
        except Exception as e:
            self.warnings.append(f"Basic tests failed: {e}")
    
    def print_summary(self):
        """Print setup summary"""
        print("\n" + "=" * 50)
        print("📋 SETUP SUMMARY")
        print("=" * 50)
        
        if not self.issues and not self.warnings:
            print("🎉 Setup completed successfully!")
            print("\n🚀 Ready to start the SOC Agent Analysis system")
            print("\nNext steps:")
            print("1. Start the services: docker-compose up -d")
            print("2. Access dashboard: http://localhost:5000")
            
        else:
            if self.issues:
                print("\n❌ CRITICAL ISSUES:")
                for issue in self.issues:
                    print(f"   • {issue}")
            
            if self.warnings:
                print("\n⚠️ WARNINGS:")
                for warning in self.warnings:
                    print(f"   • {warning}")
            
            if self.issues:
                print("\n❌ Please fix critical issues before proceeding")
                sys.exit(1)
            else:
                print("\n✅ Setup completed with warnings")
                print("⚠️ Please review warnings for optimal performance")
    
    def create_development_config(self):
        """Create development configuration files"""
        print("\n🛠️ Creating development configuration...")
        
        # Create VS Code settings for better development
        vscode_dir = self.project_root / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        
        settings = {
            "python.pythonPath": "./venv/bin/python",
            "python.defaultInterpreterPath": "./venv/bin/python",
            "files.exclude": {
                "**/__pycache__": True,
                "**/*.pyc": True,
                "node_modules": True
            },
            "python.linting.enabled": True,
            "python.linting.pylintEnabled": True,
            "python.formatting.provider": "black"
        }
        
        with open(vscode_dir / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        
        print("✅ Created VS Code settings")

def main():
    """Main setup function"""
    setup_manager = SetupManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--dev":
        setup_manager.create_development_config()
    
    setup_manager.run_setup()

if __name__ == "__main__":
    main()