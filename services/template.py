"""
Template rendering service
Handles loading and rendering HTML templates with Jinja2 support
"""
import os
import html
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
class TemplateService:
    """Service for loading and rendering HTML templates"""
    
    def __init__(self, backup_config=None):
        self.backup_config = backup_config
        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=True  # Auto-escape HTML for security
        )
    
    def get_theme_css_path(self):
        """Get the CSS path for the current theme"""
        if not self.backup_config:
            return "/static/themes/dark.css"  # default fallback
        
        theme = self.backup_config.config.get('global_settings', {}).get('theme', 'dark')
        theme_path = f"/static/themes/{theme}.css"
        
        # Check if theme file exists, fallback to dark if not
        if not os.path.exists(f"static/themes/{theme}.css"):
            theme_path = "/static/themes/dark.css"
        
        return theme_path
    
    def load_template(self, template_name):
        """Load HTML template from templates directory (enforces pages vs partials separation)"""
        template_path = f"templates/{template_name}"
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return f.read()
        else:
            return self._error_template(template_name, template_path)
    
    def load_page_template(self, page_name):
        """Template concern: load full page template (complete HTML documents)"""
        return self.load_template(f"pages/{page_name}")
    
    def load_partial_template(self, partial_name):
        """Template concern: load HTMX partial template (HTML fragments)"""
        return self.load_template(f"partials/{partial_name}")
    
    def render_template(self, template_name, **kwargs):
        """Render template using Jinja2 with context variables"""
        try:
            # Use Jinja2 to render the template
            template = self.jinja_env.get_template(template_name)
            
            # Automatically add theme CSS path to all templates
            kwargs['theme_css_path'] = self.get_theme_css_path()
            
            # Handle job table rows if jobs data is present
            if 'jobs' in kwargs:
                jobs_html = self._build_job_rows(kwargs['jobs'])
                kwargs['job_rows'] = jobs_html
            
            # Handle deleted job rows if deleted_jobs data is present  
            if 'deleted_jobs' in kwargs:
                deleted_html = self._build_deleted_job_rows(kwargs['deleted_jobs'])
                kwargs['deleted_job_rows'] = deleted_html
            
            # Handle config warning
            kwargs['config_warning'] = ''  # Empty for now
            
            return template.render(**kwargs)
            
        except Exception as e:
            raise Exception(f"Template rendering failed for {template_name}: {str(e)}")
    
    def _build_job_rows(self, jobs):
        """Build job table rows from job data"""
        if not jobs:
            return self.load_template('partials/empty_job_rows.html')
        
        rows = []
        for job in jobs:
            row_html = self.render_template('partials/job_row.html',
                job_name=job['name'],
                source_display=job['source_display'],
                dest_display=job['dest_display'], 
                status_class=job['status_class'],
                status_text=job['status'],
                schedule=job['schedule']
            )
            rows.append(row_html)
        
        return '\n'.join(rows)
    
    def _build_deleted_job_rows(self, deleted_jobs):
        """Build deleted job table rows from deleted jobs data"""
        if not deleted_jobs:
            return self.load_template('partials/empty_deleted_rows.html')
        
        rows = []
        for job_name, job_data in deleted_jobs.items():
            deleted_at = job_data.get('deleted_at', 'Unknown')
            source_path = self._extract_source_path_from_deleted_job(job_data)
            
            row_html = self.render_template('partials/deleted_job_row.html',
                job_name=job_name,
                source_path=source_path,
                deleted_at=deleted_at
            )
            rows.append(row_html)
        
        return '\n'.join(rows)
    
    def _extract_source_path_from_deleted_job(self, job_data):
        """Extract source path from deleted job data"""
        if 'config' not in job_data:
            return 'Unknown'
        
        source_config = job_data['config'].get('source_config', {})
        source_paths = source_config.get('source_paths', [])
        if source_paths:
            return source_paths[0].get('path', 'Unknown')
        else:
            return source_config.get('path', 'Unknown')
    
    def render_validation_status(self, validation_type: str, result: Dict[str, Any]) -> str:
        """Template concern: render validation status using Jinja2 template"""
        # Build details list with SSH connection always first
        details = []
        
        # SSH connection always appears first when present (success or failure)
        if result.get('ssh_status') == 'OK':
            details.append("SSH connection successful")
        
        # Only add type-specific details if SSH connection succeeded
        if result.get('ssh_status') == 'OK':
            if validation_type == 'ssh_source':
                # Show rsync status with version (source validation only)
                rsync_status = result.get('rsync_status', '')
                if rsync_status and rsync_status != 'Not found':
                    details.append(f"Rsync: {rsync_status}")
                elif rsync_status == 'Not found':
                    details.append("Rsync: Not found")
                
                # Show container engine (source validation only)
                podman_status = result.get('podman_status', '')
                docker_status = result.get('docker_status', '')
                
                if podman_status and podman_status != 'Not found':
                    details.append(f"Container Engine: {podman_status}")
                elif docker_status and docker_status != 'Not found':
                    details.append(f"Container Engine: {docker_status}")
                else:
                    details.append("Container Engine: Not found")
            
            elif validation_type == 'ssh_dest':
                # Path validation details (destination validation only)
                if result.get('path_permissions'):
                    permissions = result['path_permissions']
                    if permissions == 'RWX':
                        details.append(f"Path permissions: {permissions} (backup + restore capable)")
                    elif permissions == 'RO':
                        details.append(f"Path permissions: {permissions} (backup only - no restore capability)")
                    else:
                        details.append(f"Path permissions: {permissions}")
                # Removed redundant path_status - the main error message already indicates path issues
        
        # Determine status class and label
        if result.get('valid', False):
            status_class = 'success'
            status_label = '[OK]'
        else:
            status_class = 'error'
            status_label = '[ERROR]'
        
        # Build message from details or error
        if details:
            # Pass details as a list for proper formatting in template
            message = None
        else:
            message = result.get('error', 'Validation failed')
            details = None
        
        # Use Jinja2 template to render the result
        return self.render_template('partials/validation_result.html', 
                                   status_class=status_class,
                                   status_label=status_label,
                                   message=message,
                                   details=details)
    
    
    def _error_template(self, template_name, template_path):
        """Return error template when template not found"""
        available_templates = "Unknown"
        if os.path.exists('templates/'):
            available_templates = str(os.listdir('templates/'))
        
        return f"""
        <html>
        <head><title>Template Error</title></head>
        <body>
            <h1>Template Error</h1>
            <p>Template {template_name} not found at {template_path}</p>
            <p>Available templates: {available_templates}</p>
            <a href="/">Back to Dashboard</a>
        </body>
        </html>
        """
    
    # REMOVED: All HTTP response methods moved to handlers
    # Template service is now pure template rendering only
    # HTTP concerns belong in handler layer, not template service
