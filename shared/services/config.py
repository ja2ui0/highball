#!/usr/bin/env python3
"""
Shared Configuration I/O Service
Schema-agnostic helpers for config file operations - no domain knowledge
"""
import os
import yaml
import tempfile
import shutil
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import dotenv_values


class ConfigIOService:
    """Schema-agnostic configuration file I/O operations"""
    
    @staticmethod
    def load_yaml(path: str) -> Optional[Dict[str, Any]]:
        """Load YAML file from path, return None if file doesn't exist or is malformed"""
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                
            if not content:
                return {}
                
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else {}
            
        except Exception as e:
            print(f"Warning: Error loading YAML from {path}: {str(e)}")
            return None
    
    @staticmethod
    def save_yaml_atomic(path: str, data: Dict[str, Any]) -> bool:
        """Save YAML data atomically using temporary file"""
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                yaml.dump(data, temp_file, default_flow_style=False, indent=2)
                temp_path = temp_file.name
            
            # Atomic move
            shutil.move(temp_path, path)
            return True
            
        except Exception as e:
            # Cleanup on failure
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"Error saving YAML to {path}: {str(e)}")
            return False
    
    @staticmethod
    def write_env_atomic(path: str, secrets: Dict[str, str]) -> bool:
        """Write environment file atomically"""
        try:
            # Ensure directory exists
            secrets_dir = os.path.dirname(path)
            if secrets_dir and not os.path.exists(secrets_dir):
                os.makedirs(secrets_dir)
            
            if not secrets:
                # Remove file if no secrets
                if os.path.exists(path):
                    os.remove(path)
                return True
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_file:
                for key, value in secrets.items():
                    temp_file.write(f'{key}="{value}"\n')
                temp_path = temp_file.name
            
            # Atomic move
            shutil.move(temp_path, path)
            return True
            
        except Exception as e:
            # Cleanup on failure
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"Error writing env file to {path}: {str(e)}")
            return False
    
    @staticmethod
    def delete_file(path: str) -> bool:
        """Delete a file safely"""
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting file {path}: {str(e)}")
            return False
    
    @staticmethod
    def backup_file(path: str, reason: str) -> Optional[str]:
        """Backup a file with timestamp and reason"""
        if not os.path.exists(path):
            return None
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{path}.backup.{timestamp}.{reason}"
            shutil.copy2(path, backup_path)
            return backup_path
        except Exception as e:
            print(f"Error backing up file {path}: {str(e)}")
            return None
    
    @staticmethod
    def ensure_dir(path: str) -> bool:
        """Ensure directory exists"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating directory {path}: {str(e)}")
            return False
    
    @staticmethod
    def merge_secrets(config: Any, secrets: Dict[str, str]) -> Any:
        """Merge secrets into config by replacing ${VAR} placeholders recursively"""
        def replace_vars(obj):
            if isinstance(obj, str):
                # Replace ${VAR} patterns with actual values
                for key, value in secrets.items():
                    obj = obj.replace(f"${{{key}}}", value)
                return obj
            elif isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(item) for item in obj]
            else:
                return obj
        
        return replace_vars(config)
    
    @staticmethod
    def load_secrets(path: str) -> Dict[str, str]:
        """Load secrets from .env file"""
        if not os.path.exists(path):
            return {}
        
        try:
            return dotenv_values(path)
        except Exception as e:
            print(f"Warning: Error loading secrets from {path}: {str(e)}")
            return {}


# =============================================================================
# CONFIGURATION READER - all domains read configs via this centralized reader
# =============================================================================

class ConfigReader:
    """Centralized config reader - all domains use this for consistent read access"""

    def __init__(self):
        self.io = ConfigIOService()

    # =============================================================================
    # ADMIN DOMAIN READ METHODS - moved verbatim from admin/services/config.py
    # =============================================================================

    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings with default structure - ALWAYS LOADS FROM DISK FOR EDITING"""
        # CRITICAL: Reload from disk to get current values, not cached values
        fresh_config = self._load_global_settings()
        settings = fresh_config.copy()

        # Ensure notification key exists with empty dict as default
        if 'notification' not in settings:
            settings['notification'] = {}

        return settings

    def _load_global_settings(self) -> Dict[str, Any]:
        """Load global settings from /config/local/local.yaml"""
        config_file = "/config/local/local.yaml"
        local_yaml = ConfigIOService.load_yaml(config_file)

        if local_yaml is None:
            return self._get_default_global_settings()

        # Load user-specific secrets from /config/local/secrets/local.env
        secrets_file = "/config/local/secrets/local.env"
        secrets = ConfigIOService.load_secrets(secrets_file)

        if secrets:
            local_yaml = ConfigIOService.merge_secrets(local_yaml, secrets)

        # Return only the global_settings section from local.yaml
        return local_yaml.get('global_settings', self._get_default_global_settings())

    def _get_default_global_settings(self) -> Dict[str, Any]:
        """Return default global settings structure"""
        return {
            "scheduler_timezone": "UTC",
            "theme": "dark",  # default theme (dark, light, gruvbox, etc.)
            "default_schedule_times": {
                "hourly": "0 * * * *",     # top of every hour
                "daily": "0 3 * * *",      # 3am daily
                "weekly": "0 3 * * 0",     # 3am Sundays
                "monthly": "0 3 1 * *"     # 3am first of month
            },
            "enable_conflict_avoidance": True,  # wait for conflicting jobs before running
            "conflict_check_interval": 300,     # seconds between conflict checks (5 minutes)
            "delay_notification_threshold": 300,  # seconds delay before sending notification (5 minutes)
            "notification": {
                "telegram": {
                    "enabled": False,          # enable/disable telegram notifications globally
                    "token": "",               # Bot token from @BotFather
                    "chat_id": ""              # Chat ID for notifications
                },
                "email": {
                    "enabled": False,          # enable/disable email notifications globally
                    "smtp_server": "",         # e.g. smtp.gmail.com
                    "smtp_port": 587,          # 587 for TLS, 465 for SSL, 25 for plain
                    "use_tls": True,           # use TLS encryption
                    "use_ssl": False,          # use SSL encryption (alternative to TLS)
                    "from_email": "",          # sender email address
                    "to_email": "",            # recipient email address
                    "username": "",            # SMTP authentication username
                    "password": ""             # SMTP authentication password
                }
            },
            "maintenance": {
                "discard_schedule": "0 3 * * *",         # daily at 3am - combines forget+prune operations
                "check_schedule": "0 2 * * 0",           # weekly Sunday 2am (staggered from backups)
                "retention_policy": {
                    "keep_last": 7,        # always keep last 7 snapshots regardless of age
                    "keep_hourly": 6,      # keep 6 most recent hourly snapshots (6 hours coverage)
                    "keep_daily": 7,       # keep 7 most recent daily snapshots (1 week coverage)
                    "keep_weekly": 4,      # keep 4 most recent weekly snapshots (1 month coverage)
                    "keep_monthly": 6,     # keep 6 most recent monthly snapshots (6 months coverage)
                    "keep_yearly": 0       # disable yearly retention by default
                },
                "check_config": {
                    "read_data_subset": "5%"   # balance integrity vs performance
                }
            }
        }