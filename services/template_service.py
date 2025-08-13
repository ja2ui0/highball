"""
Template rendering service
Handles loading and rendering HTML templates
"""
import os
import html
class TemplateService:
    """Service for loading and rendering HTML templates"""
    
    def __init__(self, backup_config=None):
        self.backup_config = backup_config
    
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
        """Load HTML template from templates directory"""
        template_path = f"templates/{template_name}"
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return f.read()
        else:
            return self._error_template(template_name, template_path)
    
    def render_template(self, template_name, **kwargs):
        """Load template and replace placeholders with values"""
        template = self.load_template(template_name)
        
        # Process includes first (before variable substitution)
        template = self._process_includes(template)
        
        # Automatically add theme CSS path to all templates
        kwargs['theme_css_path'] = self.get_theme_css_path()
        
        # Replace all placeholders
        for key, value in kwargs.items():
            placeholder = f"{{{{{key.upper()}}}}}"
            template = template.replace(placeholder, str(value))
        
        return template
    
    def _process_includes(self, template):
        """Process {{INCLUDE:template_name}} directives"""
        import re
        
        # Find all include directives like {{INCLUDE:job_form_source.html}}
        include_pattern = r'\{\{INCLUDE:([^}]+)\}\}'
        
        def replace_include(match):
            include_name = match.group(1)
            try:
                return self.load_template(include_name)
            except:
                return f"<!-- Error: Could not load {include_name} -->"
        
        return re.sub(include_pattern, replace_include, template)
    
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
    
    @staticmethod
    def send_html_response(handler, html_content):
        """Send HTML response through request handler"""
        handler.send_response(200)
        handler.send_header('Content-type', 'text/html')
        handler.end_headers()
        handler.wfile.write(html_content.encode())
    
    @staticmethod
    def send_redirect(handler, location):
        """Send redirect response"""
        handler.send_response(302)
        handler.send_header('Location', location)
        handler.end_headers()
    
    @staticmethod
    def send_json_response(handler, data, status_code=200):
        """Send JSON response"""
        import json
        handler.send_response(status_code)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps(data).encode())
    
    @staticmethod
    def send_error_response(handler, message, status_code=400):
        """Send error response"""
        html_content = f"""
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error</h1>
            <p>{html.escape(message)}</p>
            <a href="/">Back to Dashboard</a>
        </body>
        </html>
        """
        handler.send_response(status_code)
        handler.send_header('Content-type', 'text/html')
        handler.end_headers()
        handler.wfile.write(html_content.encode())
