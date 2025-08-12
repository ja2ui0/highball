#!/usr/bin/env python3
"""
Configuration manager for backup system
Handles loading/saving YAML config files
"""
import os
import yaml
class BackupConfig:
    """Manages the backup configuration in YAML format"""
    
    def __init__(self, config_file="/config/config.yaml"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load config from YAML file with robust error handling"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    content = f.read().strip()
                    
                # Handle empty or whitespace-only files
                if not content:
                    return self._get_default_config()
                    
                config = yaml.safe_load(content)
                
                # Handle None result from yaml.safe_load
                if config is None:
                    return self._get_default_config()
                    
                # Validate config structure
                if not isinstance(config, dict):
                    self._backup_malformed_config("Config is not a valid dictionary")
                    return self._get_default_config()
                
                return config
                
            except yaml.YAMLError as e:
                # Handle invalid YAML - backup and use defaults
                self._backup_malformed_config(f"YAML syntax error: {str(e)}")
                return self._get_default_config()
            except Exception as e:
                # Handle other file reading errors
                self._backup_malformed_config(f"File reading error: {str(e)}")
                return self._get_default_config()
        else:
            # Config file doesn't exist - create directory if needed
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            return self._get_default_config()
    
    def _backup_malformed_config(self, error_reason):
        """Backup malformed config file and log the issue"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.config_file}.malformed.{timestamp}"
        
        try:
            # Copy the malformed file to backup location
            import shutil
            shutil.copy2(self.config_file, backup_path)
            
            # Log the issue (this will be visible in application logs)
            print(f"WARNING: Malformed config detected - {error_reason}")
            print(f"WARNING: Backed up malformed config to: {backup_path}")
            print(f"WARNING: Using default configuration. Check the backup file and repair if needed.")
            
            # Store the warning in memory so the web interface can show it
            self._config_warning = {
                'message': f"Malformed config detected: {error_reason}",
                'backup_path': backup_path,
                'timestamp': timestamp
            }
            
        except Exception as backup_error:
            print(f"ERROR: Could not backup malformed config: {str(backup_error)}")
            # Still use defaults even if backup fails
    
    def get_config_warning(self):
        """Get any config loading warnings for display in web interface"""
        return getattr(self, '_config_warning', None)
    
    def clear_config_warning(self):
        """Clear the config warning (after user acknowledges it)"""
        if hasattr(self, '_config_warning'):
            delattr(self, '_config_warning')
    
    def _get_default_config(self):
        """Return default configuration structure"""
        return {
            "global_settings": {
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
                        "enabled": False,          # enable/disable telegram notifications
                        "notify_on_success": False,# send telegram notifications for successful jobs
                        "token": "",               # Bot token from @BotFather
                        "chat_id": ""              # Chat ID for notifications
                    },
                    "email": {
                        "enabled": False,          # enable/disable email notifications
                        "notify_on_success": False,# send email notifications for successful jobs
                        "smtp_server": "",         # e.g. smtp.gmail.com
                        "smtp_port": 587,          # 587 for TLS, 465 for SSL, 25 for plain
                        "use_tls": True,           # use TLS encryption
                        "use_ssl": False,          # use SSL encryption (alternative to TLS)
                        "from_email": "",          # sender email address
                        "to_email": "",            # recipient email address  
                        "username": "",            # SMTP authentication username
                        "password": ""             # SMTP authentication password
                    }
                }
            },
            "backup_jobs": {}
        }
    
    def save_config(self, config=None):
        """Save config to YAML file"""
        if config:
            self.config = config
        
        # Ensure directory exists
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
    
    def get_backup_jobs(self):
        """Get all backup jobs"""
        return self.config.get('backup_jobs', {})
    
    def get_backup_job(self, job_name):
        """Get specific backup job"""
        return self.config.get('backup_jobs', {}).get(job_name)
    
    def add_backup_job(self, job_name, job_config):
        """Add or update a backup job"""
        if 'backup_jobs' not in self.config:
            self.config['backup_jobs'] = {}
        self.config['backup_jobs'][job_name] = job_config
        self.save_config()
    
    def delete_backup_job(self, job_name):
        """Delete a backup job"""
        if 'backup_jobs' in self.config and job_name in self.config['backup_jobs']:
            del self.config['backup_jobs'][job_name]
            self.save_config()
            return True
        return False
    
    def get_global_settings(self):
        """Get global settings"""
        return self.config.get('global_settings', {})
    
    def update_global_settings(self, settings):
        """Update global settings"""
        if 'global_settings' not in self.config:
            self.config['global_settings'] = {}
        self.config['global_settings'].update(settings)
        self.save_config()
    
