"""
Template rendering service
Handles loading and rendering HTML templates
"""

import os
import html

class TemplateService:
    """Service for loading and rendering HTML templates"""
    
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
        
        # Replace all placeholders
        for key, value in kwargs.items():
            placeholder = f"{{{{{key.upper()}}}}}"
            template = template.replace(placeholder, str(value))
        
        return template
    
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
    def send_json_response(handler, data):
        """Send JSON response"""
        import json
        handler.send_response(200)
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
