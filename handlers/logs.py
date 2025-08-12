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
    }
    
    def __init__(self, template_service, backup_config=None):
        self.template_service = template_service
        self.backup_config = backup_config
    
    def show_logs(self, handler, log_type='app'):
        """Show logs viewer with live tailing capability"""
        from urllib.parse import urlparse, parse_qs
        
        # Check if this is a job log request
        url_parts = urlparse(handler.path)
        params = parse_qs(url_parts.query)
        # If system=1 is present, force system logs (ignore job parameter)
        force_system = params.get('system', [''])[0] == '1'
        job_name = '' if force_system else params.get('job', [''])[0]
        
        if job_name:
            # Show job-specific log
            log_file = f'/var/log/highball/jobs/{job_name}.log'
            log_name = f'Job: {job_name}'
            log_content = self._read_log_file(log_file)
            log_buttons = f'<a href="/logs?system=1" class="button">Back to System Logs</a>'
            # Set log_type for JavaScript streaming detection
            template_log_type = f'job:{job_name}'
        else:
            # Show system logs
            # Validate log type
            if log_type not in self.LOG_TYPES:
                log_type = 'app'
            
            current_log = self.LOG_TYPES[log_type]
            log_name = current_log['name']
            log_content = self._read_log_file(current_log['file'])
            log_buttons = self._generate_log_buttons(log_type)
            template_log_type = log_type
        
        # Generate job dropdown
        job_dropdown = self._generate_job_dropdown(job_name)
        
        # Render template
        html_content = self.template_service.render_template(
            'logs.html',
            log_buttons=log_buttons,
            log_content=log_content,  # Remove double escaping
            log_type=template_log_type,  # Use correct log_type for JavaScript
            log_name=log_name,
            job_dropdown=job_dropdown
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def stream_logs(self, handler, log_type='app'):
        """Stream logs in real-time using Server-Sent Events"""
        # Set SSE headers
        handler.send_response(200)
        handler.send_header('Content-type', 'text/event-stream')
        handler.send_header('Cache-Control', 'no-cache')
        handler.send_header('Connection', 'keep-alive')
        handler.send_header('X-Accel-Buffering', 'no')  # Tell nginx not to buffer
        handler.end_headers()
        
        # Send a simple test message and close
        message = f"data: TEST: Streaming works for {log_type}\n\n"
        handler.wfile.write(message.encode())
        handler.wfile.flush()
    
    def _generate_log_buttons(self, current_log_type):
        """Generate HTML for log type selection buttons"""
        buttons = ""
        for log_type, info in self.LOG_TYPES.items():
            active_class = "button-success" if log_type == current_log_type else ""
            buttons += f'<a href="/logs?type={log_type}" class="button {active_class}">{info["name"]}</a>\n'
        return buttons
    
    def _generate_job_dropdown(self, selected_job=None):
        """Generate HTML for job log selection dropdown"""
        if not self.backup_config:
            return '<option value="">No jobs configured</option>'
        
        jobs = self.backup_config.config.get('backup_jobs', {})
        if not jobs:
            return '<option value="">No jobs configured</option>'
        
        options = '<option value="">Select a job...</option>\n'
        for job_name in sorted(jobs.keys()):
            selected = 'selected' if job_name == selected_job else ''
            options += f'<option value="{html.escape(job_name)}" {selected}>{html.escape(job_name)}</option>\n'
        
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
    
    def _tail_log_file(self, handler, log_file):
        """Tail log file and send updates via SSE"""
        try:
            # Send a few recent lines first
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-5:] if len(lines) > 5 else lines
                for line in recent_lines:
                    self._send_sse_message(handler, line.strip())
        except Exception as e:
            self._send_sse_message(handler, f"ERROR: Could not read log file - {str(e)}")
            return
        
        # Start streaming new lines
        self._send_sse_message(handler, "--- Live tail started ---")
        
        process = None
        try:
            process = subprocess.Popen(
                ['tail', '-f', log_file], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=0  # Unbuffered
            )
            
            while True:
                output = process.stdout.readline()
                if output:
                    self._send_sse_message(handler, output.strip())
                elif process.poll() is not None:
                    # Process ended
                    self._send_sse_message(handler, "ERROR: Tail process ended")
                    break
                else:
                    # No output, small sleep to prevent busy loop
                    time.sleep(0.1)
                    
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected - normal for streaming
            pass
        except Exception as e:
            try:
                self._send_sse_message(handler, f"ERROR: Tail failed - {str(e)}")
            except:
                pass
        finally:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except:
                    process.kill()
    
    def _send_sse_message(self, handler, message):
        """Send Server-Sent Event message"""
        try:
            data = f"data: {html.escape(message)}\n\n"
            handler.wfile.write(data.encode())
            handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected - re-raise so caller can handle
            raise
        except Exception as e:
            # Other write errors - re-raise with context
            raise ConnectionError(f"Failed to send message: {str(e)}")