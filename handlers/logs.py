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
        'job-status': {
            'name': 'Job Status',
            'file': '/var/log/highball/job_status.yaml'
        },
        'running-jobs': {
            'name': 'Running Jobs',
            'file': '/var/log/highball/running_jobs.txt'
        },
        'validation': {
            'name': 'SSH Validation Cache',
            'file': '/var/log/highball/job_validation.yaml'
        },
        'notification-queues': {
            'name': 'Notification Queues',
            'file': '/var/log/highball/notification_queues'
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
        
        # Generate backup job dropdown and job types for browser
        backup_job_dropdown, job_types_js = self._generate_backup_job_dropdown()
        
        # Render template
        html_content = self.template_service.render_template(
            'logs.html',
            log_buttons=log_buttons,
            log_content=log_content,
            log_type=log_type,
            log_name=log_name,
            job_dropdown=job_dropdown,
            backup_job_dropdown=backup_job_dropdown,
            job_types_js=job_types_js
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    
    def _generate_log_buttons(self, current_log_type):
        """Generate HTML for log type selection buttons"""
        buttons = ""
        button_count = 0
        for log_type, info in self.LOG_TYPES.items():
            active_class = "button-success" if log_type == current_log_type else ""
            buttons += f'<a href="/logs?type={log_type}" class="button {active_class}">{info["name"]}</a>\n'
            button_count += 1
            # Add line break after Supervisor (4th button)
            if button_count == 4:
                buttons += '<br>\n'
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
    
    def _generate_backup_job_dropdown(self):
        """Generate HTML for backup job selection dropdown and job types JavaScript"""
        options = ""
        job_types = {}
        
        if not self.backup_config:
            return options, ""
        
        jobs = self.backup_config.config.get('backup_jobs', {})
        if not jobs:
            return options, ""
        
        # Generate options for all backup jobs and collect job types
        for job_name in sorted(jobs.keys()):
            job_config = jobs[job_name]
            dest_type = job_config.get('dest_type', 'unknown')
            
            options += f'<option value="{html.escape(job_name)}">{html.escape(job_name)}</option>\n'
            job_types[job_name] = dest_type
        
        # Generate JavaScript for job types
        import json
        job_types_js = f"<script>window.jobTypes = {json.dumps(job_types)};</script>"
        
        return options, job_types_js
    
    def _read_log_file(self, log_file):
        """Read last 100 lines of log file or directory contents"""
        try:
            # Special handling for notification queues directory
            if log_file == '/var/log/highball/notification_queues':
                return self._read_notification_queues_dir(log_file)
            
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
    
    def _read_notification_queues_dir(self, queue_dir):
        """Read all notification queue files and combine into single view"""
        try:
            if not os.path.exists(queue_dir):
                return "Notification queue directory not found - no queues have been created yet."
            
            queue_files = [f for f in os.listdir(queue_dir) if f.endswith('.yaml')]
            
            if not queue_files:
                return "No notification queue files found - all queues are empty."
            
            content = f"Notification Queue Status ({len(queue_files)} active queues):\n\n"
            
            for queue_file in sorted(queue_files):
                provider = queue_file.replace('_state.yaml', '')
                content += f"=== {provider.upper()} QUEUE ===\n"
                
                try:
                    with open(os.path.join(queue_dir, queue_file), 'r') as f:
                        file_content = f.read()
                        content += file_content + "\n"
                except Exception as e:
                    content += f"Error reading {queue_file}: {str(e)}\n"
                
                content += "\n"
            
            return content
            
        except Exception as e:
            return f"Error reading notification queues: {str(e)}"
    
