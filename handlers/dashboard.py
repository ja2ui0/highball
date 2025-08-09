"""
Dashboard handler for backup job management
"""

import html
from datetime import datetime

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
        """Save backup job from form data"""
        job_name = form_data.get('job_name', [''])[0].strip()
        if not job_name:
            self.template_service.send_error_response(handler, "Job name is required")
            return
        
        # Parse form data
        includes = self._parse_lines(form_data.get('includes', [''])[0])
        excludes = self._parse_lines(form_data.get('excludes', [''])[0])
        
        job_config = {
            'source': form_data.get('source', [''])[0].strip(),
            'includes': includes,
            'excludes': excludes,
            'schedule': form_data.get('schedule', ['manual'])[0],
            'enabled': 'enabled' in form_data
        }
        
        # Save job
        self.backup_config.add_backup_job(job_name, job_config)
        self.template_service.send_redirect(handler, '/')
    
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
            return '<tr><td colspan="6" style="text-align: center; color: #888;">No backup jobs configured</td></tr>'
        
        rows = ""
        for job_name, job_config in jobs.items():
            status = "enabled" if job_config.get('enabled', True) else "disabled"
            
            # Build history link
            job_log = logs.get(job_name, {})
            if job_log.get('last_run'):
                history_link = f'<a href="/history?job={html.escape(job_name)}" class="history-link">View</a>'
            else:
                history_link = '<span style="color: #888;">None</span>'
            
            # Format source path for better wrapping
            source_path = self._format_source_path(job_config['source'])
            
            rows += f"""
                <tr>
                    <td>{html.escape(job_name)}</td>
                    <td class="source-path">{source_path}</td>
                    <td class="{status}">{status.capitalize()}</td>
                    <td>{html.escape(job_config.get('schedule', 'manual'))}</td>
                    <td>{history_link}</td>
                    <td>
                        <div class="action-buttons">
                            <form method="post" action="/run-backup" style="display: inline;">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Run Now" class="button">
                            </form>
                            <form method="post" action="/dry-run-backup" style="display: inline;">
                                <input type="hidden" name="job_name" value="{html.escape(job_name)}">
                                <input type="submit" value="Dry Run" class="button button-warning">
                            </form>
                            <a href="/edit-job?name={html.escape(job_name)}" class="button">Edit</a>
                        </div>
                    </td>
                </tr>
            """
        return rows
    
    def _build_deleted_job_rows(self, deleted_jobs):
        """Build HTML rows for deleted jobs table"""
        if not deleted_jobs:
            return '<tr><td colspan="5" style="text-align: center; color: #888;">No deleted jobs</td></tr>'
        
        rows = ""
        for job_name, job_config in deleted_jobs.items():
            deleted_at = self._format_timestamp(job_config.get('deleted_at', 'Unknown'))
            source_path = self._format_source_path(job_config['source'])
            
            rows += f"""
                <tr>
                    <td>{html.escape(job_name)}</td>
                    <td class="source-path">{source_path}</td>
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
