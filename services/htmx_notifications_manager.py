"""
HTMX Notifications Manager Service
Handles notification provider management for job forms
"""

import json
import html
import logging

logger = logging.getLogger(__name__)

class HTMXNotificationsManager:
    """Handles notification provider management for HTMX responses"""
    
    def __init__(self):
        self.configured_providers = []
    
    def render_notification_providers(self, available_providers, existing_notifications=None):
        """Render complete notification providers section"""
        html_parts = []
        
        # Initialize configured providers from existing data
        self.configured_providers = []
        if existing_notifications:
            for notification in existing_notifications:
                self.configured_providers.append(notification.get('provider', ''))
                html_parts.append(self._render_existing_provider(notification))
        
        # Build complete section
        provider_selection = self._render_provider_selection(available_providers)
        providers_html = ''.join(html_parts)
        
        return f'''
        <div id="notification_providers">
            {providers_html}
        </div>
        {provider_selection}
        '''
    
    def add_notification_provider(self, provider_name, available_providers):
        """Add a new notification provider"""
        if not provider_name:
            return self._render_error("Invalid provider selection")
        
        # Track this provider as configured (temporarily for this request)
        self.configured_providers.append(provider_name)
        
        # Render new provider configuration
        new_provider_html = self._render_new_provider(provider_name)
        
        # Update dropdown to exclude the provider we just added
        updated_selection = self._render_provider_selection(available_providers)
        
        return f'''
        <div id="notification_providers" hx-swap-oob="beforeend">
            {new_provider_html}
        </div>
        <div id="add_provider_section" hx-swap-oob="true">
            {updated_selection}
        </div>
        '''
    
    def remove_notification_provider(self, provider_id, available_providers):
        """Remove a notification provider"""
        # Extract provider name from ID (format: notification_{provider}_{timestamp})
        parts = provider_id.split('_')
        if len(parts) >= 2:
            provider_name = parts[1]
            if provider_name in self.configured_providers:
                self.configured_providers.remove(provider_name)
        
        # Return updated provider selection dropdown
        return self._render_provider_selection(available_providers)
    
    def toggle_success_message(self, provider_id, enabled):
        """Toggle success message field visibility"""
        logger.info(f"toggle_success_message called: provider_id={provider_id}, enabled={enabled}")
        if enabled:
            return '''
            <div class="success-message-group">
                <input type="text" class="success-message-input" name="notification_success_messages[]" 
                       placeholder="Job '{job_name}' completed successfully in {duration}">
                <div class="help-text">Custom success message (leave blank for default)</div>
            </div>
            '''
        else:
            return '<div class="success-message-group hidden"></div>'
    
    def toggle_failure_message(self, provider_id, enabled):
        """Toggle failure message field visibility"""
        if enabled:
            return '''
            <div class="failure-message-group">
                <input type="text" class="failure-message-input" name="notification_failure_messages[]" 
                       placeholder="Job '{job_name}' failed: {error_message}">
                <div class="help-text">Custom failure message (leave blank for default)</div>
            </div>
            '''
        else:
            return '<div class="failure-message-group hidden"></div>'
    
    def _render_new_provider(self, provider_name):
        """Render a new provider configuration"""
        timestamp = int(time.time() * 1000)  # JavaScript-style timestamp
        provider_id = f"notification_{provider_name}_{timestamp}"
        display_name = provider_name.capitalize()
        
        return f'''
        <div id="{provider_id}" class="notification-provider">
            <div class="path-group">
                <h3 class="provider-header">
                    <span class="provider-name">{display_name}</span>
                    <button type="button" class="remove-provider-btn button button-danger"
                            hx-post="/htmx/remove-notification-provider"
                            hx-target="#add_provider_section"
                            hx-include="closest .notification-provider"
                            hx-swap="outerHTML">Remove</button>
                </h3>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-success-checkbox" name="notify_on_success[]"
                               hx-post="/htmx/toggle-success-message"
                               hx-target="next .success-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Success
                    </label>
                    <div class="success-message-group hidden">
                        <input type="text" class="success-message-input" name="notification_success_messages[]" 
                               placeholder="Job '{{job_name}}' completed successfully in {{duration}}">
                        <div class="help-text">Custom success message (leave blank for default)</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-failure-checkbox" name="notify_on_failure[]"
                               hx-post="/htmx/toggle-failure-message"
                               hx-target="next .failure-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Failure
                    </label>
                    <div class="failure-message-group hidden">
                        <input type="text" class="failure-message-input" name="notification_failure_messages[]" 
                               placeholder="Job '{{job_name}}' failed: {{error_message}}">
                        <div class="help-text">Custom failure message (leave blank for default)</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-maintenance-failure-checkbox" name="notify_on_maintenance_failure[]"> 
                        Notify on Maintenance Failure
                    </label>
                    <div class="help-text">Get notified when repository maintenance operations (forget/prune/check) fail</div>
                </div>
                
                <input type="hidden" class="provider-name-hidden" name="notification_providers[]" value="{provider_name}">
                <input type="hidden" class="provider-id-hidden" name="provider_id" value="{provider_id}">
            </div>
        </div>
        '''
    
    def _render_existing_provider(self, config):
        """Render an existing provider configuration"""
        provider_name = config.get('provider', '')
        display_name = provider_name.capitalize()
        provider_id = f"notification_{provider_name}_existing"
        
        # Build success message section
        success_checked = 'checked' if config.get('notify_on_success', False) else ''
        success_message_class = '' if config.get('notify_on_success', False) else 'hidden'
        success_message = html.escape(config.get('success_message', ''))
        
        # Build failure message section  
        failure_checked = 'checked' if config.get('notify_on_failure', False) else ''
        failure_message_class = '' if config.get('notify_on_failure', False) else 'hidden'
        failure_message = html.escape(config.get('failure_message', ''))
        
        # Maintenance failure checkbox
        maintenance_checked = 'checked' if config.get('notify_on_maintenance_failure', False) else ''
        
        return f'''
        <div id="{provider_id}" class="notification-provider">
            <div class="path-group">
                <h3 class="provider-header">
                    <span class="provider-name">{display_name}</span>
                    <button type="button" class="remove-provider-btn button button-danger"
                            hx-post="/htmx/remove-notification-provider"
                            hx-target="#add_provider_section"
                            hx-include="closest .notification-provider"
                            hx-swap="outerHTML">Remove</button>
                </h3>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-success-checkbox" name="notify_on_success[]" {success_checked}
                               hx-post="/htmx/toggle-success-message"
                               hx-target="next .success-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Success
                    </label>
                    <div id="success_message_{provider_id}" class="success-message-group {success_message_class}">
                        <input type="text" class="success-message-input" name="notification_success_messages[]" 
                               value="{success_message}" placeholder="Job '{{job_name}}' completed successfully in {{duration}}">
                        <div class="help-text">Custom success message (leave blank for default)</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-failure-checkbox" name="notify_on_failure[]" {failure_checked}
                               hx-post="/htmx/toggle-failure-message"
                               hx-target="next .failure-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Failure
                    </label>
                    <div id="failure_message_{provider_id}" class="failure-message-group {failure_message_class}">
                        <input type="text" class="failure-message-input" name="notification_failure_messages[]" 
                               value="{failure_message}" placeholder="Job '{{job_name}}' failed: {{error_message}}">
                        <div class="help-text">Custom failure message (leave blank for default)</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" class="notify-maintenance-failure-checkbox" name="notify_maintenance_failure[]" {maintenance_checked}> 
                        Notify on Maintenance Failure
                    </label>
                    <div class="help-text">Get notified when repository maintenance operations (forget/prune/check) fail</div>
                </div>
                
                <input type="hidden" class="provider-name-hidden" name="notification_providers[]" value="{provider_name}">
                <input type="hidden" class="provider-id-hidden" name="provider_id" value="{provider_id}">
            </div>
        </div>
        '''
    
    def _render_provider_selection(self, available_providers):
        """Render the provider selection dropdown"""
        # Filter out already configured providers
        available_options = [p for p in available_providers if p not in self.configured_providers]
        
        options_html = ''.join([
            f'<option value="{provider}">{provider.capitalize()}</option>'
            for provider in available_options
        ])
        
        # Hide dropdown if no more providers available
        display_style = 'style="display: none;"' if not available_options else ''
        
        return f'''
        <div id="add_provider_section" class="form-group" {display_style}>
            <label for="add_notification_provider">Add Notification Provider:</label>
            <select id="add_notification_provider" name="provider"
                    hx-post="/htmx/add-notification-provider"
                    hx-trigger="change[target.value != '']">
                <option value="">Select a provider...</option>
                {options_html}
            </select>
            <div class="help-text">Configure notifications for this job using globally configured providers</div>
        </div>
        '''
    
    def _render_error(self, message):
        """Render an error message"""
        return f'<div class="error-message">{html.escape(message)}</div>'

# Import time for timestamps
import time