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
        """Load config from YAML file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Config file doesn't exist - create directory if needed
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # Return empty structure if no config exists
            return {
                "global_settings": {
                    "dest_host": "192.168.1.252",
                    "rsync_path": "/usr/bin/rsync",
                    "time_path": "/usr/bin/time",
                    "notification": {
                        "telegram_token": "",
                        "telegram_chat_id": ""
                    }
                },
                "backup_jobs": {},
                "backup_logs": {}
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
    
    def log_backup_run(self, job_name, status, message=""):
        """Log a backup run"""
        if 'backup_logs' not in self.config:
            self.config['backup_logs'] = {}
        
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        
        self.config['backup_logs'][job_name] = {
            'last_run': timestamp,
            'status': status,
            'message': message
        }
        self.save_config()
