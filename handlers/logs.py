"""
Logs handler for viewing log files
"""
import os
import html
from services.template_service import TemplateService
class LogsHandler:
    """Handles log viewing"""
    
    LOG_TYPES = {
        'app': {
            'name': 'Application Logs',
            'file': '/var/log/supervisor/backup-app.log'
        },
        'nginx': {
            'name': 'Nginx Access',
            'file': '/var/log/nginx/backup-manager.access.log'
        },
        'nginx-error': {
            'name': 'Nginx Errors',
            'file': '/var/log/nginx/backup-manager.error.log'
        },
        'supervisor': {
            'name': 'Supervisor',
            'file': '/var/log/supervisor/supervisord.log'
        },
    }
    
    def __init__(self, template_service, backup_config=None):
        self.template_service = template_service
        self.backup_config = backup_config
    
    def show_logs(self, handler, log_type='app'):
        """Show logs viewer"""
        from urllib.parse import urlparse, parse_qs
        
        # Check if this is a job log request
        url_parts = urlparse(handler.path)
        params = parse_qs(url_parts.query)
        job_name = params.get('job', [''])[0]
        
        if job_name:
            # Show job-specific log
            log_file = f'/var/log/highball/jobs/{job_name}.log'
            log_name = f'Job: {job_name}'
            log_content = self._read_log_file(log_file)
            log_buttons = self._generate_log_buttons(log_type)  # Show system log buttons
        else:
            # Show system logs
            # Validate log type
            if log_type not in self.LOG_TYPES:
                log_type = 'app'
            
            current_log = self.LOG_TYPES[log_type]
            log_name = current_log['name']
            log_content = self._read_log_file(current_log['file'])
            log_buttons = self._generate_log_buttons(log_type)
        
        # Generate job dropdown with system option
        job_dropdown = self._generate_job_dropdown(job_name)
        
        # Generate Restic job dropdown
        restic_job_dropdown = self._generate_restic_job_dropdown()
        
        # Render template
        html_content = self.template_service.render_template(
            'logs.html',
            log_buttons=log_buttons,
            log_content=log_content,
            log_type=log_type,
            log_name=log_name,
            job_dropdown=job_dropdown,
            restic_job_dropdown=restic_job_dropdown
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    
    def _generate_log_buttons(self, current_log_type):
        """Generate HTML for log type selection buttons"""
        buttons = ""
        for log_type, info in self.LOG_TYPES.items():
            active_class = "button-success" if log_type == current_log_type else ""
            buttons += f'<a href="/logs?type={log_type}" class="button {active_class}">{info["name"]}</a>\n'
        return buttons
    
    def _generate_job_dropdown(self, selected_job=None):
        """Generate HTML for job log selection dropdown with system option"""
        # System option (selected when no job is selected)
        system_selected = 'selected' if not selected_job else ''
        options = f'<option value="" {system_selected}>-- System --</option>\n'
        
        if not self.backup_config:
            return options
        
        jobs = self.backup_config.config.get('backup_jobs', {})
        if not jobs:
            return options
        
        # Add job options
        for job_name in sorted(jobs.keys()):
            selected = 'selected' if job_name == selected_job else ''
            options += f'<option value="{html.escape(job_name)}" {selected}>{html.escape(job_name)}</option>\n'
        
        return options
    
    def _generate_restic_job_dropdown(self):
        """Generate HTML for Restic job selection dropdown"""
        options = ""
        
        if not self.backup_config:
            return options
        
        jobs = self.backup_config.config.get('backup_jobs', {})
        if not jobs:
            return options
        
        # Find all Restic jobs
        restic_jobs = []
        for job_name, job_config in jobs.items():
            if job_config.get('dest_type') == 'restic':
                restic_jobs.append(job_name)
        
        # Sort and generate options
        for job_name in sorted(restic_jobs):
            options += f'<option value="{html.escape(job_name)}">{html.escape(job_name)}</option>\n'
        
        return options
    
    def _read_log_file(self, log_file):
        """Read last 100 lines of log file"""
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return ''.join(lines[-100:]) if lines else 'No logs yet - job has not generated any log entries.'
            else:
                # More helpful message when log file doesn't exist
                if '/jobs/' in log_file:
                    job_name = os.path.basename(log_file).replace('.log', '')
                    return f'No log file yet for job "{job_name}". Job has not been executed (test or run) since creation.'
                else:
                    return f"Log file {log_file} not found"
        except Exception as e:
            return f"Error reading log: {str(e)}"
    
