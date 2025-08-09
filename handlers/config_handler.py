"""
Configuration handler for editing backup settings
"""
import yaml
from services.template_service import TemplateService
class ConfigHandler:
    """Handles configuration editing"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
    
    def show_config_editor(self, handler):
        """Show configuration editor with current YAML"""
        # Convert config to YAML text
        try:
            config_text = yaml.dump(
                self.backup_config.config, 
                default_flow_style=False, 
                indent=2
            )
        except Exception as e:
            config_text = f"Error loading configuration: {str(e)}"
        
        # Render template
        html_content = self.template_service.render_template(
            'config_editor.html',
            config_text=config_text
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def save_config_from_form(self, handler, form_data):
        """Save configuration from web form"""
        config_text = form_data.get('config_text', [''])[0]
        
        try:
            # Parse and validate YAML
            new_config = yaml.safe_load(config_text)
            
            if not isinstance(new_config, dict):
                raise ValueError("Configuration must be a valid YAML dictionary")
            
            # Save the new configuration
            self.backup_config.config = new_config
            self.backup_config.save_config()
            
            # Redirect back to config page
            self.template_service.send_redirect(handler, '/config')
            
        except yaml.YAMLError as e:
            self.template_service.send_error_response(
                handler, 
                f"Invalid YAML syntax: {str(e)}"
            )
        except Exception as e:
            self.template_service.send_error_response(
                handler, 
                f"Configuration error: {str(e)}"
            )
