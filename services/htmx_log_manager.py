"""
HTMX Log Management Service
Handles job log refresh and display operations for inspection pages
"""
import os
import html


class HTMXLogManager:
    """Manages job log operations for HTMX endpoints"""
    
    def __init__(self):
        pass
    
    def refresh_log_content(self, job_name):
        """
        Refresh log content for a specific job
        Returns HTML fragment for log content area
        """
        try:
            log_content = self._read_job_log(job_name)
            return f'<div id="logContent" class="log-viewer">{log_content}</div>'
        except Exception as e:
            error_content = html.escape(f"Error refreshing logs: {str(e)}")
            return f'<div id="logContent" class="log-viewer error-message">{error_content}</div>'
    
    def clear_log_display(self):
        """
        Clear log display (frontend only)
        Returns empty log content area
        """
        return '<div id="logContent" class="log-viewer">(Display cleared - use Refresh to reload)</div>'
    
    def _read_job_log(self, job_name):
        """Read job-specific log file (reused from inspect_handler.py)"""
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