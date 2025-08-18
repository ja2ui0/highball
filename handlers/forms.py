"""
Forms Handler - Pure HTTP coordination for HTMX operations
Delegates all business logic to appropriate services
"""

import logging
from models.validation import ValidationService
from models.forms import JobFormParser
from services.template import TemplateService

logger = logging.getLogger(__name__)

class FormsHandler:
    """Pure HTTP coordination for HTMX form operations"""
    
    def __init__(self, backup_config, template_service):
        # HTTP coordination only - no business logic state
        self.validation_service = ValidationService(backup_config)
        self.form_parser = JobFormParser()
        self.template_service = template_service
    
    def handle_htmx_request(self, request, action):
        """Single HTMX entry point with action dispatch"""
        # HTTP concern: parse form data once
        form_data = self._parse_form_data(request)
        
        # Action dispatch table
        actions = {
            # Validation actions
            'validate-ssh-source': self._validate_ssh_source,
            'validate-source-path': self._validate_source_path,
            'validate-restic': self._validate_restic,
            'check-restore-overwrites': self._check_restore_overwrites,
            
            # Field rendering actions  
            'source-fields': self._render_source_fields,
            'dest-fields': self._render_dest_fields,
            'restic-fields': self._render_restic_fields,
            
            # Source path management
            'add-source-path': self._add_source_path,
            'remove-source-path': self._remove_source_path,
            
            # Notification management
            'notification-providers': self._render_notification_providers,
            'add-notification-provider': self._add_notification_provider,
            'remove-notification-provider': self._remove_notification_provider,
            'toggle-success-message': self._toggle_success_message,
            'toggle-failure-message': self._toggle_failure_message,
            
            # Repository management
            'init-restic-repository': self._init_restic_repository,
            
            # Maintenance fields
            'maintenance-fields': self._render_maintenance_fields,
            'rsyncd-fields': self._render_rsyncd_fields,
        }
        
        handler_func = actions.get(action)
        if not handler_func:
            return self._send_error(f"Unknown action: {action}")
        
        try:
            html_response = handler_func(form_data)
            return self._send_htmx_response(html_response)
        except Exception as e:
            logger.error(f"HTMX action {action} failed: {e}")
            return self._send_error(f"Action failed: {str(e)}")
    
    # =============================================================================
    # VALIDATION ACTIONS - Direct validator calls, no coordinators
    # =============================================================================
    
    def _validate_ssh_source(self, form_data):
        """HTTP coordination: extract params, delegate validation, render response"""
        # HTTP concern: extract parameters from request
        hostname = self._get_form_value(form_data, 'hostname')
        username = self._get_form_value(form_data, 'username')
        
        # Business logic concern: delegate to validation service
        result = self.validation_service.validate_ssh_connection(hostname, username)
        
        # View concern: delegate to template service
        return self.template_service.render_validation_status('ssh_source', result)
    
    def _check_restore_overwrites(self, form_data):
        """HTTP coordination: check restore overwrites via service"""
        # HTTP concern: extract parameters
        job_name = self._get_form_value(form_data, 'job_name')
        restore_target = self._get_form_value(form_data, 'restore_target', 'highball')
        select_all = self._get_form_value(form_data, 'select_all') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: delegate to restore service
        from services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.validation_service.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths, select_all
        )
        
        # View concern: render overwrite warning HTML
        return self._render_overwrite_warning(has_overwrites, restore_target)
    
    def _render_overwrite_warning(self, has_overwrites: bool, restore_target: str) -> str:
        """Template concern: render overwrite warning HTML"""
        if has_overwrites:
            target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
            return f"""
            <div id="overwriteWarning" class="warning-message">
                <span class="warning-icon">⚠️</span>
                This restore will overwrite existing files in {target_text}.
            </div>
            <div id="confirmationSection" class="confirmation-section">
                <label>
                    <input type="checkbox" name="confirm_overwrite" required>
                    I understand this will overwrite existing files
                </label>
            </div>
            """
        else:
            return '<div id="overwriteWarning" class="hidden"></div>'
    
    def _validate_source_path(self, form_data):
        """HTTP coordination: extract params, delegate path validation, render response"""
        # HTTP concern: extract parameters from request
        path = self._get_form_value(form_data, 'path')
        hostname = self._get_form_value(form_data, 'hostname')
        username = self._get_form_value(form_data, 'username')
        
        # Business logic concern: delegate to validation service
        result = self.validation_service.validate_source_path_with_ssh(hostname, username, path)
        
        # View concern: delegate to template service
        return self.template_service.render_validation_status('source_path', result)
    
    def _validate_restic(self, form_data):
        """HTTP coordination: extract params, delegate restic validation, render response"""
        # HTTP concern: extract parameters from request
        repo_type = self._get_form_value(form_data, 'repo_type')
        repo_uri = self._get_form_value(form_data, 'repo_uri') 
        password = self._get_form_value(form_data, 'password')
        
        # Business logic concern: delegate to validation service
        result = self.validation_service.validate_restic_config(repo_type, repo_uri, password)
        
        # View concern: delegate to template service
        return self.template_service.render_validation_status('restic', result)
    
    # =============================================================================
    # FIELD RENDERING ACTIONS - Inline HTML, no renderer services
    # =============================================================================
    
    def _render_source_fields(self, form_data):
        """Render source-specific fields based on source type"""
        source_type = form_data.get('source_type', [''])[0]
        
        if source_type == 'ssh':
            return '''
            <div class="form-group">
                <label for="hostname">Hostname:</label>
                <input type="text" id="hostname" name="hostname" required>
            </div>
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <button type="button" 
                        hx-post="/htmx/validate-ssh-source"
                        hx-include="closest form"
                        hx-target="#ssh_validation_result"
                        hx-swap="outerHTML">Validate SSH Connection</button>
                <div id="ssh_validation_result"></div>
            </div>
            '''
        elif source_type == 'local':
            return '<div class="info-message">Local filesystem source - no additional configuration needed</div>'
        else:
            return '<div class="info-message">Select a source type to configure</div>'
    
    def _render_dest_fields(self, form_data):
        """Render destination-specific fields based on destination type"""
        dest_type = form_data.get('dest_type', [''])[0]
        
        if dest_type == 'ssh':
            return '''
            <div class="form-group">
                <label for="dest_hostname">Hostname:</label>
                <input type="text" id="dest_hostname" name="dest_hostname" required>
            </div>
            <div class="form-group">
                <label for="dest_username">Username:</label>
                <input type="text" id="dest_username" name="dest_username" required>
            </div>
            <div class="form-group">
                <label for="dest_path">Destination Path:</label>
                <input type="text" id="dest_path" name="dest_path" required>
            </div>
            '''
        elif dest_type == 'local':
            return '''
            <div class="form-group">
                <label for="dest_path">Destination Path:</label>
                <input type="text" id="dest_path" name="dest_path" required>
            </div>
            '''
        elif dest_type == 'rsyncd':
            return '''
            <div class="form-group">
                <label for="rsyncd_hostname">Hostname:</label>
                <input type="text" id="rsyncd_hostname" name="rsyncd_hostname" required>
            </div>
            <div class="form-group">
                <label for="rsyncd_share">Share:</label>
                <input type="text" id="rsyncd_share" name="rsyncd_share" required>
            </div>
            '''
        elif dest_type == 'restic':
            return self._render_restic_fields(form_data)
        else:
            return '<div class="info-message">Select a destination type to configure</div>'
    
    def _render_restic_fields(self, form_data):
        """Render Restic repository configuration fields"""
        return '''
        <div class="form-group">
            <label for="repo_type">Repository Type:</label>
            <select id="repo_type" name="repo_type" required 
                    hx-post="/htmx/restic-fields"
                    hx-include="closest form"
                    hx-target="#restic_repo_fields"
                    hx-swap="outerHTML">
                <option value="">Select repository type...</option>
                <option value="local">Local</option>
                <option value="rest">REST Server</option>
                <option value="s3">Amazon S3</option>
                <option value="rclone">rclone</option>
                <option value="sftp">SFTP</option>
            </select>
        </div>
        <div id="restic_repo_fields">
            <div class="info-message">Select a repository type to configure</div>
        </div>
        <div class="form-group">
            <label for="restic_password">Repository Password:</label>
            <input type="password" id="restic_password" name="restic_password">
        </div>
        <div class="form-group">
            <button type="button" 
                    hx-post="/htmx/validate-restic"
                    hx-include="closest form"
                    hx-target="#restic_validation_result"
                    hx-swap="outerHTML">Validate Repository</button>
            <div id="restic_validation_result"></div>
        </div>
        '''
    
    # =============================================================================
    # SOURCE PATH MANAGEMENT - Direct array manipulation
    # =============================================================================
    
    def _add_source_path(self, form_data):
        """Add a new source path entry"""
        # Get current path count
        current_paths = form_data.get('source_paths[]', [])
        path_index = len(current_paths)
        
        return f'''
        <div id="source_path_{path_index}" class="source-path-entry">
            <div class="path-group">
                <h3>Source Path {path_index + 1}
                    <button type="button" class="remove-path-btn button button-danger"
                            hx-post="/htmx/remove-source-path"
                            hx-target="#source_path_{path_index}"
                            hx-swap="outerHTML">Remove</button>
                </h3>
                <div class="form-group">
                    <label>Path:</label>
                    <input type="text" name="source_paths[]" required>
                    <button type="button" 
                            hx-post="/htmx/validate-source-path"
                            hx-include="closest .source-path-entry"
                            hx-target="next .path-validation"
                            hx-swap="outerHTML">Validate</button>
                    <div class="path-validation"></div>
                </div>
                <div class="form-group">
                    <label>Include patterns (one per line):</label>
                    <textarea name="source_includes[]" placeholder="*.txt&#10;documents/"></textarea>
                </div>
                <div class="form-group">
                    <label>Exclude patterns (one per line):</label>
                    <textarea name="source_excludes[]" placeholder="*.tmp&#10;.git/"></textarea>
                </div>
            </div>
        </div>
        '''
    
    def _remove_source_path(self, form_data):
        """Remove a source path entry"""
        return ""  # Empty response removes the element
    
    # =============================================================================
    # NOTIFICATION MANAGEMENT - Simplified provider handling
    # =============================================================================
    
    def _render_notification_providers(self, form_data):
        """Render notification providers section"""
        available_providers = ['telegram', 'email']  # From global config
        existing_notifications = []  # Parse from form if editing
        
        # Build provider configurations
        provider_html = ""
        for i, provider in enumerate(existing_notifications):
            provider_html += self._render_notification_provider(provider, i)
        
        # Build provider selection dropdown
        selection_html = self._render_provider_selection(available_providers)
        
        return f'''
        <div id="notification_providers">
            {provider_html}
        </div>
        {selection_html}
        '''
    
    def _add_notification_provider(self, form_data):
        """Add a new notification provider"""
        provider_name = form_data.get('provider', [''])[0]
        if not provider_name:
            return self._render_error("Invalid provider selection")
        
        # Generate unique ID
        timestamp = int(time.time() * 1000)
        provider_id = f"notification_{provider_name}_{timestamp}"
        
        new_provider_html = self._render_notification_provider({
            'provider': provider_name,
            'notify_on_success': False,
            'notify_on_failure': False,
            'success_message': '',
            'failure_message': ''
        }, timestamp, provider_id)
        
        # Update dropdown 
        available_providers = ['telegram', 'email']
        self.configured_providers.append(provider_name)
        updated_selection = self._render_provider_selection(available_providers)
        
        return f'''
        <div id="notification_providers" hx-swap-oob="beforeend">
            {new_provider_html}
        </div>
        <div id="add_provider_section" hx-swap-oob="true">
            {updated_selection}
        </div>
        '''
    
    def _remove_notification_provider(self, form_data):
        """Remove a notification provider"""
        available_providers = ['telegram', 'email']
        return self._render_provider_selection(available_providers)
    
    def _toggle_success_message(self, form_data):
        """Toggle success message field visibility"""
        # Check if checkbox is checked
        enabled = 'notify_on_success[]' in form_data
        
        if enabled:
            return '''
            <div class="success-message-group">
                <input type="text" name="notification_success_messages[]" 
                       placeholder="Job '{job_name}' completed successfully in {duration}">
                <div class="help-text">Custom success message (leave blank for default)</div>
            </div>
            '''
        else:
            return '<div class="success-message-group hidden"></div>'
    
    def _toggle_failure_message(self, form_data):
        """Toggle failure message field visibility"""
        enabled = 'notify_on_failure[]' in form_data
        
        if enabled:
            return '''
            <div class="failure-message-group">
                <input type="text" name="notification_failure_messages[]" 
                       placeholder="Job '{job_name}' failed: {error_message}">
                <div class="help-text">Custom failure message (leave blank for default)</div>
            </div>
            '''
        else:
            return '<div class="failure-message-group hidden"></div>'
    
    # =============================================================================
    # REPOSITORY MANAGEMENT - Direct operations
    # =============================================================================
    
    def _init_restic_repository(self, form_data):
        """Initialize Restic repository"""
        # Parse Restic config from unified parser
        restic_result = destination_parser.parse_restic_destination(form_data)
        
        if not restic_result['valid']:
            return self._render_validation_result("error", restic_result['error'])
        
        # Direct repository initialization
        try:
            from services.restic_repository_service import ResticRepositoryService
            repo_service = ResticRepositoryService()
            result = repo_service.initialize_repository(restic_result['config'])
            
            if result['success']:
                return self._render_validation_result("success", "Repository initialized successfully")
            else:
                return self._render_validation_result("error", f"Initialization failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            return self._render_validation_result("error", f"Initialization error: {str(e)}")
    
    # =============================================================================
    # MAINTENANCE AND RSYNCD FIELDS - Simple rendering
    # =============================================================================
    
    def _render_maintenance_fields(self, form_data):
        """Render maintenance configuration fields"""
        return '''
        <div class="form-group">
            <label>
                <input type="checkbox" name="auto_maintenance" checked> 
                Automatic Repository Maintenance
            </label>
            <div class="help-text">Automatically run forget/prune/check operations</div>
        </div>
        '''
    
    def _render_rsyncd_fields(self, form_data):
        """Render rsyncd-specific fields based on current state"""
        return '''
        <div class="form-group">
            <label for="rsyncd_hostname">Hostname:</label>
            <input type="text" id="rsyncd_hostname" name="rsyncd_hostname" required>
        </div>
        <div class="form-group">
            <label for="rsyncd_share">Share:</label>
            <input type="text" id="rsyncd_share" name="rsyncd_share" required>
        </div>
        '''
    
    # =============================================================================
    # UTILITY METHODS - Inline rendering helpers
    # =============================================================================
    
    def _render_validation_result(self, status, message):
        """Render validation result with consistent styling"""
        status_class = {
            'success': 'success',
            'error': 'error', 
            'warning': 'warning'
        }.get(status, 'info')
        
        status_label = {
            'success': '[OK]',
            'error': '[ERROR]',
            'warning': '[WARN]'
        }.get(status, '[INFO]')
        
        return f'''
        <div class="validation-result {status_class}">
            <span class="status">{status_label}</span> {html.escape(message)}
        </div>
        '''
    
    def _render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration"""
        provider_name = config.get('provider', '')
        display_name = provider_name.capitalize()
        
        if not provider_id:
            provider_id = f"notification_{provider_name}_{index}"
        
        success_checked = 'checked' if config.get('notify_on_success', False) else ''
        success_class = '' if config.get('notify_on_success', False) else 'hidden'
        success_message = html.escape(config.get('success_message', ''))
        
        failure_checked = 'checked' if config.get('notify_on_failure', False) else ''
        failure_class = '' if config.get('notify_on_failure', False) else 'hidden'
        failure_message = html.escape(config.get('failure_message', ''))
        
        return f'''
        <div id="{provider_id}" class="notification-provider">
            <div class="path-group">
                <h3 class="provider-header">
                    <span class="provider-name">{display_name}</span>
                    <button type="button" class="remove-provider-btn button button-danger"
                            hx-post="/htmx/remove-notification-provider"
                            hx-target="#add_provider_section"
                            hx-swap="outerHTML">Remove</button>
                </h3>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="notify_on_success[]" {success_checked}
                               hx-post="/htmx/toggle-success-message"
                               hx-target="next .success-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Success
                    </label>
                    <div class="success-message-group {success_class}">
                        <input type="text" name="notification_success_messages[]" 
                               value="{success_message}" placeholder="Job '{{job_name}}' completed successfully in {{duration}}">
                        <div class="help-text">Custom success message (leave blank for default)</div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="notify_on_failure[]" {failure_checked}
                               hx-post="/htmx/toggle-failure-message"
                               hx-target="next .failure-message-group"
                               hx-trigger="change"
                               hx-swap="outerHTML"> 
                        Notify on Failure
                    </label>
                    <div class="failure-message-group {failure_class}">
                        <input type="text" name="notification_failure_messages[]" 
                               value="{failure_message}" placeholder="Job '{{job_name}}' failed: {{error_message}}">
                        <div class="help-text">Custom failure message (leave blank for default)</div>
                    </div>
                </div>
                
                <input type="hidden" name="notification_providers[]" value="{provider_name}">
            </div>
        </div>
        '''
    
    def _render_provider_selection(self, available_providers):
        """Render provider selection dropdown"""
        # Filter out configured providers
        available_options = [p for p in available_providers if p not in self.configured_providers]
        
        options_html = ''.join([
            f'<option value="{provider}">{provider.capitalize()}</option>'
            for provider in available_options
        ])
        
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
        </div>
        '''
    
    def _parse_form_data(self, request):
        """HTTP concern: parse form data from request"""
        if hasattr(request, 'form'):
            return request.form
        elif hasattr(request, 'data'):
            # Parse raw form data
            form_str = request.data.decode('utf-8')
            return parse_qs(form_str)
        else:
            return {}
    
    def _get_form_value(self, form_data, key, default=''):
        """HTTP concern: extract single value from form data"""
        value_list = form_data.get(key, [default])
        return value_list[0] if value_list else default
    
    def _send_htmx_response(self, html):
        """Send HTMX HTML response"""
        return html
    
    def _send_error(self, message):
        """Send error response"""
        return f'<div class="error-message">{html.escape(message)}</div>'
    
    def _render_error(self, message):
        """Render error message"""
        return f'<div class="error-message">{html.escape(message)}</div>'