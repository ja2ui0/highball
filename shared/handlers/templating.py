"""
Template rendering service
Handles loading and rendering HTML templates with Jinja2 support
"""
import os
from typing import Dict, Any, Optional
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
    
    def get_theme_css_path(self) -> str:
        """Get the CSS path for the current theme - ALWAYS LOADS FROM DISK"""
        if not self.backup_config:
            return "/static/themes/dark.css"  # default fallback
        
        # CRITICAL: Use get_global_settings() which now loads fresh from disk
        global_settings = self.backup_config.get_global_settings()
        theme = global_settings.get('theme', 'dark')
        theme_path = f"/static/themes/{theme}.css"
        
        # Check if theme file exists, fallback to dark if not
        if not os.path.exists(f"static/themes/{theme}.css"):
            theme_path = "/static/themes/dark.css"
        
        return theme_path
    
    def load_template(self, template_name: str) -> str:
        """Load HTML template from templates directory (enforces pages vs partials separation)"""
        template_path = f"templates/{template_name}"
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return f.read()
        else:
            return self._error_template(template_name, template_path)
    
    def load_page_template(self, page_name: str) -> str:
        """Template concern: load full page template (complete HTML documents)"""
        return self.load_template(f"pages/{page_name}")
    
    def load_partial_template(self, partial_name: str) -> str:
        """Template concern: load HTMX partial template (HTML fragments)"""
        return self.load_template(f"partials/{partial_name}")
    
    def render_template(self, template_name: str, **kwargs: Any) -> str:
        """Render template using Jinja2 with context variables"""
        try:
            # Use Jinja2 to render the template
            template = self.jinja_env.get_template(template_name)
            
            # Automatically add theme CSS path to all templates
            kwargs['theme_css_path'] = self.get_theme_css_path()
            
            # Handle config warning
            kwargs['config_warning'] = ''  # Empty for now
            
            return template.render(**kwargs)
            
        except Exception as e:
            raise Exception(f"Template rendering failed for {template_name}: {str(e)}")
    
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
    
