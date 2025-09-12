"""
Admin Management Service
Handles admin configuration operations and settings management
"""

import yaml
from typing import Dict, Any
from models.forms import safe_get_value
from admin.schema import PROVIDER_FIELD_SCHEMAS
from shared.handlers.errors import handle_service_errors


class AdminOperationsService:
    """Service for admin configuration operations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    # =========================================================================
    # CONFIG ACCESS METHODS - handlers should use these instead of direct access
    # =========================================================================
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings - handlers should call this instead of backup_config.get_global_settings()"""
        return self.backup_config.get_global_settings()
    
    def get_config_file_path(self) -> str:
        """Get config file path - handlers should call this instead of backup_config.config_file"""
        return self.backup_config.config_file
    
    def update_global_settings(self, settings: Dict[str, Any]) -> None:
        """Update global settings - handlers should call this instead of backup_config.update_global_settings()"""
        return self.backup_config.update_global_settings(settings)
    
    def reload_config(self) -> None:
        """Reload config - handlers should call this instead of backup_config.reload_config()"""
        self.backup_config.config = self.backup_config.load_config()
    
    def get_or_create_global_settings(self) -> Dict[str, Any]:
        """Get or create global settings dict - handlers should call this instead of backup_config.config.setdefault()"""
        return self.backup_config.config.setdefault('global_settings', {})
    
    # =========================================================================
    # BUSINESS LOGIC METHODS - moved from handlers  
    # =========================================================================
    
    def save_structured_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save structured configuration from form data - contains all business logic"""
        try:
            # Get current configuration and update global settings
            global_settings = self.get_or_create_global_settings()
            
            # Update basic settings using safe_get_value
            global_settings['scheduler_timezone'] = safe_get_value(form_data, 'scheduler_timezone', 'UTC')
            
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
            self.update_global_settings(global_settings)
            
            return {'success': True, 'message': 'Configuration saved successfully'}
            
        except Exception as e:
            return {'success': False, 'error': f'Configuration save failed: {str(e)}'}
    
    def preview_config_changes_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preview configuration changes without saving - contains all business logic"""
        # Start with current configuration to preserve existing notification settings
        current_config = self.backup_config.load_config()
        preview_config = {'global_settings': current_config.get('global_settings', {}).copy()}
        global_settings = preview_config['global_settings']
        
        # Basic settings
        global_settings['scheduler_timezone'] = safe_get_value(form_data, 'scheduler_timezone', 'UTC')
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
    
    def _build_notification_preview(self, global_settings: dict, form_data: Dict[str, Any]):
        """Build notification settings for preview (without modifying actual config)"""
        notification_config = global_settings.setdefault('notification', {})
        
        # Process each provider's configuration
        for provider_name, provider_schema in PROVIDER_FIELD_SCHEMAS.items():
            # Only process if provider fields are present in form
            if any(f"{provider_name}_{field['name']}" in form_data for field in provider_schema.get('fields', [])):
                provider_config = notification_config.setdefault(provider_name, {})
                
                # Process individual fields
                for field_info in provider_schema.get('fields', []):
                    self._process_notification_field(provider_config, provider_name, field_info, form_data)
                
                # Handle all sections (smtp_config, queue_settings, etc.)
                for section_name in ['smtp_config', 'queue_settings', 'retry_settings']:
                    if section_name in provider_config:
                        for field_info in provider_config[section_name]:
                            self._process_notification_field(provider_config, provider_name, field_info, form_data)
    
    @handle_service_errors("Add notification provider")
    def add_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new notification provider to configuration"""
        provider = safe_get_value(form_data, 'add_provider')
        if not provider or provider not in ['telegram', 'email']:
            return {'success': False, 'error': 'Invalid provider selection'}
        
        # Get current config and add empty provider section
        current_config = self.backup_config.load_config()
        global_settings = current_config.get('global_settings', {})
        notification_config = global_settings.setdefault('notification', {})
        
        # Add provider with default settings
        from admin.schema import PROVIDER_FIELD_SCHEMAS
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
        self.update_global_settings(global_settings)
        
        return {'success': True, 'provider': provider}

    @handle_service_errors("Remove notification provider")
    def remove_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a notification provider from configuration"""
        provider = safe_get_value(form_data, 'provider')
        if not provider or provider not in ['telegram', 'email']:
            return {'success': False, 'error': 'Invalid provider'}
        
        # Get current config and remove provider section
        current_config = self.backup_config.load_config()
        global_settings = current_config.get('global_settings', {})
        notification_config = global_settings.get('notification', {})
        
        if provider in notification_config:
            del notification_config[provider]
            
            # Save the updated configuration
            self.update_global_settings(global_settings)
            
            return {'success': True, 'provider': provider}
        else:
            return {'success': False, 'error': f'{provider} provider not found'}

    @handle_service_errors("Test telegram notification")
    def test_telegram_notification(self, test_message: str) -> Dict[str, Any]:
        """Test telegram notification via service"""
        from admin.services.notifications import NotificationTestService
        test_service = NotificationTestService(self.backup_config)
        return test_service.test_telegram_notification(test_message)

    @handle_service_errors("Test email notification")
    def test_email_notification(self, test_message: str) -> Dict[str, Any]:
        """Test email notification via service"""
        from admin.services.notifications import NotificationTestService
        test_service = NotificationTestService(self.backup_config)
        return test_service.test_email_notification(test_message)

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


# Export service instance for easy import
def create_admin_operations_service(backup_config=None):
    """Factory function to create AdminOperationsService instance"""
    if backup_config is None:
        from config import BackupConfig
        backup_config = BackupConfig()
    return AdminOperationsService(backup_config)