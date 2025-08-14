"""
Inspect handler for per-job inspection and restore operations
"""
import os
import html
from urllib.parse import urlparse, parse_qs


class InspectHandler:
    """Handles per-job inspection including logs, backup browser, and restore controls"""
    
    def __init__(self, template_service, backup_config):
        self.template_service = template_service
        self.backup_config = backup_config
    
    def show_job_inspect(self, handler):
        """Show per-job inspection page - requires job name parameter"""
        # Parse job name from query parameters
        url_parts = urlparse(handler.path)
        params = parse_qs(url_parts.query)
        job_name = params.get('name', [''])[0]
        
        # Require job name
        if not job_name:
            self.template_service.send_error_response(handler, 
                "Job name required. Use /inspect?name=<jobname>")
            return
        
        # Validate job exists
        jobs = self.backup_config.config.get('backup_jobs', {})
        if job_name not in jobs:
            self.template_service.send_error_response(handler, 
                f"Job '{job_name}' not found")
            return
        
        job_config = jobs[job_name]
        
        # Generate job-specific backup browser data
        backup_job_dropdown, job_types_js = self._generate_single_job_dropdown(job_name)
        
        # Get job status information (from history functionality)
        from .job_manager import JobManager
        job_manager = JobManager(self.backup_config)
        logs = job_manager.get_job_logs()
        job_log = logs.get(job_name, {})
        
        # Read job log content
        job_log_content = self._read_job_log(job_name)
        
        # Render template
        html_content = self.template_service.render_template(
            'job_inspect.html',
            job_name=html.escape(job_name),
            job_type=job_config.get('dest_type', 'unknown'),
            last_run=job_log.get('last_run', 'Never'),
            status=job_log.get('status', 'No runs'),
            message=html.escape(job_log.get('message', 'No message')),
            backup_job_dropdown=backup_job_dropdown,
            job_types_js=job_types_js,
            job_log_content=job_log_content
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def _generate_single_job_dropdown(self, job_name):
        """Generate dropdown with single job pre-selected and job types JavaScript"""
        job_config = self.backup_config.config.get('backup_jobs', {}).get(job_name, {})
        dest_type = job_config.get('dest_type', 'unknown')
        
        # Single option dropdown (pre-selected)
        options = f'<option value="{html.escape(job_name)}" selected>{html.escape(job_name)}</option>\n'
        
        # JavaScript for job types (single job)
        import json
        job_types = {job_name: dest_type}
        job_types_js = f"<script>window.jobTypes = {json.dumps(job_types)};</script>"
        
        return options, job_types_js
    
    def _read_job_log(self, job_name):
        """Read job-specific log file"""
        log_file = f'/var/log/highball/jobs/{job_name}.log'
        
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return ''.join(lines[-100:]) if lines else 'No logs yet - job has not generated any log entries.'
            else:
                return f'No log file yet for job "{job_name}". Job has not been executed (test or run) since creation.'
        except Exception as e:
            return f"Error reading job log: {str(e)}"