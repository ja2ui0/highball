"""
HTMX Form Handler
Thin coordinator for HTMX form operations - delegates to specialized services
"""

import logging
from services.htmx_field_renderer import HTMXFieldRenderer
from services.htmx_validation_coordinator import HTMXValidationCoordinator
from services.htmx_restic_coordinator import HTMXResticCoordinator
from services.htmx_source_path_manager import HTMXSourcePathManager
from services.htmx_log_manager import HTMXLogManager
from services.htmx_config_manager import HTMXConfigManager
from services.htmx_maintenance_manager import HTMXMaintenanceManager
from services.htmx_rsyncd_manager import HTMXRsyncdManager
from services.htmx_notifications_manager import HTMXNotificationsManager

logger = logging.getLogger(__name__)

class HTMXFormHandler:
    """Thin coordinator for HTMX form operations"""
    
    def __init__(self):
        self.field_renderer = HTMXFieldRenderer()
        self.validation_coordinator = HTMXValidationCoordinator()
        self.restic_coordinator = HTMXResticCoordinator()
        self.source_path_manager = HTMXSourcePathManager()
        self.log_manager = HTMXLogManager()
        self.config_manager = HTMXConfigManager()
        self.maintenance_manager = HTMXMaintenanceManager()
        self.rsyncd_manager = HTMXRsyncdManager()
        self.notifications_manager = HTMXNotificationsManager()
    
    def handle_source_type_change(self, source_type, existing_data=None):
        """Delegate source field rendering to field renderer"""
        logger.info(f"HTMX source type change: {source_type}")
        return self.field_renderer.render_source_fields(source_type, existing_data)
    
    def handle_dest_type_change(self, dest_type, existing_data=None):
        """Delegate destination field rendering to field renderer"""
        logger.info(f"HTMX dest type change: {dest_type}")
        return self.field_renderer.render_dest_fields(dest_type, existing_data)
    
    def handle_ssh_validation(self, form_data):
        """Delegate SSH validation to validation coordinator"""
        return self.validation_coordinator.validate_ssh_connection(form_data)
    
    def handle_source_path_validation(self, form_data):
        """Delegate source path validation to validation coordinator"""
        return self.validation_coordinator.validate_source_paths(form_data)
    
    def handle_restic_repo_fields(self, form_data):
        """Delegate Restic repository field rendering to Restic coordinator"""
        repo_type = form_data.get('restic_repo_type', [''])[0]
        return self.restic_coordinator.handle_repo_type_change(repo_type, form_data)
    
    def handle_restic_uri_preview(self, form_data):
        """Delegate Restic URI preview generation to Restic coordinator"""
        return self.restic_coordinator.handle_uri_preview_update(form_data)
    
    def handle_restic_validation(self, form_data):
        """Delegate Restic validation to Restic coordinator"""
        return self.restic_coordinator.handle_restic_validation(form_data)
    
    def handle_restic_initialization(self, form_data):
        """Delegate Restic repository initialization to restic coordinator"""
        return self.restic_coordinator.handle_repository_initialization(form_data)
    
    def handle_add_source_path(self, form_data):
        """Delegate source path addition to source path manager"""
        return self.source_path_manager.add_new_path(form_data)
    
    def handle_remove_source_path(self, form_data):
        """Delegate source path removal to source path manager"""
        path_index = int(form_data.get('path_index', ['0'])[0])
        return self.source_path_manager.remove_path(form_data, path_index)
    
    def handle_validate_single_source_path(self, form_data):
        """Delegate single path validation to validation coordinator"""
        return self.validation_coordinator.validate_single_source_path(form_data)
    
    def handle_log_refresh(self, job_name):
        """Delegate log refresh to log manager"""
        logger.info(f"HTMX log refresh for job: {job_name}")
        return self.log_manager.refresh_log_content(job_name)
    
    def handle_log_clear(self):
        """Delegate log clear to log manager"""
        logger.info("HTMX log clear")
        return self.log_manager.clear_log_display()
    
    def handle_cron_field_toggle(self, form_data):
        """Handle cron field visibility toggle"""
        schedule_value = form_data.get('schedule', [''])[0]
        existing_cron = form_data.get('cron_pattern', [''])[0]
        logger.info(f"HTMX cron field toggle: schedule={schedule_value}")
        return self.field_renderer.render_cron_field(schedule_value, existing_cron)
    
    def handle_notification_settings_toggle(self, form_data):
        """Handle notification settings visibility toggle"""
        provider = form_data.get('provider', [''])[0]
        enabled = form_data.get('enabled', [''])[0] == 'true'
        logger.info(f"HTMX notification settings toggle: provider={provider}, enabled={enabled}")
        
        # Convert form data to dict for existing values
        existing_data = {key: value[0] if isinstance(value, list) else value 
                        for key, value in form_data.items()}
        
        return self.config_manager.render_notification_settings(provider, enabled, existing_data)
    
    def handle_queue_settings_toggle(self, form_data):
        """Handle queue settings visibility toggle"""
        provider = form_data.get('provider', [''])[0]
        enabled = form_data.get('enabled', [''])[0] == 'true'
        logger.info(f"HTMX queue settings toggle: provider={provider}, enabled={enabled}")
        
        # Convert form data to dict for existing values
        existing_data = {key: value[0] if isinstance(value, list) else value 
                        for key, value in form_data.items()}
        
        return self.config_manager.render_queue_settings(provider, enabled, existing_data)
    
    def handle_notification_test(self, provider, form_data):
        """Handle notification testing"""
        logger.info(f"HTMX notification test: provider={provider}")
        
        # For now, we'll delegate to the existing notification test handler
        # and format the response for HTMX
        try:
            if provider == 'telegram':
                return self._test_telegram_notification(form_data)
            elif provider == 'email':
                return self._test_email_notification(form_data)
            else:
                return self.config_manager.render_test_result(provider, "Unknown provider", False)
        except Exception as e:
            logger.error(f"Notification test error: {e}")
            return self.config_manager.render_test_result(provider, f"Test failed: {str(e)}", False)
    
    def _test_telegram_notification(self, form_data):
        """Test Telegram notification via existing handler"""
        # This will integrate with the existing notification test handler
        # For now, return a placeholder that matches the expected format
        token = form_data.get('telegram_token', [''])[0]
        chat_id = form_data.get('telegram_chat_id', [''])[0]
        
        if not token or not chat_id:
            return self.config_manager.render_test_result('telegram', 
                "Error: Bot token and chat ID are required", False)
        
        # TODO: Integrate with actual notification testing
        return self.config_manager.render_test_result('telegram', 
            "Test notification functionality ready for integration", True)
    
    def _test_email_notification(self, form_data):
        """Test Email notification via existing handler"""
        # This will integrate with the existing notification test handler
        smtp_server = form_data.get('email_smtp_server', [''])[0]
        from_email = form_data.get('email_from', [''])[0]
        to_email = form_data.get('email_to', [''])[0]
        
        if not smtp_server or not from_email or not to_email:
            return self.config_manager.render_test_result('email',
                "Error: SMTP server, from email, and to email are required", False)
        
        # TODO: Integrate with actual notification testing
        return self.config_manager.render_test_result('email',
            "Test notification functionality ready for integration", True)
    
    def handle_maintenance_toggle(self, form_data):
        """Handle maintenance mode toggle"""
        mode = form_data.get('mode', [''])[0]
        logger.info(f"HTMX maintenance toggle: mode={mode}")
        
        # Convert form data to dict for existing values
        existing_data = {key: value[0] if isinstance(value, list) else value 
                        for key, value in form_data.items()}
        
        return self.maintenance_manager.render_maintenance_display(mode, existing_data)
    
    def handle_maintenance_section_visibility(self, form_data):
        """Handle maintenance section visibility based on destination type"""
        dest_type = form_data.get('dest_type', [''])[0]
        logger.info(f"HTMX maintenance section visibility: dest_type={dest_type}")
        
        # Convert form data to dict for existing values
        existing_data = {key: value[0] if isinstance(value, list) else value 
                        for key, value in form_data.items()}
        
        return self.maintenance_manager.render_maintenance_section_visibility(dest_type, existing_data)
    
    def handle_rsyncd_discovery(self, form_data):
        """Handle rsyncd share discovery"""
        hostname = form_data.get('dest_rsyncd_hostname', [''])[0]
        logger.info(f"HTMX rsyncd discovery: hostname={hostname}")
        
        if not hostname:
            return self.rsyncd_manager.render_discovery_result(False, "Please enter hostname first")
        
        # For now, return a placeholder that shows the integration point
        # This would integrate with the actual rsyncd validation handler
        return self.rsyncd_manager.render_loading_state()
    
    def handle_rsyncd_validation(self, form_data):
        """Handle rsyncd validation"""
        hostname = form_data.get('dest_rsyncd_hostname', [''])[0]
        share = form_data.get('dest_rsyncd_share', [''])[0]
        logger.info(f"HTMX rsyncd validation: hostname={hostname}, share={share}")
        
        if not hostname or not share:
            return self.rsyncd_manager.render_validation_result(False, "Hostname and share are required")
        
        # Placeholder for actual validation
        return self.rsyncd_manager.render_validation_result(True, 
            f"Rsyncd validation ready for integration: {hostname}::{share}")
    
    def handle_add_notification_provider(self, form_data, available_providers):
        """Handle adding a notification provider"""
        provider = form_data.get('provider', [''])[0]
        print(f"[DEBUG] add_notification_provider: form_data={form_data}, provider={provider}")
        logger.info(f"HTMX add notification provider: provider={provider}")
        
        return self.notifications_manager.add_notification_provider(provider, available_providers)
    
    def handle_remove_notification_provider(self, form_data, available_providers):
        """Handle removing a notification provider"""
        provider_id = form_data.get('provider_id', [''])[0]
        logger.info(f"HTMX remove notification provider: provider_id={provider_id}")
        
        return self.notifications_manager.remove_notification_provider(provider_id, available_providers)
    
    def handle_toggle_success_message(self, form_data):
        """Handle toggle success message visibility"""
        # Checkbox is checked if notify_on_success[] is present in form data
        enabled = 'notify_on_success[]' in form_data
        logger.info(f"HTMX toggle success message: enabled={enabled}")
        
        return self.notifications_manager.toggle_success_message("", enabled)
    
    def handle_toggle_failure_message(self, form_data):
        """Handle toggle failure message visibility"""
        # Checkbox is checked if notify_on_failure[] is present in form data
        enabled = 'notify_on_failure[]' in form_data
        logger.info(f"HTMX toggle failure message: enabled={enabled}")
        
        return self.notifications_manager.toggle_failure_message("", enabled)