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

    def __init__(self, backup_config, template_service, scheduler_service=None):
        self.backup_config = backup_config
        self.template_service = template_service
        self.scheduler_service = scheduler_service  # optional; may be unused for now
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

        # Parse current configuration
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        source_type = job_config.get('source_type', 'ssh')
        dest_type = job_config.get('dest_type', 'rsyncd')
        
        # Parse schedule - detect if it's a cron pattern
        schedule = job_config.get('schedule', 'manual')
        schedule_type = schedule
        cron_pattern = ''
        
        # Check if it's a cron pattern (has spaces and not in known types)
        if ' ' in schedule and schedule not in ['manual', 'hourly', 'daily', 'weekly']:
            schedule_type = 'cron'
            cron_pattern = schedule

        # Render edit form with full field population
        html_content = self.template_service.render_template(
            'edit_job.html',
            job_name=html.escape(job_name),
            source_type=source_type,
            dest_type=dest_type,
            # Source fields
            source_local_path=source_config.get('path', ''),
            source_ssh_hostname=source_config.get('hostname', ''),
            source_ssh_username=source_config.get('username', ''),
            source_ssh_path=source_config.get('path', ''),
            # Dest fields
            dest_local_path=dest_config.get('path', ''),
            dest_ssh_hostname=dest_config.get('hostname', ''),
            dest_ssh_username=dest_config.get('username', ''),
            dest_ssh_path=dest_config.get('path', ''),
            dest_rsyncd_hostname=dest_config.get('hostname', ''),
            dest_rsyncd_share=dest_config.get('share', ''),
            # Patterns and schedule
            includes='\n'.join(job_config.get('includes', [])),
            excludes='\n'.join(job_config.get('excludes', [])),
            schedule_type=schedule_type,
            cron_pattern=cron_pattern,
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

        # Check if this is a job rename (edit operation)
        original_job_name = form_data.get('original_job_name', [''])[0]
        new_job_name = parsed_job['job_name']
        is_rename = original_job_name and original_job_name != new_job_name

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
        
        self.template_service.send_redirect(handler, '/')
    
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

    def validate_ssh_source(self, handler, source):
        """AJAX endpoint to validate SSH source"""
        if not source:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'No source provided'
            })
            return

        # Import here to avoid circular import
        from services.ssh_validator import SSHValidator
        
        # Delegate to validator
        result = SSHValidator.validate_ssh_source(source)
        self.template_service.send_json_response(handler, result)

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
