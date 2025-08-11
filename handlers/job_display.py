"""
Job display formatting
Handles HTML generation for job tables and display elements
"""
import html
from datetime import datetime

class JobDisplay:
    """Formats job data for HTML display"""
    
    @staticmethod
    def build_job_rows(jobs, logs):
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
            source_display = JobDisplay.format_source_display(job_config)
            dest_display = JobDisplay.format_destination_display(job_config)
            
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
    
    @staticmethod
    def build_deleted_job_rows(deleted_jobs, job_manager):
        """Build HTML rows for deleted jobs table"""
        if not deleted_jobs:
            return '<tr><td colspan="5" style="text-align: center; color: #888;">No deleted jobs</td></tr>'
        
        rows = ""
        for job_name, job_config in deleted_jobs.items():
            # Get deletion time from job manager logs
            deletion_time = job_manager.get_job_deletion_time(job_name)
            deleted_at = JobDisplay.format_timestamp(deletion_time) if deletion_time else 'Unknown'
            
            # Handle both new and legacy job structures
            if 'source_type' in job_config:
                source_display = JobDisplay.format_source_display(job_config)
            else:
                # Legacy format
                source_path = job_config.get('source', 'Unknown')
                source_display = JobDisplay.format_source_path(source_path)
            
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
    
    @staticmethod
    def build_edit_form_data(job_config):
        """Build data for edit form display"""
        # Assume new job structure (greenfield)
        source_type = job_config.get('source_type', 'unknown')
        dest_type = job_config.get('dest_type', 'unknown')
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        
        # Build hidden fields for source/dest config
        hidden_fields = JobDisplay._build_hidden_config_fields(source_type, source_config, dest_type, dest_config)
        
        # Build display strings (remove HTML tags for plain text display)
        source_display = JobDisplay.format_source_display(job_config)
        dest_display = JobDisplay.format_destination_display(job_config)
        
        # Clean up HTML for display
        source_display = source_display.replace('<span class="source-type">', '').replace('</span>', '').replace('<br>', ' ').replace('/<wbr>', '/')
        dest_display = dest_display.replace('<span class="dest-type">', '').replace('</span>', '').replace('<br>', ' ').replace('/<wbr>', '/')
        
        return {
            'source_type': source_type,
            'dest_type': dest_type,
            'source_display': source_display,
            'dest_display': dest_display,
            'hidden_config_fields': hidden_fields
        }
    
    @staticmethod
    def _build_hidden_config_fields(source_type, source_config, dest_type, dest_config):
        """Build hidden form fields for source/dest configuration"""
        fields = []
        
        # Source config hidden fields
        for key, value in source_config.items():
            field_name = f"source_{source_type}_{key}"
            fields.append(f'<input type="hidden" name="{html.escape(field_name)}" value="{html.escape(str(value))}">')
        
        # Dest config hidden fields  
        for key, value in dest_config.items():
            field_name = f"dest_{dest_type}_{key}"
            fields.append(f'<input type="hidden" name="{html.escape(field_name)}" value="{html.escape(str(value))}">')
        
        return '\n'.join(fields)
    
    @staticmethod
    def format_source_display(job_config):
        """Format source for display in dashboard"""
        if 'source_type' in job_config:
            source_type = job_config['source_type']
            source_config = job_config.get('source_config', {})
            
            if source_type == 'local':
                path = source_config.get('path', 'Unknown')
                return f'<span class="source-type">Local:</span><br>{JobDisplay.format_source_path(path)}'
            elif source_type == 'ssh':
                hostname = source_config.get('hostname', 'unknown')
                username = source_config.get('username', 'unknown')
                path = source_config.get('path', 'unknown')
                return f'<span class="source-type">SSH:</span><br>{JobDisplay.format_source_path(f"{username}@{hostname}:{path}")}'
        
        # Fall back to legacy format
        source = job_config.get('source', 'Unknown')
        return JobDisplay.format_source_path(source)
    
    @staticmethod
    def format_destination_display(job_config):
        """Format destination for display in dashboard"""
        if 'dest_type' in job_config:
            dest_type = job_config['dest_type']
            dest_config = job_config.get('dest_config', {})
            
            if dest_type == 'local':
                path = dest_config.get('path', 'Unknown')
                return f'<span class="dest-type">Local:</span><br>{JobDisplay.format_source_path(path)}'
            elif dest_type == 'ssh':
                hostname = dest_config.get('hostname', 'unknown')
                username = dest_config.get('username', 'unknown')
                path = dest_config.get('path', 'unknown')
                return f'<span class="dest-type">SSH:</span><br>{JobDisplay.format_source_path(f"{username}@{hostname}:{path}")}'
            elif dest_type == 'rsyncd':
                hostname = dest_config.get('hostname', 'unknown')
                share = dest_config.get('share', 'unknown')
                return f'<span class="dest-type">rsyncd:</span><br>{JobDisplay.format_source_path(f"rsync://{hostname}/{share}")}'
        
        # Fall back to legacy format - assume rsyncd to configured host
        return f'<span class="dest-type">rsyncd:</span><br>Default destination'
    
    @staticmethod
    def format_source_path(path):
        """Format source path for better display and wrapping"""
        # Escape HTML first
        escaped_path = html.escape(path)
        
        # Add word break opportunities after slashes for better wrapping
        formatted_path = escaped_path.replace('/', '/<wbr>')
        
        return formatted_path
    
    @staticmethod
    def format_timestamp(timestamp):
        """Format timestamp for compact display"""
        if timestamp == 'Unknown' or not timestamp:
            return 'Unknown'
        
        try:
            # Parse ISO timestamp and format more compactly
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return f'<span class="deleted-timestamp">{dt.strftime("%Y-%m-%d<br>%H:%M:%S")}</span>'
        except Exception:
            return f'<span class="deleted-timestamp">{html.escape(str(timestamp))}</span>'
