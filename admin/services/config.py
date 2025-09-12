#!/usr/bin/env python3
"""
Admin domain configuration service
Handles CRUD operations for global settings (/config/local/local.yaml)
"""
import os
import yaml
from typing import Dict, Any
from shared.services.config import ConfigIOService
from admin.schema import PROVIDER_FIELD_SCHEMAS
from models.forms import safe_get_value


class AdminConfigService:
    """Domain service for admin configuration management - global settings only"""
    
    def __init__(self):
        self.config_file = "/config/local/local.yaml"
    
    # =============================================================================
    # GLOBAL SETTINGS CRUD METHODS - moved from root config.py
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
    
    def update_global_settings(self, settings: Dict[str, Any]) -> bool:
        """Update global settings and save only global settings to local.yaml"""
        # Load existing local.yaml to preserve any manual edits
        local_yaml = ConfigIOService.load_yaml(self.config_file) or {}
        
        # Update only the global_settings section
        local_yaml['global_settings'] = settings
        
        # Save only global settings to local.yaml
        return ConfigIOService.save_yaml_atomic(self.config_file, local_yaml)
    
    def _load_global_settings(self) -> Dict[str, Any]:
        """Load global settings from /config/local/local.yaml"""
        local_yaml = ConfigIOService.load_yaml(self.config_file)
        
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
    # BUSINESS LOGIC METHODS - moved from manage.py
    # =============================================================================
    
    def save_structured_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save structured configuration from form data - contains all business logic"""
        try:
            # Get current configuration and update global settings
            global_settings = self.get_global_settings()
            
            # Update basic settings only if provided in form
            scheduler_timezone = safe_get_value(form_data, 'scheduler_timezone', '')
            if scheduler_timezone:
                global_settings['scheduler_timezone'] = scheduler_timezone
            
            # Update theme if provided
            theme = safe_get_value(form_data, 'theme', '')
            if theme:
                global_settings['theme'] = theme
            
            global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
            global_settings['conflict_check_interval'] = int(safe_get_value(form_data, 'conflict_check_interval', '300'))
            global_settings['delay_notification_threshold'] = int(safe_get_value(form_data, 'delay_notification_threshold', '300'))
            
            # Default schedule times
            default_schedule_times = global_settings.setdefault('default_schedule_times', {})
            default_schedule_times['hourly'] = safe_get_value(form_data, 'hourly_default', '0 * * * *')
            default_schedule_times['daily'] = safe_get_value(form_data, 'daily_default', '0 3 * * *')
            default_schedule_times['weekly'] = safe_get_value(form_data, 'weekly_default', '0 3 * * 0')
            default_schedule_times['monthly'] = safe_get_value(form_data, 'monthly_default', '0 3 1 * *')
            
            # Notification settings
            self._update_notification_settings(global_settings, form_data)
            
            # Save only global settings to local.yaml (not domain configs)
            success = self.update_global_settings(global_settings)
            
            if success:
                return {'success': True, 'message': 'Configuration saved successfully'}
            else:
                return {'success': False, 'error': 'Failed to save configuration to disk'}
            
        except Exception as e:
            return {'success': False, 'error': f'Configuration save failed: {str(e)}'}
    
    def preview_config_changes_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preview configuration changes without saving - contains all business logic"""
        # Start with current configuration to preserve existing notification settings
        current_config = {'global_settings': self.get_global_settings().copy()}
        preview_config = current_config.copy()
        global_settings = preview_config['global_settings']
        
        # Basic settings - only update if provided in form
        scheduler_timezone = safe_get_value(form_data, 'scheduler_timezone', '')
        if scheduler_timezone:
            global_settings['scheduler_timezone'] = scheduler_timezone
        theme = safe_get_value(form_data, 'theme', '')
        if theme:
            global_settings['theme'] = theme
            
        global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
        global_settings['conflict_check_interval'] = int(safe_get_value(form_data, 'conflict_check_interval', '300'))
        global_settings['delay_notification_threshold'] = int(safe_get_value(form_data, 'delay_notification_threshold', '300'))
        
        # Default schedule times
        default_schedule_times = global_settings.setdefault('default_schedule_times', {})
        default_schedule_times['hourly'] = safe_get_value(form_data, 'hourly_default', '0 * * * *')
        default_schedule_times['daily'] = safe_get_value(form_data, 'daily_default', '0 3 * * *')
        default_schedule_times['weekly'] = safe_get_value(form_data, 'weekly_default', '0 3 * * 0')
        default_schedule_times['monthly'] = safe_get_value(form_data, 'monthly_default', '0 3 1 * *')
        
        # Notification settings (preview only - preserve existing settings)
        self._update_notification_settings(global_settings, form_data)
        
        # Convert to YAML for display
        yaml_content = yaml.dump(preview_config, default_flow_style=False, sort_keys=False)
        
        return {
            'success': True,
            'yaml_content': yaml_content,
            'preview_config': preview_config
        }
    
    def add_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new notification provider to configuration"""
        try:
            provider = safe_get_value(form_data, 'add_provider')
            if not provider or provider not in ['telegram', 'email']:
                return {'success': False, 'error': 'Invalid provider selection'}
            
            # Get current config and add empty provider section
            global_settings = self.get_global_settings()
            notification_config = global_settings.setdefault('notification', {})
            
            # Add provider with default settings
            provider_schema = PROVIDER_FIELD_SCHEMAS.get(provider, {})
            provider_config = {}
            
            # Set default values for all fields
            for field_info in provider_schema.get('fields', []):
                if 'default' in field_info:
                    provider_config[field_info['name']] = field_info['default']
                elif field_info['type'] == 'checkbox':
                    # Default checkboxes to False to make config truthy
                    provider_config[field_info['name']] = False
            
            # Ensure the config is truthy even if no defaults were set
            if not provider_config:
                # Add a marker field to make the config truthy for template rendering
                provider_config['_configured'] = True
            
            notification_config[provider] = provider_config
            
            # Save the updated configuration
            success = self.update_global_settings(global_settings)
            
            if success:
                return {'success': True, 'provider': provider}
            else:
                return {'success': False, 'error': 'Failed to save provider configuration'}
            
        except Exception as e:
            return {'success': False, 'error': f'Add provider failed: {str(e)}'}

    def remove_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a notification provider from configuration"""
        try:
            provider = safe_get_value(form_data, 'provider')
            if not provider or provider not in ['telegram', 'email']:
                return {'success': False, 'error': 'Invalid provider'}
            
            # Get current config and remove provider section
            global_settings = self.get_global_settings()
            notification_config = global_settings.get('notification', {})
            
            if provider in notification_config:
                del notification_config[provider]
                
                # Save the updated configuration
                success = self.update_global_settings(global_settings)
                
                if success:
                    return {'success': True, 'provider': provider}
                else:
                    return {'success': False, 'error': 'Failed to save configuration changes'}
            else:
                return {'success': False, 'error': f'{provider} provider not found'}
                
        except Exception as e:
            return {'success': False, 'error': f'Remove provider failed: {str(e)}'}
    
    def _update_notification_settings(self, global_settings: dict, form_data: Dict[str, Any]):
        """Update notification settings from form data"""
        notification_config = global_settings.setdefault('notification', {})
        
        # Process each provider's configuration
        for provider_name, provider_schema in PROVIDER_FIELD_SCHEMAS.items():
            # Only process if provider fields are present in form
            if any(f"{provider_name}_{field['name']}" in form_data for field in provider_schema.get('fields', [])):
                provider_config = notification_config.setdefault(provider_name, {})
                
                # Process individual fields
                for field_info in provider_schema.get('fields', []):
                    self._process_notification_field(provider_config, provider_name, field_info, form_data)

    def _process_notification_field(self, provider_config: dict, provider_name: str, field_info: dict, form_data: Dict[str, Any]):
        """Process a single notification field from form data"""
        field_name = f"{provider_name}_{field_info['name']}"
        
        if field_info['type'] == 'checkbox':
            provider_config[field_info['name']] = field_name in form_data
        elif field_info['type'] == 'select':
            # Handle select with config_field mapping (e.g., encryption)
            select_value = safe_get_value(form_data, field_name, '')
            
            if 'options' in field_info:
                # Reset all config_field booleans first
                for option in field_info['options']:
                    if 'config_field' in option:
                        provider_config[option['config_field']] = False
                
                # Set the selected option's config_field to True
                for option in field_info['options']:
                    if option['value'] == select_value and 'config_field' in option:
                        provider_config[option['config_field']] = True
                        break
                        
                # Also store the select value itself
                provider_config[field_info['name']] = select_value
        else:
            # Handle text, password, number fields
            provider_config[field_info['name']] = safe_get_value(form_data, field_name, field_info.get('default', ''))