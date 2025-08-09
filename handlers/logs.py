"""
Logs handler for viewing and streaming log files
"""

import os
import subprocess
import time
import html
from services.template_service import TemplateService

class LogsHandler:
    """Handles log viewing and streaming"""
    
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
        'backup-dry-run': {
            'name': 'Backup Dry Run',
            'file': '/tmp/backup-dry-run.log'
        }
    }
    
    def __init__(self, template_service):
        self.template_service = template_service
    
    def show_logs(self, handler, log_type='app'):
        """Show logs viewer with live tailing capability"""
        # Validate log type
        if log_type not in self.LOG_TYPES:
            log_type = 'app'
        
        current_log = self.LOG_TYPES[log_type]
        
        # Generate log type buttons
        log_buttons = self._generate_log_buttons(log_type)
        
        # Get current log content
        log_content = self._read_log_file(current_log['file'])
        
        # Render template
        html_content = self.template_service.render_template(
            'logs.html',
            log_buttons=log_buttons,
            log_content=html.escape(log_content),
            log_type=log_type,
            log_name=current_log['name']
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def stream_logs(self, handler, log_type='app'):
        """Stream logs in real-time using Server-Sent Events"""
        log_file = self.LOG_TYPES.get(log_type, self.LOG_TYPES['app'])['file']
        
        # Set SSE headers
        handler.send_response(200)
        handler.send_header('Content-type', 'text/event-stream')
        handler.send_header('Cache-Control', 'no-cache')
        handler.send_header('Connection', 'keep-alive')
        handler.end_headers()
        
        try:
            if os.path.exists(log_file):
                self._tail_log_file(handler, log_file)
            else:
                self._send_sse_message(handler, f"Log file {log_file} not found")
        except Exception as e:
            self._send_sse_message(handler, f"Error streaming logs: {str(e)}")
    
    def _generate_log_buttons(self, current_log_type):
        """Generate HTML for log type selection buttons"""
        buttons = ""
        for log_type, info in self.LOG_TYPES.items():
            active_class = "button-success" if log_type == current_log_type else ""
            buttons += f'<a href="/logs?type={log_type}" class="button {active_class}">{info["name"]}</a>\n'
        return buttons
    
    def _read_log_file(self, log_file):
        """Read last 100 lines of log file"""
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return ''.join(lines[-100:]) if lines else 'No logs yet'
            else:
                return f"Log file {log_file} not found"
        except Exception as e:
            return f"Error reading log: {str(e)}"
    
    def _tail_log_file(self, handler, log_file):
        """Tail log file and send updates via SSE"""
        process = subprocess.Popen(
            ['tail', '-f', log_file], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        try:
            while True:
                output = process.stdout.readline()
                if output:
                    self._send_sse_message(handler, output.strip())
                else:
                    time.sleep(0.1)
        except Exception:
            # Client disconnected or other error
            pass
        finally:
            process.terminate()
    
    def _send_sse_message(self, handler, message):
        """Send Server-Sent Event message"""
        data = f"data: {html.escape(message)}\n\n"
        handler.wfile.write(data.encode())
        handler.wfile.flush()
