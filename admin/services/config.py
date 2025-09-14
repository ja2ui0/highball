#!/usr/bin/env python3
"""
Admin domain configuration service
Handles CRUD operations for global settings (/config/local/local.yaml)
"""
import os
import yaml
from typing import Dict, Any
from shared.services.config import ConfigIOService, ConfigReader
from admin.data.constants import PROVIDER_FIELD_SCHEMAS
from admin.data.models import (
    ConfigSaveResult, ConfigPreviewResult, ProviderOperationResult,
    GlobalSettings, TelegramConfig, EmailConfig
)
from models.forms import safe_get_value


class AdminConfigService:
    """Domain service for admin configuration management - global settings only"""
    
    def __init__(self):
        self.config_file = "/config/local/local.yaml"
        self.config_reader = ConfigReader()
    
    # =============================================================================
    # GLOBAL SETTINGS CRUD METHODS - moved from root config.py
    # =============================================================================
    
    def update_global_settings(self, settings: Dict[str, Any]) -> bool:
        """Update global settings and save only global settings to local.yaml"""
        # Load existing local.yaml to preserve any manual edits
        local_yaml = ConfigIOService.load_yaml(self.config_file) or {}
        
        # Update only the global_settings section
        local_yaml['global_settings'] = settings
        
        # Save only global settings to local.yaml
        return ConfigIOService.save_yaml_atomic(self.config_file, local_yaml)

    # =============================================================================
    # BUSINESS LOGIC METHODS - moved from manage.py
    # =============================================================================
    
    def save_structured_config_from_form(self, form_data: Dict[str, Any]) -> ConfigSaveResult:
        """Save structured configuration from form data - contains all business logic"""
        try:
            # Get current configuration and update global settings
            global_settings = self.config_reader.get_global_settings()
            
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
            
            # Notification settings with validation
            self._update_notification_settings_with_validation(global_settings, form_data)
            
            # Save only global settings to local.yaml (not domain configs)
            success = self.update_global_settings(global_settings)
            
            if success:
                return ConfigSaveResult(success=True)
            else:
                return ConfigSaveResult(success=False, error='Failed to save configuration to disk')
            
        except Exception as e:
            return ConfigSaveResult(success=False, error=f'Configuration save failed: {str(e)}')
    
    def preview_config_changes_from_form(self, form_data: Dict[str, Any]) -> ConfigPreviewResult:
        """Preview configuration changes without saving - contains all business logic"""
        # Start with current configuration to preserve existing notification settings
        current_config = {'global_settings': self.config_reader.get_global_settings().copy()}
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
        self._update_notification_settings_with_validation(global_settings, form_data)
        
        # Convert to YAML for display
        yaml_content = yaml.dump(preview_config, default_flow_style=False, sort_keys=False)
        
        return ConfigPreviewResult(
            success=True,
            preview_content=yaml_content
        )
    
    def add_notification_provider_from_form(self, form_data: Dict[str, Any]) -> ProviderOperationResult:
        """Add a new notification provider to configuration"""
        try:
            provider = safe_get_value(form_data, 'add_provider')
            if not provider or provider not in ['telegram', 'email']:
                return ProviderOperationResult(success=False, error='Invalid provider selection')
            
            # Get current config and add empty provider section
            global_settings = self.config_reader.get_global_settings()
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
                return ProviderOperationResult(success=True, provider=provider)
            else:
                return ProviderOperationResult(success=False, error='Failed to save provider configuration')
            
        except Exception as e:
            return ProviderOperationResult(success=False, error=f'Add provider failed: {str(e)}')

    def remove_notification_provider_from_form(self, form_data: Dict[str, Any]) -> ProviderOperationResult:
        """Remove a notification provider from configuration"""
        try:
            provider = safe_get_value(form_data, 'provider')
            if not provider or provider not in ['telegram', 'email']:
                return ProviderOperationResult(success=False, error='Invalid provider')
            
            # Get current config and remove provider section
            global_settings = self.config_reader.get_global_settings()
            notification_config = global_settings.get('notification', {})
            
            if provider in notification_config:
                del notification_config[provider]
                
                # Save the updated configuration
                success = self.update_global_settings(global_settings)
                
                if success:
                    return ProviderOperationResult(success=True, provider=provider)
                else:
                    return ProviderOperationResult(success=False, error='Failed to save configuration changes')
            else:
                return ProviderOperationResult(success=False, error=f'{provider} provider not found')
                
        except Exception as e:
            return ProviderOperationResult(success=False, error=f'Remove provider failed: {str(e)}')
    
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

    def _update_notification_settings_with_validation(self, global_settings: dict, form_data: Dict[str, Any]):
        """Update notification settings with Pydantic validation"""
        notification_config = global_settings.setdefault('notification', {})

        # Process each provider with validation
        for provider_name in ['telegram', 'email']:
            provider_fields = {key.replace(f'{provider_name}_', ''): value
                             for key, value in form_data.items()
                             if key.startswith(f'{provider_name}_')}

            if provider_fields:
                try:
                    # Validate using Pydantic models
                    if provider_name == 'telegram':
                        validated_config = TelegramConfig.model_validate(provider_fields)
                    elif provider_name == 'email':
                        validated_config = EmailConfig.model_validate(provider_fields)
                    else:
                        continue

                    # Store validated config as dict
                    notification_config[provider_name] = validated_config.model_dump()

                except Exception as validation_error:
                    # If validation fails, raise with clear error
                    raise ValueError(f"{provider_name.title()} configuration invalid: {str(validation_error)}")