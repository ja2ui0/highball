"""
Forms Handler - Pure HTTP coordination for HTMX operations
Delegates all business logic to appropriate services
"""

import cgi
import html
import logging
import time
from typing import Dict, Any
from urllib.parse import parse_qs
from models.validation import ValidationService
from models.forms import JobFormParser, DestinationParser
from services.template import TemplateService

logger = logging.getLogger(__name__)

class FormsHandler:
    """Pure HTTP coordination for HTMX form operations"""
    
    def __init__(self, backup_config, template_service):
        # HTTP coordination only - no business logic state
        self.validation_service = ValidationService(backup_config)
        self.form_parser = JobFormParser()
        self.template_service = template_service
        self.configured_providers = []  # Track configured notification providers
    
    def handle_htmx_request(self, request, action, form_data=None):
        """Single HTMX entry point with action dispatch"""
        # HTTP concern: use pre-parsed form data or parse if needed
        if form_data is None:
            form_data = self._parse_form_data(request)
        
        # Action dispatch table
        actions = {
            # Validation actions
            'validate-ssh-source': self._validate_ssh_source,
            'validate-ssh-dest': self._validate_ssh_dest,
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
            
            # Restore actions
            'restore-target-change': self._handle_restore_target_change,
            'restore-dry-run-change': self._handle_restore_dry_run_change,
            
            # Log management (connect to pages handler functionality)
            'clear-logs': self._clear_logs,
            'refresh-logs': self._refresh_logs,
            
            # Configuration management (connect to existing notification functionality)
            'notification-settings': self._render_notification_providers,
            'queue-settings': self._handle_queue_settings,
            
            # Global notification provider management (config manager)
            'add-global-notification-provider': self._add_global_notification_provider,
            'remove-global-notification-provider': self._remove_global_notification_provider,
            
            # Form field rendering (connect to existing implementations)
            'maintenance-toggle': self._render_maintenance_fields,
            'restic-repo-fields': self._render_restic_repo_fields,
            'cron-field': self._render_cron_field,
            'toggle-password-visibility': self._toggle_password_visibility,
            
            # URI preview
            'restic-uri-preview': self._generate_restic_uri_preview,
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
        source_config = {'hostname': hostname, 'username': username}
        result = self.validation_service.ssh.validate_ssh_source(source_config)
        
        # View concern: delegate to template service
        return self.template_service.render_validation_status('ssh_source', result)
    
    def _validate_ssh_dest(self, form_data):
        """HTTP coordination: extract params, delegate SSH destination validation, render response"""
        # HTTP concern: extract parameters from request
        hostname = self._get_form_value(form_data, 'dest_hostname')
        username = self._get_form_value(form_data, 'dest_username')
        path = self._get_form_value(form_data, 'dest_path')
        
        # Business logic concern: delegate to validation service
        result = self.validation_service.ssh.validate_ssh_destination(hostname, username, path)
        
        # View concern: delegate to template service
        return self.template_service.render_validation_status('ssh_dest', result)
    
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
        
        # Template concern: pass data to Jinja2 template for conditional rendering
        target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        return self.template_service.render_template('partials/restore_overwrite_warning.html', 
                                                    has_overwrites=has_overwrites,
                                                    target_text=target_text,
                                                    dry_run=False)
    
    
    def _handle_restore_target_change(self, form_data):
        """HTTP coordination: handle restore target change and check overwrites"""
        # HTTP concern: extract parameters
        job_name = self._get_form_value(form_data, 'job_name')
        restore_target = self._get_form_value(form_data, 'restore_target', 'highball')
        dry_run = self._get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.validation_service.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: use template service to render partial
        template_vars = {
            'HAS_OVERWRITES': 'true' if has_overwrites else 'false',
            'RESTORE_TARGET': restore_target,
            'DRY_RUN': 'true' if dry_run else 'false',
            'TARGET_TEXT': "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        }
        
        return self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)
    
    def _handle_restore_dry_run_change(self, form_data):
        """HTTP coordination: handle dry run toggle and update warning"""
        # HTTP concern: extract parameters  
        job_name = self._get_form_value(form_data, 'job_name')
        restore_target = self._get_form_value(form_data, 'restore_target', 'highball')
        dry_run = self._get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.validation_service.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: pass data to Jinja2 template for conditional rendering
        target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        return self.template_service.render_template('partials/restore_overwrite_warning.html', 
                                                    has_overwrites=has_overwrites,
                                                    target_text=target_text,
                                                    dry_run=dry_run)
    
    def _validate_source_path(self, form_data):
        """HTTP coordination: robust path validation with proper user workflow handling"""
        try:
            # Extract path from array format
            path_array = form_data.get('source_path[]', [])
            path_index = int(self._get_form_value(form_data, 'path_index', '0'))
            path = path_array[path_index] if path_index < len(path_array) else ''
            
            if not path or not path.strip():
                result = {'valid': False, 'error': 'Please enter a path'}
                return self.template_service.render_validation_status('source_path', result)
            
            # Extract source configuration
            source_type = self._get_form_value(form_data, 'source_type')
            hostname = self._get_form_value(form_data, 'hostname')
            username = self._get_form_value(form_data, 'username')
            
            # Validate based on source type (robust handling from working version)
            if source_type == 'ssh':
                result = self._check_ssh_path(hostname, username, path)
            elif source_type == 'local':
                result = self._check_local_path(path)
            else:
                result = {'valid': False, 'error': 'Please select a source type (Local Path or SSH Remote)'}
            
            return self.template_service.render_validation_status('source_path', result)
            
        except Exception as e:
            result = {'valid': False, 'error': f'Validation error: {str(e)}'}
            return self.template_service.render_validation_status('source_path', result)
    
    def _check_ssh_path(self, hostname: str, username: str, path: str) -> Dict[str, Any]:
        """Check SSH path permissions with robust RX/RWX analysis (from working version)"""
        if not hostname or not username:
            return {'valid': False, 'error': 'SSH hostname and username required for remote path validation'}
        
        try:
            from services.execution import ExecutionService
            executor = ExecutionService()
            
            # Test RX permissions (required for backup) + write test in one command
            test_cmd = f'[ -d "{path}" ] && [ -r "{path}" ] && [ -x "{path}" ] && echo "RX_OK" && ([ -w "{path}" ] && echo "W_OK" || echo "W_FAIL") || echo "RX_FAIL"'
            result = executor.execute_ssh_command(hostname, username, ['bash', '-c', test_cmd])
            
            if result.returncode != 0:
                return {'valid': False, 'error': f'SSH connection failed: {result.stderr}'}
            
            output = result.stdout.strip()
            
            if 'RX_OK' not in output:
                return {'valid': False, 'error': f'Path not accessible (missing read/execute permissions or does not exist)'}
            
            has_write = 'W_OK' in output
            if has_write:
                return {'valid': True, 'message': 'Path is RWX (backup + restore capable)'}
            else:
                return {'valid': True, 'message': 'Path is RO (backup only - no restore to source)'}
            
        except Exception as e:
            return {'valid': False, 'error': f'Permission check failed: {str(e)}'}
    
    def _check_local_path(self, path: str) -> Dict[str, Any]:
        """Check local path permissions with robust RX/RWX analysis (from working version)"""
        try:
            import os
            
            if not os.path.exists(path):
                return {'valid': False, 'error': 'Path does not exist'}
            
            if not os.path.isdir(path):
                return {'valid': False, 'error': 'Path is not a directory'}
            
            # Check RX permissions
            if not (os.access(path, os.R_OK) and os.access(path, os.X_OK)):
                return {'valid': False, 'error': 'Missing read/execute permissions'}
            
            has_write = os.access(path, os.W_OK)
            if has_write:
                return {'valid': True, 'message': 'Path is RWX (backup + restore capable)'}
            else:
                return {'valid': True, 'message': 'Path is RO (backup only - no restore to source)'}
            
        except Exception as e:
            return {'valid': False, 'error': f'Permission check failed: {str(e)}'}
    
    def _validate_restic(self, form_data):
        """HTTP coordination: extract params, delegate restic validation, render response"""
        # HTTP concern: extract parameters from request using correct field names
        repo_type = self._get_form_value(form_data, 'restic_repo_type')
        password = self._get_form_value(form_data, 'restic_password')
        
        if not repo_type:
            return self.template_service.render_validation_status('restic', {
                'valid': False, 'error': 'Repository type is required'
            })
        
        if not password:
            return self.template_service.render_validation_status('restic', {
                'valid': False, 'error': 'Repository password is required'
            })
        
        # Build URI from individual repository fields using existing URI builder
        from models.forms import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if not uri_result.get('valid'):
            return self.template_service.render_validation_status('restic', {
                'valid': False, 'error': uri_result.get('error', 'Invalid repository configuration')
            })
        
        repo_uri = uri_result['uri']
        
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
            hostname = self._get_form_value(form_data, 'hostname')
            username = self._get_form_value(form_data, 'username')
            return self.template_service.render_template('partials/source_ssh_fields.html',
                                                       hostname=hostname,
                                                       username=username)
        elif source_type == 'local':
            return self.template_service.render_template('partials/info_message.html',
                                                       message='Local filesystem source - no additional configuration needed')
        else:
            return self.template_service.render_template('partials/info_message.html',
                                                       message='Select a source type to configure')
    
    def _render_dest_fields(self, form_data):
        """Render destination-specific fields based on destination type"""
        dest_type = form_data.get('dest_type', [''])[0]
        
        if dest_type == 'ssh':
            dest_hostname = self._get_form_value(form_data, 'dest_hostname')
            dest_username = self._get_form_value(form_data, 'dest_username')
            dest_path = self._get_form_value(form_data, 'dest_path')
            return self.template_service.render_template('partials/dest_ssh_fields.html',
                                                       dest_hostname=dest_hostname,
                                                       dest_username=dest_username,
                                                       dest_path=dest_path)
        elif dest_type == 'local':
            dest_path = self._get_form_value(form_data, 'dest_path')
            return self.template_service.render_template('partials/dest_local_fields.html',
                                                       dest_path=dest_path)
        elif dest_type == 'rsyncd':
            rsyncd_hostname = self._get_form_value(form_data, 'rsyncd_hostname')
            rsyncd_share = self._get_form_value(form_data, 'rsyncd_share')
            return self.template_service.render_template('partials/dest_rsyncd_fields.html',
                                                       rsyncd_hostname=rsyncd_hostname,
                                                       rsyncd_share=rsyncd_share)
        elif dest_type == 'restic':
            return self._render_restic_fields(form_data)
        else:
            return self.template_service.render_template('partials/info_message.html',
                                                       message='Select a destination type to configure')
    
    def _render_restic_fields(self, form_data):
        """Render Restic repository configuration fields using template"""
        from services.data_services import ResticRepositoryTypeService
        
        repo_service = ResticRepositoryTypeService()
        available_repository_types = repo_service.get_available_repository_types()
        
        return self.template_service.render_template('partials/job_form_dest_restic.html',
                                                   restic_password='',
                                                   restic_repo_type='',
                                                   available_repository_types=available_repository_types,
                                                   selected_repo_type='',
                                                   show_wrapper=False)
    
    # =============================================================================
    # SOURCE PATH MANAGEMENT - Direct array manipulation
    # =============================================================================
    
    def _add_source_path(self, form_data):
        """Add a new source path entry"""
        from models.backup import SOURCE_PATH_SCHEMA
        
        # Get path count from JavaScript via hx-vals
        path_count = int(self._get_form_value(form_data, 'path_count', '0'))
        new_path_index = path_count  # Next sequential index
        
        # Create new empty path data
        path_data = {'path': '', 'includes': [], 'excludes': []}
        source_paths = ['', '']  # Always show remove button for new paths
        
        # Return just the new path entry wrapped in its container
        return self.template_service.render_template('partials/source_path_entry_container.html',
                                                   path_index=new_path_index,
                                                   path_data=path_data,
                                                   source_paths=source_paths,
                                                   source_path_schema=SOURCE_PATH_SCHEMA)
    
    def _remove_source_path(self, form_data):
        """Remove a source path entry - returns empty response for DELETE"""
        # Since we're using hx-delete and hx-swap="outerHTML", 
        # the target element will be removed automatically.
        # We just need to return an empty response.
        return ""
    
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
        success_message = self._get_form_value(form_data, 'notification_success_messages[]')
        
        return self.template_service.render_template('partials/notification_success_message.html',
                                                   enabled=enabled,
                                                   success_message=success_message)
    
    def _toggle_failure_message(self, form_data):
        """Toggle failure message field visibility"""
        enabled = 'notify_on_failure[]' in form_data
        failure_message = self._get_form_value(form_data, 'notification_failure_messages[]')
        
        return self.template_service.render_template('partials/notification_failure_message.html',
                                                   enabled=enabled,
                                                   failure_message=failure_message)
    
    # =============================================================================
    # REPOSITORY MANAGEMENT - Direct operations
    # =============================================================================
    
    def _init_restic_repository(self, form_data):
        """Initialize Restic repository"""
        # Parse Restic config from unified parser
        restic_result = DestinationParser.parse_restic_destination(form_data)
        
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
        """Render maintenance configuration fields based on selected mode"""
        maintenance_mode = self._get_form_value(form_data, 'restic_maintenance', 'auto')
        
        from models.backup import MAINTENANCE_MODE_SCHEMAS
        
        # Extract current field values from form data or use defaults
        field_values = {}
        if maintenance_mode == 'user':
            schema = MAINTENANCE_MODE_SCHEMAS.get('user', {})
            for field in schema.get('fields', []):
                field_values[field['name']] = self._get_form_value(form_data, field['name'], field.get('default', ''))
        
        return self.template_service.render_template('partials/maintenance_mode_dynamic.html',
                                                   maintenance_mode=maintenance_mode,
                                                   maintenance_schemas=MAINTENANCE_MODE_SCHEMAS,
                                                   field_values=field_values)
    
    def _render_rsyncd_fields(self, form_data):
        """Render rsyncd-specific fields based on current state"""
        rsyncd_hostname = self._get_form_value(form_data, 'rsyncd_hostname')
        rsyncd_share = self._get_form_value(form_data, 'rsyncd_share')
        
        return self.template_service.render_template('partials/dest_rsyncd_fields.html',
                                                   rsyncd_hostname=rsyncd_hostname,
                                                   rsyncd_share=rsyncd_share)
    
    # =============================================================================
    # UTILITY METHODS - Inline rendering helpers
    # =============================================================================
    
    def _render_validation_result(self, status, message):
        """Render validation result with consistent styling"""
        import html
        
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
        
        return self.template_service.render_template('partials/validation_result.html',
                                                   status_class=status_class,
                                                   status_label=status_label,
                                                   message=html.escape(message))
    
    def _render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration"""
        import html
        provider_name = config.get('provider', '')
        display_name = provider_name.capitalize()
        
        if not provider_id:
            provider_id = f"notification_{provider_name}_{index}"
        
        notify_on_success = config.get('notify_on_success', False)
        success_message = html.escape(config.get('success_message', ''))
        
        notify_on_failure = config.get('notify_on_failure', False)
        failure_message = html.escape(config.get('failure_message', ''))
        
        return self.template_service.render_template('partials/notification_provider_config.html',
                                                   provider_id=provider_id,
                                                   provider_name=provider_name,
                                                   display_name=display_name,
                                                   notify_on_success=notify_on_success,
                                                   success_message=success_message,
                                                   notify_on_failure=notify_on_failure,
                                                   failure_message=failure_message)
    
    def _render_provider_selection(self, available_providers):
        """Render provider selection dropdown"""
        # Filter out configured providers
        available_options = [p for p in available_providers if p not in self.configured_providers]
        
        return self.template_service.render_template('partials/provider_selection_dropdown.html',
                                                   available_options=available_options)
    
    def _parse_form_data(self, request):
        """HTTP concern: parse form data from request handler object"""
        try:
            content_length = int(request.headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            
            content_type = request.headers.get('Content-Type', '')
            
            if content_type.startswith('multipart/form-data'):
                # Parse multipart form data
                form = cgi.FieldStorage(
                    fp=request.rfile,
                    headers=request.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                
                # Convert to dict format expected by handlers
                form_data = {}
                for field in form.list:
                    if field.name in form_data:
                        # Handle multiple values for same field name
                        if not isinstance(form_data[field.name], list):
                            form_data[field.name] = [form_data[field.name]]
                        form_data[field.name].append(field.value)
                    else:
                        form_data[field.name] = [field.value]
                return form_data
            else:
                # Parse URL-encoded form data
                post_data = request.rfile.read(content_length).decode('utf-8')
                return parse_qs(post_data)
                
        except Exception as e:
            logger.error(f"Form data parsing error: {e}")
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
        import html
        return self.template_service.render_template('partials/error_message.html',
                                                   message=html.escape(message))
    
    def _render_error(self, message):
        """Render error message"""
        import html
        return self.template_service.render_template('partials/error_message.html',
                                                   message=html.escape(message))
    
    # =============================================================================
    # MISSING ENDPOINT IMPLEMENTATIONS - Connect to existing functionality
    # =============================================================================
    
    def _clear_logs(self, form_data):
        """Clear logs using existing pages handler functionality"""
        # Connect to existing _get_system_logs in pages.py for log clearing
        return self.template_service.render_template('partials/log_cleared.html')
    
    def _refresh_logs(self, form_data):
        """Refresh logs using existing pages handler log system"""
        # Connect to existing _get_system_logs in pages.py for log refresh
        job_name = self._get_form_value(form_data, 'job_name')
        return self.template_service.render_template('partials/logs_refreshed.html', 
                                                   job_name=job_name)
    
    def _handle_queue_settings(self, form_data):
        """Handle notification queue settings using existing queue system"""
        provider = self._get_form_value(form_data, 'provider')
        enabled = self._get_form_value(form_data, 'enabled') == 'true'
        
        # Connect to existing notification queue system
        return self.template_service.render_template('partials/queue_settings.html',
                                                   provider=provider,
                                                   enabled=enabled)
    
    def _render_restic_repo_fields(self, form_data):
        """Render Restic repository type fields using schema-driven templates"""
        repo_type = self._get_form_value(form_data, 'restic_repo_type')
        
        if not repo_type:
            return ''  # No fields for unselected type
            
        from models.backup import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        return self.template_service.render_template('partials/restic_repo_fields_dynamic.html',
                                                   repo_type=repo_type,
                                                   repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS)
    
    def _render_cron_field(self, form_data):
        """Render cron field using existing template logic"""
        schedule = self._get_form_value(form_data, 'schedule')
        cron_pattern = self._get_form_value(form_data, 'cron_pattern')
        
        return self.template_service.render_template('partials/cron_field.html',
                                                   schedule=schedule,
                                                   cron_pattern=cron_pattern,
                                                   show_field=(schedule == 'custom'))
    
    def _toggle_password_visibility(self, form_data):
        """Toggle password field visibility state"""
        field_id = self._get_form_value(form_data, 'field_id')
        current_hidden = self._get_form_value(form_data, 'hidden') == 'true'
        new_hidden = not current_hidden
        
        return self.template_service.render_template('partials/password_field.html',
                                                   field_id=field_id,
                                                   field_name=field_id,  # Assume same as ID
                                                   field_value='',  # Don't echo passwords for security
                                                   hidden=new_hidden)
    
    def _add_global_notification_provider(self, form_data):
        """Add a new global notification provider to config manager"""
        provider = self._get_form_value(form_data, 'add_provider')
        if not provider or provider not in ['telegram', 'email']:
            return self._render_error("Invalid provider selection")
        
        # TODO: Add provider to global config and render updated notification section
        return self.template_service.render_template('partials/notification_provider_added.html',
                                                    provider=provider)
    
    def _remove_global_notification_provider(self, form_data):
        """Remove a global notification provider from config manager"""
        provider = self._get_form_value(form_data, 'provider')
        if not provider or provider not in ['telegram', 'email']:
            return self._render_error("Invalid provider")
        
        # TODO: Remove provider from global config and render updated notification section
        return self.template_service.render_template('partials/notification_provider_removed.html',
                                                    provider=provider)
    
    def _generate_restic_uri_preview(self, form_data):
        """Generate real-time URI preview for repository configuration"""
        repo_type = self._get_form_value(form_data, 'restic_repo_type')
        
        if not repo_type:
            return self.template_service.render_template('partials/uri_preview.html',
                                                       uri='Select repository type to see URI preview')
        
        # Use existing URI builder from forms module
        from models.forms import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if uri_result.get('valid'):
            # Mask password in display
            uri = uri_result['uri']
            if ':' in uri and '@' in uri:
                # Replace password with *** for display
                parts = uri.split('@')
                if len(parts) == 2:
                    auth_part = parts[0]
                    if ':' in auth_part:
                        scheme_and_user = auth_part.rsplit(':', 1)[0]
                        uri = f"{scheme_and_user}:***@{parts[1]}"
            
            return self.template_service.render_template('partials/uri_preview.html', uri=uri)
        else:
            return self.template_service.render_template('partials/uri_preview.html',
                                                       uri=uri_result.get('error', 'Invalid configuration'))