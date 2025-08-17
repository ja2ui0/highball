"""
Consolidated Page Handlers
Merges all page rendering handlers into single module
Replaces: dashboard.py, config_handler.py, inspect_handler.py, logs.py, network.py
"""

import json
import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import models for unified validation and forms
from models.validation import validation_service
from models.forms import job_parser

# Import services
from services.template_service import TemplateService
from services.job_form_data_builder import JobFormDataBuilder
from services.form_data_service import FormDataService

logger = logging.getLogger(__name__)

class PagesHandler:
    """Unified handler for all page rendering operations"""
    
    def __init__(self, backup_config, template_service: TemplateService):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = JobFormDataBuilder()
        self.form_data_service = FormDataService()
    
    # =============================================================================
    # DASHBOARD PAGES
    # =============================================================================
    
    def show_dashboard(self, request_handler):
        """Show main dashboard with job list"""
        try:
            jobs = self.backup_config.get_jobs()
            global_settings = self.backup_config.get_global_settings()
            
            # Get job status information
            from services.job_logger import JobLogger
            job_logger = JobLogger()
            
            job_list = []
            for job_name, job_config in jobs.items():
                status_info = job_logger.get_job_status(job_name)
                
                job_display = {
                    'name': job_name,
                    'config': job_config,
                    'status': status_info.get('status', 'unknown'),
                    'last_run': status_info.get('last_run'),
                    'last_duration': status_info.get('duration'),
                    'enabled': job_config.get('enabled', True),
                    'schedule': job_config.get('schedule', 'manual')
                }
                job_list.append(job_display)
            
            # Sort jobs by name
            job_list.sort(key=lambda j: j['name'])
            
            template_data = {
                'jobs': job_list,
                'global_settings': global_settings,
                'page_title': 'Dashboard'
            }
            
            html = self.template_service.render_template('dashboard.html', template_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self._send_error(request_handler, f"Dashboard error: {str(e)}")
    
    def show_add_job_form(self, request_handler):
        """Show add job form"""
        try:
            form_data = self.job_form_builder.build_empty_form_data()
            html = self.template_service.render_template('job_form.html', form_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Add job form error: {e}")
            self._send_error(request_handler, f"Form error: {str(e)}")
    
    def show_edit_job_form(self, request_handler, job_name: str):
        """Show edit job form"""
        try:
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_error(request_handler, f"Job '{job_name}' not found")
                return
            
            job_config = jobs[job_name]
            form_data = self.job_form_builder.build_form_data_from_job(job_name, job_config)
            html = self.template_service.render_template('job_form.html', form_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Edit job form error: {e}")
            self._send_error(request_handler, f"Form error: {str(e)}")
    
    def save_backup_job(self, request_handler, form_data: Dict[str, Any]):
        """Save backup job from form submission"""
        try:
            # Parse job form data using unified parser
            job_result = job_parser.parse_job_form(form_data)
            
            if not job_result['valid']:
                # Show form with errors
                error_form_data = self.job_form_builder.build_form_data_with_error(
                    form_data, job_result['error']
                )
                html = self.template_service.render_template('job_form.html', error_form_data)
                self._send_html_response(request_handler, html)
                return
            
            # Save job configuration
            job_name = job_result['job_name']
            job_config = {
                'source_type': job_result['source_type'],
                'source_config': job_result['source_config'],
                'dest_type': job_result['dest_type'],
                'dest_config': job_result['dest_config'],
                'schedule': job_result['schedule'],
                'enabled': job_result['enabled'],
                'respect_conflicts': job_result['respect_conflicts'],
                'notifications': job_result['notifications']
            }
            
            # Add maintenance config if present
            if 'maintenance_config' in job_result:
                job_config['maintenance_config'] = job_result['maintenance_config']
            
            # Save to config
            success = self.backup_config.save_job(job_name, job_config)
            
            if success:
                # Redirect to dashboard
                self._send_redirect(request_handler, '/dashboard')
            else:
                error_form_data = self.job_form_builder.build_form_data_with_error(
                    form_data, "Failed to save job configuration"
                )
                html = self.template_service.render_template('job_form.html', error_form_data)
                self._send_html_response(request_handler, html)
                
        except Exception as e:
            logger.error(f"Save job error: {e}")
            error_form_data = self.job_form_builder.build_form_data_with_error(
                form_data, f"Save error: {str(e)}"
            )
            html = self.template_service.render_template('job_form.html', error_form_data)
            self._send_html_response(request_handler, html)
    
    def delete_backup_job(self, request_handler, job_name: str):
        """Delete backup job"""
        try:
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            success = self.backup_config.delete_job(job_name)
            
            if success:
                self._send_redirect(request_handler, '/dashboard')
            else:
                self._send_error(request_handler, f"Failed to delete job '{job_name}'")
                
        except Exception as e:
            logger.error(f"Delete job error: {e}")
            self._send_error(request_handler, f"Delete error: {str(e)}")
    
    # =============================================================================
    # CONFIGURATION PAGES
    # =============================================================================
    
    def show_config_manager(self, request_handler):
        """Show configuration management page"""
        try:
            global_settings = self.backup_config.get_global_settings()
            
            template_data = {
                'global_settings': global_settings,
                'page_title': 'Configuration'
            }
            
            html = self.template_service.render_template('config.html', template_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Config manager error: {e}")
            self._send_error(request_handler, f"Config error: {str(e)}")
    
    def show_raw_editor(self, request_handler):
        """Show raw YAML configuration editor"""
        try:
            config_path = self.backup_config.config_file
            raw_config = ""
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    raw_config = f.read()
            
            template_data = {
                'raw_config': raw_config,
                'config_path': config_path,
                'page_title': 'Raw Configuration Editor'
            }
            
            html = self.template_service.render_template('config_raw.html', template_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Raw editor error: {e}")
            self._send_error(request_handler, f"Editor error: {str(e)}")
    
    def save_structured_config(self, request_handler, form_data: Dict[str, Any]):
        """Save structured configuration from form"""
        try:
            # Parse configuration form data
            # This would need implementation based on config form structure
            self._send_redirect(request_handler, '/config')
            
        except Exception as e:
            logger.error(f"Save config error: {e}")
            self._send_error(request_handler, f"Save error: {str(e)}")
    
    def save_raw_config(self, request_handler, form_data: Dict[str, Any]):
        """Save raw YAML configuration"""
        try:
            raw_config = form_data.get('raw_config', [''])[0]
            
            # Validate YAML syntax
            try:
                yaml.safe_load(raw_config)
            except yaml.YAMLError as e:
                self._send_error(request_handler, f"Invalid YAML: {str(e)}")
                return
            
            # Save to file
            config_path = self.backup_config.config_file
            with open(config_path, 'w') as f:
                f.write(raw_config)
            
            # Reload configuration
            self.backup_config.reload_config()
            
            self._send_redirect(request_handler, '/config')
            
        except Exception as e:
            logger.error(f"Save raw config error: {e}")
            self._send_error(request_handler, f"Save error: {str(e)}")
    
    # =============================================================================
    # INSPECTION PAGES
    # =============================================================================
    
    def show_job_inspect(self, request_handler):
        """Show job inspection page"""
        try:
            # Get job name from query parameters
            from urllib.parse import urlparse, parse_qs
            url_parts = urlparse(request_handler.path)
            params = parse_qs(url_parts.query)
            job_name = params.get('name', [''])[0]
            
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_error(request_handler, f"Job '{job_name}' not found")
                return
            
            job_config = jobs[job_name]
            
            # Get job status and logs
            from services.job_logger import JobLogger
            job_logger = JobLogger()
            status_info = job_logger.get_job_status(job_name)
            recent_logs = job_logger.get_recent_logs(job_name, limit=50)
            
            template_data = {
                'job_name': job_name,
                'job_config': job_config,
                'status_info': status_info,
                'recent_logs': recent_logs,
                'page_title': f'Inspect: {job_name}'
            }
            
            html = self.template_service.render_template('job_inspect.html', template_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Job inspect error: {e}")
            self._send_error(request_handler, f"Inspect error: {str(e)}")
    
    # =============================================================================
    # LOG PAGES
    # =============================================================================
    
    def show_dev_logs(self, request_handler, log_type: str = 'app'):
        """Show development/debug logs page"""
        try:
            logs_data = self._get_system_logs(log_type)
            
            template_data = {
                'log_type': log_type,
                'logs': logs_data,
                'available_types': ['app', 'system', 'job_status', 'validation', 'running_jobs', 'deleted_jobs'],
                'page_title': f'Debug Logs: {log_type}'
            }
            
            html = self.template_service.render_template('dev_logs.html', template_data)
            self._send_html_response(request_handler, html)
            
        except Exception as e:
            logger.error(f"Dev logs error: {e}")
            self._send_error(request_handler, f"Logs error: {str(e)}")
    
    def _get_system_logs(self, log_type: str) -> List[str]:
        """Get system logs by type"""
        try:
            if log_type == 'app':
                # Application logs from docker
                import subprocess
                result = subprocess.run(['docker', 'logs', '--tail', '100', 'highball'], 
                                      capture_output=True, text=True, timeout=10)
                return result.stdout.split('\n') if result.returncode == 0 else ['Log retrieval failed']
            
            elif log_type == 'system':
                # System logs
                log_files = ['/var/log/syslog', '/var/log/messages']
                for log_file in log_files:
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                        return lines[-100:]  # Last 100 lines
                return ['No system logs found']
            
            elif log_type in ['job_status', 'validation', 'running_jobs', 'deleted_jobs']:
                # Highball operational logs
                log_file = f'/var/log/highball/{log_type}.yaml'
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    return [content] if content.strip() else ['Empty log file']
                return ['Log file not found']
            
            else:
                return ['Unknown log type']
                
        except Exception as e:
            logger.error(f"Get logs error: {e}")
            return [f'Error retrieving logs: {str(e)}']
    
    # =============================================================================
    # NETWORK UTILITIES
    # =============================================================================
    
    def scan_network_for_rsyncd(self, request_handler, network_range: str):
        """Scan network for rsyncd services"""
        try:
            # Basic network scanning functionality
            import subprocess
            
            # Use nmap to scan for rsyncd (port 873)
            cmd = ['nmap', '-p', '873', '--open', network_range]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            scan_results = []
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_host = None
                
                for line in lines:
                    line = line.strip()
                    if 'Nmap scan report for' in line:
                        current_host = line.split('for ')[-1]
                    elif '873/tcp open' in line and current_host:
                        scan_results.append({
                            'host': current_host,
                            'port': 873,
                            'service': 'rsyncd'
                        })
            
            template_data = {
                'network_range': network_range,
                'scan_results': scan_results,
                'page_title': 'Network Scan Results'
            }
            
            html = self.template_service.render_template('network_scan.html', template_data)
            self._send_html_response(request_handler, html)
            
        except subprocess.TimeoutExpired:
            self._send_error(request_handler, "Network scan timeout")
        except Exception as e:
            logger.error(f"Network scan error: {e}")
            self._send_error(request_handler, f"Scan error: {str(e)}")
    
    # =============================================================================
    # VALIDATION ENDPOINTS
    # =============================================================================
    
    def validate_ssh_source(self, request_handler, source: str):
        """Validate SSH source configuration"""
        try:
            # Parse source string (format: username@hostname)
            if '@' not in source:
                self._send_json_response(request_handler, {
                    'valid': False,
                    'error': 'Invalid source format. Expected: username@hostname'
                })
                return
            
            username, hostname = source.split('@', 1)
            ssh_config = {'username': username, 'hostname': hostname}
            
            # Use unified validation service
            result = validation_service.validate_ssh_source(ssh_config)
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"SSH validation error: {e}")
            self._send_json_response(request_handler, {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            })
    
    def validate_source_paths(self, request_handler, form_data: Dict[str, Any]):
        """Validate source paths from form"""
        try:
            # Parse source paths from form
            from models.forms import source_paths_parser
            paths_result = source_paths_parser.parse_multi_path_options(form_data)
            
            if not paths_result['valid']:
                self._send_json_response(request_handler, paths_result)
                return
            
            # Validate each path
            source_type = form_data.get('source_type', ['local'])[0]
            validation_results = []
            
            for path_config in paths_result['source_paths']:
                if source_type == 'ssh':
                    hostname = form_data.get('hostname', [''])[0]
                    username = form_data.get('username', [''])[0]
                    ssh_config = {'hostname': hostname, 'username': username}
                    result = validation_service.validate_source_path(ssh_config, path_config['path'])
                else:
                    result = validation_service.validate_source_path({}, path_config['path'])
                
                validation_results.append({
                    'path': path_config['path'],
                    'valid': result['valid'],
                    'error': result.get('error'),
                    'permissions': result.get('permissions')
                })
            
            self._send_json_response(request_handler, {
                'valid': True,
                'results': validation_results
            })
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            self._send_json_response(request_handler, {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            })
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _send_html_response(self, request_handler, html: str):
        """Send HTML response"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        request_handler.wfile.write(html.encode())
    
    def _send_json_response(self, request_handler, data: Dict[str, Any]):
        """Send JSON response"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'application/json')
        request_handler.end_headers()
        request_handler.wfile.write(json.dumps(data).encode())
    
    def _send_redirect(self, request_handler, location: str):
        """Send redirect response"""
        request_handler.send_response(302)
        request_handler.send_header('Location', location)
        request_handler.end_headers()
    
    def _send_error(self, request_handler, message: str, status_code: int = 500):
        """Send error response"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        
        error_html = f"""
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error</h1>
            <p>{message}</p>
            <a href="/dashboard">Return to Dashboard</a>
        </body>
        </html>
        """
        request_handler.wfile.write(error_html.encode())