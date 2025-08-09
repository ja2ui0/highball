"""
Dashboard handler for backup job management
"""
import html
from datetime import datetime
from services.ssh_validator import SSHValidator

class DashboardHandler:
    """Handles dashboard and backup job CRUD operations"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
    
    def show_dashboard(self, handler):
        """Show the main dashboard with active and deleted jobs"""
        # Get data
        jobs = self.backup_config.get_backup_jobs()
        logs = self.backup_config.config.get('backup_logs', {})
        deleted_jobs = self.backup_config.config.get('deleted_jobs', {})
        
        # Build active jobs table
        job_rows = self._build_job_rows(jobs, logs)
        
        # Build deleted jobs table  
        deleted_rows = self._build_deleted_job_rows(deleted_jobs)
        
        # Render template
        html_content = self.template_service.render_template(
            'dashboard.html',
            job_rows=job_rows,
            deleted_rows=deleted_rows
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def show_add_job_form(self, handler):
        """Show form to add new backup job"""
        template = self.template_service.load_template('add_job.html')
        self.template_service.send_html_response(handler, template)
    
    def show_edit_job_form(self, handler, job_name):
        """Show form to edit existing backup job"""
        if not job_name or job_name not in self.backup_config.get_backup_jobs():
            self.template_service.send_error_response(handler, f"Job '{job_name}' not found")
            return
        
        job_config = self.backup_config.get_backup_job(job_name)
        
        # Render edit form with job data
        html_content = self.template_service.render_template(
            'edit_job.html',
            job_name=html.escape(job_name),
            source=html.escape(job_config['source']),
            includes='\n'.join(job_config.get('includes', [])),
            excludes='\n'.join(job_config.get('excludes', [])),
            schedule=job_config.get('schedule', 'manual'),
            enabled_checked='checked' if job_config.get('enabled', True) else ''
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def save_backup_job(self, handler, form_data):
        """Save backup job from new form data structure"""
        job_name = form_data.get('job_name', [''])[0].strip()
        if not job_name:
            self.template_service.send_error_response(handler, "Job name is required")
            return

        # Parse source configuration
        source_type = form_data.get('source_type', [''])[0]
        if not source_type:
            self.template_service.send_error_response(handler, "Source type is required")
            return

        source_config = self._parse_source_config(form_data, source_type)
        if not source_config['valid']:
            self.template_service.send_error_response(handler, source_config['error'])
            return

        # Parse destination configuration
        dest_type = form_data.get('dest_type', [''])[0]
        if not dest_type:
            self.template_service.send_error_response(handler, "Destination type is required")
            return

        dest_config = self._parse_destination_config(form_data, dest_type)
        if not dest_config['valid']:
            self.template_service.send_error_response(handler, dest_config['error'])
            return

        # Validate SSH connections if needed
        if source_type == 'ssh':
            validation_result = SSHValidator.validate_ssh_source(source_config['source_string'])
            if not validation_result['success']:
                error_msg = f"Source SSH Validation Failed: {validation_result['message']}"
                self.template_service.send_error_response(handler, error_msg)
                return

        if dest_type == 'ssh':
            validation_result = SSHValidator.validate_ssh_source(dest_config['dest_string'])
            if not validation_result['success']:
                error_msg = f"Destination SSH Validation Failed: {validation_result['message']}"
                self.template_service.send_error_response(handler, error_msg)
                return

        # Parse form data
        includes = self._parse_lines(form_data.get('includes', [''])[0])
        excludes = self._parse_lines(form_data.get('excludes', [''])[0])

        job_config = {
            'source_type': source_type,
            'source_config': source_config,
            'dest_type': dest_type,
            'dest_config': dest_config,
            'includes': includes,
            'excludes': excludes,
            'schedule': form_data.get('schedule', ['manual'])[0],
            'enabled': 'enabled' in form_data,
            # Keep legacy source field for backward compatibility
            'source': source_config['source_string']
        }

        # Add SSH validation timestamps
        if source_type == 'ssh':
            job_config['source_ssh_validated_at'] = datetime.now().isoformat()
        if dest_type == 'ssh':
            job_config['dest_ssh_validated_at'] = datetime.now().isoformat()

        # Save job
        self.backup_config.add_backup_job(job_name, job_config)
        self.template_service.send_redirect(handler, '/')

    def _parse_source_config(self, form_data, source_type):
        """Parse source configuration from form data"""
        if source_type == 'local':
            path = form_data.get('source_local_path', [''])[0].strip()
            if not path:
                return {'valid': False, 'error': 'Local source path is required'}
            return {
                'valid': True,
                'source_string': path,
                'path': path
            }
        
        elif source_type == 'ssh':
            hostname = form_data.get('source_ssh_hostname', [''])[0].strip()
            username = form_data.get('source_ssh_username', [''])[0].strip()
            path = form_data.get('source_ssh_path', [''])[0].strip()
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'SSH source requires hostname, username, and path'}
            
            source_string = f"{username}@{hostname}:{path}"
            return {
                'valid': True,
                'source_string': source_string,
                'hostname': hostname,
                'username': username,
                'path': path
            }
        
        return {'valid': False, 'error': f'Unknown source type: {source_type}'}

    def _parse_destination_config(self, form_data, dest_type):
        """Parse destination configuration from form data"""
        if dest_type == 'local':
            path = form_data.get('dest_local_path', [''])[0].strip()
            if not path:
                return {'valid': False, 'error': 'Local destination path is required'}
            return {
                'valid': True,
                'dest_string': path,
                'path': path
            }
        
        elif dest_type == 'ssh':
            hostname = form_data.get('dest_ssh_hostname', [''])[0].strip()
            username = form_data.get('dest_ssh_username', [''])[0].strip()
            path = form_data.get('dest_ssh_path', [''])[0].strip()
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'SSH destination requires hostname, username, and path'}
            
            dest_string = f"{username}@{hostname}:{path}"
            return {
                'valid': True,
                'dest_string': dest_string,
                'hostname': hostname,
                'username': username,
                'path': path
            }
        
        elif dest_type == 'rsyncd':
            hostname = form_data.get('dest_rsyncd_hostname', [''])[0].strip()
            share = form_data.get('dest_rsyncd_share', [''])[0].strip()
            
            if not all([hostname, share]):
                return {'valid': False, 'error': 'rsyncd destination requires hostname and share'}
            
            dest_string = f"rsync://{hostname}/{share}"
            return {
                'valid': True,
                'dest_string': dest_string,
                'hostname': hostname,
                'share': share
            }
        
        return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}

    def validate_ssh_source(self, handler, source):
        """AJAX endpoint to validate SSH source"""
        if not source:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'No source provided'
            })
            return
        
        if not self._is_ssh_source(source):
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'Not an SSH source format'
            })
            return
        
        # Perform validation
        result = SSHValidator.validate_ssh_source(source)
        self.template_service.send_json_response(handler, result)

    def validate_rsyncd_destination(self, handler, hostname, share):
        """Validate rsyncd destination"""
        if not hostname or not share:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'Hostname and share name are required'
            })
            return

        try:
            # Test if rsync daemon is accessible and share exists
            import subprocess
            cmd = ['rsync', '--list-only', f'rsync://{hostname}/{share}/']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.template_service.send_json_response(handler, {
                    'success': True,
                    'message': f'rsync daemon on {hostname} is accessible and share "{share}" exists'
                })
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'unknown module' in error_msg.lower():
                    error_msg = f'Share "{share}" not found on {hostname}'
                elif 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {hostname}:873'
                
                self.template_service.send_json_response(handler, {
                    'success': False,
                    'message': error_msg
                })
        
        except subprocess.TimeoutExpired:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': 'Connection timeout - rsync daemon not responding'
            })
        except Exception as e:
            self.template_service.send_json_response(handler, {
                'success': False,
                'message': f'Validation error: {str(e)}'
            })
    
    def _is_ssh_source(self, source):
        """Check if source is SSH format (user@host:/path)"""
        import re
        return bool(re.match(r'^[^@]+@[^:]+:.+', source))
    
    def delete_backup_job(self, handler, job_name):
        """Move backup job to deleted_jobs section"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name in jobs:
            # Move to deleted section with timestamp
            job_config = jobs[job_name].copy()
            job_config['deleted_at'] = datetime.now().isoformat()
            
            # Create deleted_jobs section if needed
            if 'deleted_jobs' not in self.backup_config.config:
                self.backup_config.config['deleted_jobs'] = {}
            
            # Move job
            self.backup_config.config['deleted_jobs'][job_name] = job_config
            del self.backup_config.config['backup_jobs'][job_name]
            self.backup_config.save_config()
        
        self.template_service.send_redirect(handler, '/')
    
    def restore_backup_job(self, handler, job_name):
        """Restore job from deleted_jobs back to active jobs"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        deleted_jobs = self.backup_config.config.get('deleted_jobs', {})
        if job_name in deleted_jobs:
            # Remove deletion timestamp and restore
            job_config = deleted_jobs[job_name].copy()
            job_config.pop('deleted_at', None)
            
            self.backup_config.config['backup_jobs'][job_name] = job_config
            del self.backup_config.config['deleted_jobs'][job_name]
            self.backup_config.save_config()
        
        self.template_service.send_redirect(handler, '/')
    
    def purge_backup_job(self, handler, job_name):
        """Permanently delete job from deleted_jobs"""
        if not job_name:
            self.template_service.send_redirect(handler, '/')
            return
        
        deleted_jobs = self.backup_config.config.get('deleted_jobs', {})
        if job_name in deleted_jobs:
            del self.backup_config.config['deleted_jobs'][job_name]
            
            # Also remove logs
            backup_logs = self.backup_config.config.get('backup_logs', {})
            if job_name in backup_logs:
                del self.backup_config.config['backup_logs'][job_name]
            
            self.backup_config.save_config()
        
        self.template_service.send_redirect(handler, '/')
    
    def _build_job_rows(self, jobs, logs):
        """Build HTML rows for active jobs table"""
        if not jobs:
            return '<tr><td colspan="7" style="text-align: center; color: #888;">No backup jobs configured</td></tr>'
        
        rows = ""
        for job_name, job_config in jobs.items():
            status = "enabled" if job_config.get('enabled', True) else "disabled"
            
            # Build history link
            job_log = logs.get(job_name, {})
            if job_log.get('last_run'):
                history_link = f'<a href="/history?job={html.escape(job_name)}" class="history-link">View</a>'
            else:
                history_link = '<span style="color: #888;">None</span>'
            
            # Format source and destination paths for display
            source_display = self._format_source_display(job_config)
            dest_display = self._format_destination_display(job_config)
            
            rows += f"""
                <tr>
                    <td>{html.escape(job_name)}</td>
                    <td class="source-path">{source_display}</td>
                    <td class="source-path">{dest_display}</td>
                    <td class="{status}">{status.capitalize()}</td>
                    <td>{html.escape(job_config.get('schedule', 'manual'))}</td>
                    <td>{history_link}</td>
                    <td>
                        <div class="action-buttons">
                            <form method="post" action="/run-backup" style="display: inline;">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Run" class="button">
                            </form>
                            <form method="post" action="/dry-run-backup" style="display: inline;">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Test" class="button button-warning">
                            </form>
                            <a href="/edit-job?name={html.escape(job_name)}" class="button">Edit</a>
                        </div>
                    </td>
                </tr>
            """
        return rows

    def _format_source_display(self, job_config):
        """Format source for display in dashboard"""
        if 'source_type' in job_config:
            source_type = job_config['source_type']
            source_config = job_config.get('source_config', {})
            
            if source_type == 'local':
                path = source_config.get('path', 'Unknown')
                return f'<span class="source-type">Local:</span><br>{self._format_source_path(path)}'
            elif source_type == 'ssh':
                hostname = source_config.get('hostname', 'unknown')
                username = source_config.get('username', 'unknown')
                path = source_config.get('path', 'unknown')
                return f'<span class="source-type">SSH:</span><br>{self._format_source_path(f"{username}@{hostname}:{path}")}'
        
        # Fall back to legacy format
        source = job_config.get('source', 'Unknown')
        return self._format_source_path(source)

    def _format_destination_display(self, job_config):
        """Format destination for display in dashboard"""
        if 'dest_type' in job_config:
            dest_type = job_config['dest_type']
            dest_config = job_config.get('dest_config', {})
            
            if dest_type == 'local':
                path = dest_config.get('path', 'Unknown')
                return f'<span class="dest-type">Local:</span><br>{self._format_source_path(path)}'
            elif dest_type == 'ssh':
                hostname = dest_config.get('hostname', 'unknown')
                username = dest_config.get('username', 'unknown')
                path = dest_config.get('path', 'unknown')
                return f'<span class="dest-type">SSH:</span><br>{self._format_source_path(f"{username}@{hostname}:{path}")}'
            elif dest_type == 'rsyncd':
                hostname = dest_config.get('hostname', 'unknown')
                share = dest_config.get('share', 'unknown')
                return f'<span class="dest-type">rsyncd:</span><br>{self._format_source_path(f"rsync://{hostname}/{share}")}'
        
        # Fall back to legacy format - assume rsyncd to configured host
        return f'<span class="dest-type">rsyncd:</span><br>Default destination'

    def _build_deleted_job_rows(self, deleted_jobs):
        """Build HTML rows for deleted jobs table"""
        if not deleted_jobs:
            return '<tr><td colspan="5" style="text-align: center; color: #888;">No deleted jobs</td></tr>'
        
        rows = ""
        for job_name, job_config in deleted_jobs.items():
            deleted_at = self._format_timestamp(job_config.get('deleted_at', 'Unknown'))
            
            # Handle both new and legacy job structures
            if 'source_type' in job_config:
                source_display = self._format_source_display(job_config)
            else:
                # Legacy format
                source_path = job_config.get('source', 'Unknown')
                source_display = self._format_source_path(source_path)
            
            rows += f"""
                <tr>
                    <td>{html.escape(job_name)}</td>
                    <td class="source-path">{source_display}</td>
                    <td style="color: #dc3545;">Deleted</td>
                    <td>{deleted_at}</td>
                    <td>
                        <div class="action-buttons">
                            <form method="post" action="/restore-job" style="display: inline;">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Restore" class="button button-success">
                            </form>
                            <form method="post" action="/purge-job" style="display: inline;" onsubmit="return confirm('Permanently delete this job? This cannot be undone.')">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Purge" class="button button-danger">
                            </form>
                        </div>
                    </td>
                </tr>
            """
        return rows
    
    def _format_source_path(self, path):
        """Format source path for better display and wrapping"""
        # Escape HTML first
        escaped_path = html.escape(path)
        
        # Add word break opportunities after slashes for better wrapping
        formatted_path = escaped_path.replace('/', '/<wbr>')
        
        return formatted_path
    
    def _format_timestamp(self, timestamp):
        """Format timestamp for compact display"""
        if timestamp == 'Unknown' or not timestamp:
            return 'Unknown'
        
        try:
            # Parse ISO timestamp and format more compactly
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return f'<span class="deleted-timestamp">{dt.strftime("%Y-%m-%d<br>%H:%M:%S")}</span>'
        except Exception:
            return f'<span class="deleted-timestamp">{html.escape(str(timestamp))}</span>'
    
    @staticmethod
    def _parse_lines(text):
        """Parse textarea input into list of non-empty lines"""
        return [line.strip() for line in text.split('\n') if line.strip()]
