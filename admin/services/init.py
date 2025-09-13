#!/usr/bin/env python3
"""
Admin Services - System Initialization

Centralized system initialization and service container for Highball.
Manages SSH keypair setup, scheduler bootstrapping, and handler initialization.
"""
import os
import subprocess
import stat
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

from jobs.services.schedule import JobSchedulerHandler
from shared.handlers.templating import TemplateService
from jobs.services.schedule import SchedulingService
from jobs.services.define import JobFormDataBuilder
from shared.handlers.errors import handle_service_errors


class HighballServices:
    """Container for shared application services"""
    
    def __init__(self):
        self.template_service = None
        self.scheduler_service = None
        self.handlers = None
        self.job_form_builder = None
    
    def initialize(self):
        """Initialize all services once at startup"""
        if self.template_service is not None:
            return  # Already initialized

        # Ensure global settings exist
        from shared.services.config import ConfigIOService
        ConfigIOService.ensure_global_settings_exist()

        # Core services
        self.template_service = TemplateService()
        self.scheduler_service = SchedulingService()
        self.job_form_builder = JobFormDataBuilder()

        # Initialize SSH keypair for Highball-managed origins (do not bring down UI if this fails)
        try:
            self._ensure_highball_ssh_keypair()
            print("Highball SSH keypair verified/created")
        except Exception as e:
            print(f"[SSH_KEYS] Warning: SSH key generation failed: {e}")

        # Register schedules (do not bring down UI if this fails)
        try:
            count = self.scheduler_service.bootstrap_schedules()
            print(f"Scheduled {count} backup job(s) from config.")
        except Exception as e:
            print(f"[SCHEDULER] disabled at startup: {e}")

        # Initialize handlers
        from admin.services.notifications import NotificationTestService
        from shared.services.config import ConfigReader

        # Create config adapter for notification service
        class ConfigAdapter:
            def __init__(self):
                self.config_reader = ConfigReader()
            def get_global_settings(self):
                return self.config_reader.get_global_settings()

        self.notification_test = NotificationTestService(ConfigAdapter())
        
        self.handlers = {
            'job_scheduler': JobSchedulerHandler(self.scheduler_service),
        }
    
    def _ensure_highball_ssh_keypair(self):
        """Ensure Highball SSH keypair exists, generate if needed"""
        ssh_dir = "/config/local/secrets/.ssh"
        private_key_path = os.path.join(ssh_dir, "id_highball")
        public_key_path = os.path.join(ssh_dir, "id_highball.pub")
        
        # Check if keypair already exists
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            # Verify permissions on existing key
            try:
                os.chmod(private_key_path, 0o600)
                os.chmod(public_key_path, 0o644)
            except Exception as e:
                print(f"Warning: Could not set SSH key permissions: {e}")
            return
        
        # Create SSH directory if it doesn't exist
        os.makedirs(ssh_dir, exist_ok=True)
        
        # Generate keypair without passphrase for non-interactive use
        print("Generating Highball SSH keypair...")
        cmd = [
            'ssh-keygen', 
            '-t', 'rsa',
            '-b', '2048',
            '-f', private_key_path,
            '-N', '',  # No passphrase
            '-C', 'HIGHBALL@HIGHBALL',
            '-q'  # Quiet mode
        ]
        
        # Run ssh-keygen
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(f"ssh-keygen failed: {result.stderr}")
        
        # Set proper permissions
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        # Create known_hosts file for host key acceptance
        known_hosts_path = os.path.join(ssh_dir, "known_hosts")
        if not os.path.exists(known_hosts_path):
            with open(known_hosts_path, 'w') as f:
                f.write("# SSH known hosts for Highball\n")
            os.chmod(known_hosts_path, 0o644)
    
    @handle_service_errors("Get available themes")
    def get_available_themes(self) -> List[str]:
        """Get list of available theme files from static/themes directory"""
        themes_dir = Path('static/themes')
        if not themes_dir.exists():
            return ['dark', 'light']  # Fallback themes
        
        themes = []
        for theme_file in themes_dir.glob('*.css'):
            theme_name = theme_file.stem
            themes.append(theme_name)
        
        return sorted(themes)
    
    @handle_service_errors("Read raw config")
    def read_raw_config(self, config_path: str) -> str:
        """Read raw configuration file content"""
        if not os.path.exists(config_path):
            return ""
        
        with open(config_path, 'r') as f:
            return f.read()
    
    @handle_service_errors("Save raw config")
    def save_raw_config(self, raw_config: str, config_path: str) -> Dict[str, Any]:
        """Validate and save raw YAML configuration"""
        # Validate YAML syntax
        try:
            yaml.safe_load(raw_config)
        except yaml.YAMLError as e:
            return {
                'success': False,
                'error': f'Invalid YAML syntax: {str(e)}'
            }
        
        # Save to file
        with open(config_path, 'w') as f:
            f.write(raw_config)
        
        return {'success': True}
    
    @handle_service_errors("Generate config YAML")
    def generate_config_yaml(self, config_dict: Dict[str, Any]) -> str:
        """Convert configuration dictionary to YAML format for display"""
        return yaml.dump(config_dict, default_flow_style=False, indent=2)
    
    @handle_service_errors("Preview config changes")
    def preview_config_changes(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate preview of configuration changes from form data"""
        # Load raw YAML from config/local/local.yaml only (not concatenated config)
        import os
        config_file = "/config/local/local.yaml"
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                raw_local_config = yaml.safe_load(f) or {}
        else:
            raw_local_config = {}
        
        # Start with existing global_settings structure
        preview_global_settings = raw_local_config.get('global_settings', {}).copy()
        
        # Apply form changes to the global_settings structure (matching admin form logic)
        for key, value in form_data.items():
            if isinstance(value, list) and len(value) > 0:
                form_value = value[0]
            else:
                form_value = value
            
            # Map form fields to global_settings structure
            if key == 'scheduler_timezone':
                preview_global_settings['scheduler_timezone'] = form_value
            elif key == 'theme':
                preview_global_settings['theme'] = form_value
            elif key == 'enable_conflict_avoidance':
                preview_global_settings['enable_conflict_avoidance'] = (form_value == 'on')
            elif key == 'conflict_check_interval':
                preview_global_settings['conflict_check_interval'] = int(form_value) if form_value.isdigit() else 300
            elif key == 'delay_notification_threshold':
                preview_global_settings['delay_notification_threshold'] = int(form_value) if form_value.isdigit() else 300
            elif key in ['hourly_default', 'daily_default', 'weekly_default', 'monthly_default']:
                # Map to default_schedule_times structure
                schedule_type = key.replace('_default', '')
                if 'default_schedule_times' not in preview_global_settings:
                    preview_global_settings['default_schedule_times'] = {}
                preview_global_settings['default_schedule_times'][schedule_type] = form_value
        
        # Generate YAML preview showing only the global_settings structure
        preview_structure = {'global_settings': preview_global_settings}
        yaml_content = self.generate_config_yaml(preview_structure)
        
        return {
            'success': True,
            'preview_content': yaml_content
        }
    
