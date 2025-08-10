"""
Dashboard handler - coordinates job management operations
Slim coordinator that delegates to specialized modules
"""
import html
from urllib.parse import urlparse, parse_qs
from .job_manager import JobManager
from .job_form_parser import JobFormParser
from .job_validator import JobValidator
from .job_display import JobDisplay

class DashboardHandler:
    """Coordinates dashboard operations using specialized modules"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_manager = JobManager(backup_config)
    
    def show_dashboard(self, handler):
        """Show the main dashboard with active and deleted jobs"""
        # Get data through job manager
        jobs = self.job_manager.get_all_jobs()
        logs = self.job_manager.get_job_logs()
        deleted_jobs = self.job_manager.get_deleted_jobs()
        
        # Check for config warnings
        config_warning = self.backup_config.get_config_warning()
        warning_html = ""
        if config_warning:
            warning_html = f'''
                <div class="alert alert-error">
                    <strong>Configuration Warning:</strong> {html.escape(config_warning['message'])}<br>
                    Malformed config backed up to: <code>{html.escape(config_warning['backup_path'])}</code><br>
                    Using default configuration. Please check the backup file and repair if needed.
                    <form method="post" action="/dismiss-warning" style="margin-top: 10px;">
                        <input type="submit" value="Dismiss Warning" class="button button-warning">
                    </form>
                </div>
            '''
        
        # Generate display HTML
        job_rows = JobDisplay.build_job_rows(jobs, logs)
        deleted_rows = JobDisplay.build_deleted_job_rows(deleted_jobs)
        
        # Render template
        html_content = self.template_service.render_template(
            'dashboard.html',
            config_warning=warning_html,
            job_rows=job_rows,
            deleted_rows=deleted_rows
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def dismiss_config_warning(self, handler):
        """Dismiss config warning"""
        self.backup_config.clear_config_warning()
        self.template_service.send_redirect(handler, '/')
    
    def show_add_job_form(self, handler):
        """Show form to add new backup job"""
        template = self.template_service.load_template('add_job.html')
        self.template_service.send_html_response(handler, template)
    
    def show_edit_job_form(self, handler, job_name):
        """Show form to edit existing backup job"""
        job_config = self.job_manager.get_job(job_name)
        if not job_config:
            self.template_service.send_error_response(handler, f"Job '{job_name}' not found")
            return
        
        # Get edit form data from display module
        edit_data = JobDisplay.build_edit_form_data(job_config)
        
        # Render edit form
        html_content = self.template_service.render_template(
            'edit_job.html',
            job_name=html.escape(job_name),
            source_type=edit_data['source_type'],
            dest_type=edit_data['dest_type'],
            source_display=edit_data['source_display'],
            dest_display=edit_data['dest_display'],
            hidden_config_fields=edit_data['hidden_config_fields'],
            includes='\n'.join(job_config.get('includes', [])),
            excludes='\n'.join(job_config.get('excludes', [])),
            schedule=job_config.get('schedule', 'manual'),
            enabled_checked='checked' if job_config.get('enabled', True) else ''
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def save_backup_job(self, handler, form_data):
        """Save backup job using modular parsing and validation"""
        # Parse form data
        parsed_job = JobFormParser.parse_job_form(form_data)
        if not parsed_job['valid']:
            self.template_service.send_error_response(handler, parsed_job['error'])
            return
        
        # Validate job configuration
        validation_result = JobValidator.validate_job_config(parsed_job)
        if not validation_result['valid']:
            error_msg = "Validation failed:\n" + "\n".join(validation_result['errors'])
            self.template_service.send_error_response(handler, error_msg)
            return
        
        # Build job configuration
        job_config = {
            'source_type': parsed_job['source_type'],
            'source_config': parsed_job['source_config'],
            'dest_type': parsed_job['dest_type'],
            'dest_config': parsed_job['dest_config'],
            'includes': parsed_job['includes'],
            'excludes': parsed_job['excludes'],
            'schedule': parsed_job['schedule'],
            'enabled': parsed_job['enabled'],
            # Keep legacy source field for backward compatibility
            'source': parsed_job['source_config']['source_string']
        }
        
        # Add validation timestamps
        job_config = JobValidator.add_validation_timestamps(
            job_config, 
            parsed_job['source_type'], 
            parsed_job['dest_type']
        )
        
        # Save job
        self.job_manager.create_job(parsed_job['job_name'], job_config)
        self.template_service.send_redirect(handler, '/')
    
    def delete_backup_job(self, handler, job_name):
        """Delete backup job using job manager"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        self.job_manager.delete_job(job_name)
        self.template_service.send_redirect(handler, '/')
    
    def restore_backup_job(self, handler, job_name):
        """Restore job using job manager"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        self.job_manager.restore_job(job_name)
        self.template_service.send_redirect(handler, '/')
    
    def purge_backup_job(self, handler, job_name):
        """Purge job using job manager"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        self.job_manager.purge_job(job_name)
        self.template_service.send_redirect(handler, '/')
    
    def validate_ssh_source(self, handler, source):
        """AJAX endpoint to validate SSH source"""
        if not source:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'No source provided'
            })
            return
        
        # Delegate to validator
        result = JobValidator.validate_ssh_source(source)
        self.template_service.send_json_response(handler, result)
    
    def validate_rsyncd_destination(self, handler, hostname, share):
        """AJAX endpoint to validate rsyncd destination or discover shares"""
        # Try to get source config from query params for better validation
        url_parts = urlparse(handler.path)
        params = parse_qs(url_parts.query)
        
        source_config = None
        source_hostname = params.get('source_hostname', [''])[0]
        source_username = params.get('source_username', [''])[0]
        
        if source_hostname and source_username:
            source_config = {
                'hostname': source_hostname,
                'username': source_username
            }
        
        # If share is "dummy", this is a discovery request
        if share == "dummy":
            result = JobValidator.discover_rsyncd_shares(hostname, source_config)
        else:
            # This is a validation request for a specific share
            result = JobValidator.validate_rsyncd_destination(hostname, share, source_config)
        
        self.template_service.send_json_response(handler, result)
