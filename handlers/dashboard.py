"""
Dashboard handler - coordinates job management operations
Slim coordinator that delegates to specialized modules
"""
import html
from urllib.parse import urlparse, parse_qs
from .job_manager import JobManager
from .job_form_parser import JobFormParser
from services.job_validator import JobValidator
from .job_display import JobDisplay
from .form_error_handler import FormErrorHandler
from services.job_form_data_builder import JobFormDataBuilder


class DashboardHandler:
    """Coordinates dashboard operations using specialized modules"""

    def __init__(self, backup_config, template_service, scheduler_service=None):
        self.backup_config = backup_config
        self.template_service = template_service
        self.scheduler_service = scheduler_service  # optional; may be unused for now
        self.job_manager = JobManager(backup_config)
        self.error_handler = FormErrorHandler(template_service, self.job_manager)

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
        deleted_rows = JobDisplay.build_deleted_job_rows(deleted_jobs, self.job_manager)

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
        form_data = JobFormDataBuilder.for_new_job()
        template_vars = form_data.to_template_vars()
        html_content = self.template_service.render_template('job_form.html', **template_vars)
        self.template_service.send_html_response(handler, html_content)

    def show_edit_job_form(self, handler, job_name):
        """Show form to edit existing backup job"""
        job_config = self.job_manager.get_job(job_name)
        if not job_config:
            self.template_service.send_error_response(handler, f"Job '{job_name}' not found")
            return

        form_data = JobFormDataBuilder.from_job_config(job_name, job_config)
        template_vars = form_data.to_template_vars()
        html_content = self.template_service.render_template('job_form.html', **template_vars)
        self.template_service.send_html_response(handler, html_content)

    def save_backup_job(self, handler, form_data):
        """Save backup job using modular parsing and validation"""
        # Parse form data
        parsed_job = JobFormParser.parse_job_form(form_data)
        if not parsed_job['valid']:
            self._show_job_form_with_feedback(handler, form_data, 'error', 
                                            f'Form parsing failed: {parsed_job["error"]}', 
                                            {'parsing_error': parsed_job.get('partial_data', 'No data available')})
            return

        # Validate job configuration
        validation_result = JobValidator.validate_job_config(parsed_job)
        if not validation_result['valid']:
            error_msg = "Validation failed: " + "; ".join(validation_result['errors'])
            # Build the job config that would have been saved to show in payload
            attempted_config = {
                'source_type': parsed_job['source_type'],
                'source_config': parsed_job['source_config'],
                'dest_type': parsed_job['dest_type'],
                'dest_config': parsed_job['dest_config'],
                'schedule': parsed_job['schedule'],
                'enabled': parsed_job['enabled'],
                'respect_conflicts': parsed_job.get('respect_conflicts', True)
            }
            self._show_job_form_with_feedback(handler, form_data, 'error', error_msg, 
                                            {parsed_job['job_name']: attempted_config})
            return

        # Check if this is a job rename (edit operation)
        original_job_name = form_data.get('original_job_name', [''])[0]
        new_job_name = parsed_job['job_name']
        is_rename = original_job_name and original_job_name != new_job_name
        
        # Check for naming conflicts with deleted jobs (only for new jobs or renames)
        if not original_job_name or is_rename:
            deleted_jobs = self.job_manager.get_deleted_jobs()
            if new_job_name in deleted_jobs:
                error_msg = f'Job name "{new_job_name}" conflicts with a deleted job. Please restore the deleted job first, or choose a different name.'
                attempted_config = {
                    'source_type': parsed_job['source_type'],
                    'source_config': parsed_job['source_config'],
                    'dest_type': parsed_job['dest_type'],
                    'dest_config': parsed_job['dest_config'],
                    'schedule': parsed_job['schedule'],
                    'enabled': parsed_job['enabled'],
                    'respect_conflicts': parsed_job.get('respect_conflicts', True)
                }
                self._show_job_form_with_feedback(handler, form_data, 'error', error_msg,
                                                {new_job_name: attempted_config})
                return

        # Build job configuration
        job_config = {
            'source_type': parsed_job['source_type'],
            'source_config': parsed_job['source_config'],
            'dest_type': parsed_job['dest_type'],
            'dest_config': parsed_job['dest_config'],
            'schedule': parsed_job['schedule'],
            'enabled': parsed_job['enabled'],
            'respect_conflicts': parsed_job.get('respect_conflicts', True)  # Default to True
        }

        # Handle job rename
        if is_rename:
            # Remove old job
            self.job_manager.delete_job(original_job_name)
            # Rename associated logs
            from services.job_logger import JobLogger
            job_logger = JobLogger()
            job_logger.rename_job_logs(original_job_name, new_job_name)
            # Remove old scheduled job if it exists
            from services.scheduler_service import SchedulerService
            scheduler = SchedulerService()
            scheduler.remove_job(f"backup:{original_job_name}")

        # Add validation timestamps to job logger state
        JobValidator.add_validation_timestamps(
            new_job_name,
            parsed_job['source_type'],
            parsed_job['dest_type']
        )

        # Save job
        self.job_manager.create_job(new_job_name, job_config)
        
        # Schedule the job if it has a schedule
        if job_config.get('enabled') and job_config.get('schedule') != 'manual':
            self._schedule_job(new_job_name, job_config)
        
        # Show success feedback with payload
        self._show_job_form_with_feedback(handler, form_data, 'success', 
                                        f'Job "{new_job_name}" saved successfully', 
                                        {new_job_name: job_config})
    
    def _schedule_job(self, job_name, job_config):
        """Schedule a job if it has a valid schedule"""
        from services.schedule_loader import _resolve_cron_string
        from services.scheduler_service import SchedulerService
        from handlers.backup import BackupHandler
        
        cron_str = _resolve_cron_string(job_config.get('schedule', 'manual'), self.backup_config)
        if not cron_str:
            return
        
        # Get global settings for timezone and dry run defaults
        global_settings = self.backup_config.config.get('global_settings', {})
        tz = global_settings.get('scheduler_timezone', 'UTC')
        default_dry = bool(global_settings.get('default_dry_run_on_schedule', True))
        dry = bool(job_config.get('dry_run_on_schedule', default_dry))
        
        # Create backup handler and scheduler
        backup_handler = BackupHandler(self.backup_config)
        scheduler = SchedulerService()
        
        job_id = f"backup:{job_name}"
        
        def _run(job_name=job_name, dry_run=dry):
            backup_handler.run_backup_job_with_conflict_check(handler=None, job_name=job_name, dry_run=dry_run, source="schedule")
        
        # Remove existing job and add new one
        scheduler.remove_job(job_id)
        scheduler.add_crontab_job(
            func=_run,
            job_id=job_id,
            crontab=cron_str,
            timezone=tz
        )

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

    def _show_job_form_with_feedback(self, handler, form_data, feedback_type, message, payload):
        """Show job form with success/error feedback and YAML payload"""
        import yaml
        
        # Convert payload to YAML
        try:
            yaml_payload = yaml.dump(payload, default_flow_style=False, indent=2)
        except Exception as e:
            yaml_payload = f"Error converting to YAML: {str(e)}\nRaw data: {payload}"
        
        # Build form data from the original form submission
        from services.job_form_data_builder import JobFormDataBuilder
        
        # For errors, try to preserve as much form data as possible
        job_name = form_data.get('job_name', [''])[0] if 'job_name' in form_data else ''
        
        if feedback_type == 'error':
            # Create form data that preserves user input from form submission
            try:
                # Check if we have a valid job config in the payload (from validation errors)
                if payload and len(payload) == 1 and 'parsing_error' not in payload:
                    # We have a parsed job config, use it directly
                    job_name_from_payload = list(payload.keys())[0]
                    job_config = list(payload.values())[0]
                    form_obj = JobFormDataBuilder.from_job_config(job_name_from_payload, job_config)
                    form_obj.is_edit = False  # This is still a new job, just preserving input
                else:
                    # We don't have valid parsed config, try parsing form data
                    from .job_form_parser import JobFormParser
                    parsed_result = JobFormParser.parse_job_form(form_data)
                    
                    if parsed_result['valid']:
                        # If parsing succeeds, use the parsed config to build form data
                        form_obj = JobFormDataBuilder.from_job_config(parsed_result['job_name'], parsed_result['job_config'])
                        form_obj.is_edit = False  # This is still a new job, just preserving input
                    else:
                        # If parsing fails, use form submission method
                        form_obj = JobFormDataBuilder.from_form_submission(form_data)
                
                form_obj.error_message = message
            except Exception as e:
                # Fallback to basic form if parsing fails
                form_obj = JobFormDataBuilder.for_new_job()
                form_obj.error_message = message
                form_obj.job_name = job_name
        else:
            # For success, show clean form or edit form
            if 'original_job_name' in form_data:
                # This was an edit - show the updated job
                form_obj = JobFormDataBuilder.from_job_config(job_name, list(payload.values())[0])
            else:
                # This was a new job - show clean form
                form_obj = JobFormDataBuilder.for_new_job()
        
        # Set feedback variables on form object
        form_obj.feedback_type = feedback_type
        form_obj.feedback_message = message  
        form_obj.feedback_payload = yaml_payload
        
        # Generate template variables
        template_vars = form_obj.to_template_vars()
        
        # Render and send
        html_content = self.template_service.render_template('job_form.html', **template_vars)
        self.template_service.send_html_response(handler, html_content)

    def validate_ssh_source(self, handler, source):
        """AJAX endpoint to validate SSH source"""
        if not source:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'No source provided'
            })
            return

        # Import here to avoid circular import
        from services.ssh_validator import validate_ssh_source
        
        # Delegate to validator
        result = validate_ssh_source(source)
        self.template_service.send_json_response(handler, result)

    def validate_source_paths(self, handler, form_data):
        """AJAX endpoint to validate source paths with permission checking"""
        try:
            from .job_form_parser import JobFormParser
            from services.source_path_validator import SourcePathValidator
            
            # Parse source configuration from form data
            source_result = JobFormParser.parse_source_configuration(form_data)
            
            if source_result.get('valid'):
                result = SourcePathValidator.validate_source_paths(source_result['config'])
            else:
                result = {'success': False, 'message': source_result.get('error', 'Invalid source configuration')}
            
            self.template_service.send_json_response(handler, result)
        
        except Exception as e:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': f'Source validation failed: {str(e)}'
            })

    def show_job_history(self, handler, job_name):
        """Show job execution history"""
        if not job_name:
            self.template_service.send_error_response(handler, "Job name required")
            return

        job_config = self.job_manager.get_job(job_name)
        if not job_config:
            self.template_service.send_error_response(handler, f"Job '{job_name}' not found")
            return

        logs = self.job_manager.get_job_logs()
        job_log = logs.get(job_name, {})

        # Render history template
        html_content = self.template_service.render_template(
            'job_history.html',
            job_name=html.escape(job_name),
            last_run=job_log.get('last_run', 'Never'),
            status=job_log.get('status', 'No runs'),
            message=html.escape(job_log.get('message', 'No message'))
        )

        self.template_service.send_html_response(handler, html_content)

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

    def validate_source_paths(self, handler, form_data):
        """AJAX endpoint to validate source paths with permission checking"""
        try:
            from .job_form_parser import JobFormParser
            from services.source_path_validator import SourcePathValidator
            
            # Parse source configuration from form data
            source_result = JobFormParser.parse_source_configuration(form_data)
            
            if source_result.get('valid'):
                result = SourcePathValidator.validate_source_paths(source_result['config'])
            else:
                result = {'success': False, 'message': source_result.get('error', 'Invalid source configuration')}
            
            self.template_service.send_json_response(handler, result)
        
        except Exception as e:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': f'Source validation failed: {str(e)}'
            })
