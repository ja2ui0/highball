#!/usr/bin/env python3
"""
Shared Configuration I/O Service
Schema-agnostic helpers for config file operations - no domain knowledge
"""
import os
import yaml
import tempfile
import shutil
import glob
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

    @staticmethod
    def ensure_global_settings_exist() -> bool:
        """Ensure global settings file exists with default structure"""
        config_file = "/config/local/local.yaml"

        if os.path.exists(config_file):
            return True

        try:
            # Ensure directory exists
            config_dir = os.path.dirname(config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)

            # Create default global settings structure
            default_config = {
                'global_settings': {
                    "scheduler_timezone": "UTC",
                    "theme": "dark",
                    "default_schedule_times": {
                        "hourly": "0 * * * *",
                        "daily": "0 3 * * *",
                        "weekly": "0 3 * * 0",
                        "monthly": "0 3 1 * *"
                    },
                    "enable_conflict_avoidance": True,
                    "conflict_check_interval": 300,
                    "delay_notification_threshold": 300,
                    "notification": {
                        "telegram": {"enabled": False, "token": "", "chat_id": ""},
                        "email": {"enabled": False, "smtp_server": "", "smtp_port": 587, "use_tls": True, "use_ssl": False, "from_email": "", "to_email": "", "username": "", "password": ""}
                    },
                    "maintenance": {
                        "discard_schedule": "0 3 * * *",
                        "check_schedule": "0 2 * * 0",
                        "retention_policy": {"keep_last": 7, "keep_hourly": 6, "keep_daily": 7, "keep_weekly": 4, "keep_monthly": 6, "keep_yearly": 0},
                        "check_config": {"read_data_subset": "5%"}
                    }
                }
            }

            return ConfigIOService.save_yaml_atomic(config_file, default_config)
        except Exception as e:
            print(f"Error creating default global settings: {str(e)}")
            return False


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

    # =============================================================================
    # ORIGINS DOMAIN READ METHODS - moved verbatim from origins/services/config.py
    # =============================================================================

    def get_ssh_origins(self) -> Dict[str, Any]:
        """Get all SSH origins - read directly from disk for real-time updates"""
        return self._load_ssh_origins()

    def get_ssh_origin(self, origin_name: str) -> Optional[Dict[str, Any]]:
        """Get specific SSH origin - read directly from disk"""
        origins = self._load_ssh_origins()
        return origins.get(origin_name)

    def _load_ssh_origins(self) -> Dict[str, Any]:
        """Load SSH origins from /config/local/origins/*.yaml - no secrets for origins"""
        origins = {}
        origins_dir = "/config/local/origins"

        if not os.path.exists(origins_dir):
            return origins

        # Find all .yaml files in origins directory
        origin_files = glob.glob(os.path.join(origins_dir, "*.yaml"))

        for origin_file in origin_files:
            origin_name = os.path.splitext(os.path.basename(origin_file))[0]

            try:
                # Load origin config using shared service
                origin_config = self.io.load_yaml(origin_file)

                if origin_config is None:
                    print(f"Warning: Empty origin config for {origin_name}")
                    continue

                # No secrets handling for origins - they use only Highball SSH keys
                origins[origin_name] = origin_config

            except Exception as e:
                print(f"Warning: Error loading origin {origin_name}: {str(e)}")
                continue

        return origins

    # =============================================================================
    # DESTINATIONS DOMAIN READ METHODS - moved verbatim from dests/services/config.py
    # =============================================================================

    def get_destinations(self) -> Dict[str, Any]:
        """Get all destinations - read directly from disk for real-time updates"""
        return self._load_destinations()

    def get_destination(self, dest_name: str) -> Optional[Dict[str, Any]]:
        """Get specific destination - read directly from disk"""
        destinations = self._load_destinations()
        return destinations.get(dest_name)

    def _load_destinations(self) -> Dict[str, Any]:
        """Load destinations from /config/local/dests/*.yaml with destination-scoped secrets"""
        import os
        import glob
        from dotenv import dotenv_values

        destinations = {}
        dests_dir = "/config/local/dests"

        if not os.path.exists(dests_dir):
            return destinations

        # Find all .yaml files in destinations directory
        dest_files = glob.glob(os.path.join(dests_dir, "*.yaml"))

        for dest_file in dest_files:
            dest_name = os.path.splitext(os.path.basename(dest_file))[0]

            try:
                # Load destination config using shared service
                dest_config = self.io.load_yaml(dest_file)

                if dest_config is None:
                    print(f"Warning: Empty destination config for {dest_name}")
                    continue

                # Load destination-specific secrets if they exist (scoped per destination)
                secrets_file = f"/config/local/secrets/dests/{dest_name}.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    dest_config = self._merge_secrets(dest_config, secrets)

                destinations[dest_name] = dest_config

            except Exception as e:
                print(f"Warning: Error loading destination {dest_name}: {str(e)}")
                continue

        return destinations

    def _merge_secrets(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Dict[str, Any]:
        """Merge secrets into config by replacing ${VAR} placeholders - delegated to shared service"""
        return self.io.merge_secrets(config, secrets)

    # =============================================================================
    # JOBS DOMAIN READ METHODS - moved verbatim from jobs/services/config.py
    # =============================================================================

    def get_backup_jobs(self) -> Dict[str, Any]:
        """Get all backup jobs - read directly from disk for real-time updates"""
        return self._load_backup_jobs()

    def get_backup_job(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get specific backup job - read directly from disk"""
        jobs = self._load_backup_jobs()
        return jobs.get(job_name)

    def get_deleted_jobs(self) -> Dict[str, Any]:
        """Get all deleted jobs"""
        return self._load_deleted_jobs()

    def _load_backup_jobs(self) -> Dict[str, Any]:
        """Load active jobs from /config/local/jobs/*.yaml"""
        jobs = {}
        jobs_dir = "/config/local/jobs"

        if not os.path.exists(jobs_dir):
            return jobs

        # Find all .yaml files in jobs directory (not in deleted subdirectory)
        job_files = glob.glob(os.path.join(jobs_dir, "*.yaml"))

        for job_file in job_files:
            job_name = os.path.splitext(os.path.basename(job_file))[0]

            try:
                # Load job config using shared service
                job_config = self.io.load_yaml(job_file)

                if job_config is None:
                    print(f"Warning: Empty job config for {job_name}")
                    continue

                jobs[job_name] = job_config

            except Exception as e:
                print(f"Warning: Error loading job {job_name}: {str(e)}")
                continue

        return jobs

    def _load_deleted_jobs(self) -> Dict[str, Any]:
        """Load deleted jobs from /config/local/jobs/deleted/*.yaml"""
        deleted_jobs = {}
        deleted_dir = "/config/local/jobs/deleted"

        if not os.path.exists(deleted_dir):
            return deleted_jobs

        # Find all .yaml files in deleted directory
        deleted_files = glob.glob(os.path.join(deleted_dir, "*.yaml"))

        for deleted_file in deleted_files:
            job_name = os.path.splitext(os.path.basename(deleted_file))[0]

            try:
                # Load deleted job config
                job_config = self.io.load_yaml(deleted_file)

                if job_config is None:
                    print(f"Warning: Empty deleted job config for {job_name}")
                    continue

                deleted_jobs[job_name] = job_config

            except Exception as e:
                print(f"Warning: Error loading deleted job {job_name}: {str(e)}")
                continue

        return deleted_jobs