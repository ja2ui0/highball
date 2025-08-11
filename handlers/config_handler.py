"""
Configuration handler for editing backup settings
"""
import yaml
from datetime import datetime
from services.template_service import TemplateService

class ConfigHandler:
    """Handles configuration editing"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
    
    def show_config_manager(self, handler):
        """Show structured configuration form"""
        global_settings = self.backup_config.config.get('global_settings', {})
        notification_config = global_settings.get('notification', {})
        
        # Extract current values for form population
        default_schedule_times = global_settings.get('default_schedule_times', {})
        telegram_config = notification_config.get('telegram', {})
        email_config = notification_config.get('email', {})
        
        # Render structured config manager
        html_content = self.template_service.render_template(
            'config_manager.html',
            # Global settings (uppercase to match template)
            SCHEDULER_TIMEZONE=global_settings.get('scheduler_timezone', 'UTC'),
            ENABLE_CONFLICT_AVOIDANCE='checked' if global_settings.get('enable_conflict_avoidance', True) else '',
            CONFLICT_CHECK_INTERVAL=str(global_settings.get('conflict_check_interval', 300)),
            DELAY_NOTIFICATION_THRESHOLD=str(global_settings.get('delay_notification_threshold', 300)),
            
            # Schedule defaults
            HOURLY_DEFAULT=default_schedule_times.get('hourly', '0 * * * *'),
            DAILY_DEFAULT=default_schedule_times.get('daily', '0 3 * * *'), 
            WEEKLY_DEFAULT=default_schedule_times.get('weekly', '0 3 * * 0'),
            
            # Telegram settings
            TELEGRAM_TOKEN=telegram_config.get('token', ''),
            TELEGRAM_CHAT_ID=telegram_config.get('chat_id', ''),
            
            # Email settings
            EMAIL_SMTP_SERVER=email_config.get('smtp_server', ''),
            EMAIL_SMTP_PORT=str(email_config.get('smtp_port', 587)),
            EMAIL_USE_TLS='checked' if email_config.get('use_tls', True) else '',
            EMAIL_USE_SSL='checked' if email_config.get('use_ssl', False) else '',
            EMAIL_FROM=email_config.get('from_email', ''),
            EMAIL_TO=email_config.get('to_email', ''),
            EMAIL_USERNAME=email_config.get('username', ''),
            EMAIL_PASSWORD=email_config.get('password', ''),
            
            # Notification settings
            NOTIFY_ON_SUCCESS='checked' if notification_config.get('notify_on_success', False) else ''
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def show_raw_editor(self, handler):
        """Show raw YAML configuration editor"""
        # Convert config to YAML text
        try:
            config_text = yaml.dump(
                self.backup_config.config, 
                default_flow_style=False, 
                indent=2
            )
        except Exception as e:
            config_text = f"Error loading configuration: {str(e)}"
        
        # Render raw config editor
        html_content = self.template_service.render_template(
            'config_editor.html',
            config_text=config_text
        )
        
        self.template_service.send_html_response(handler, html_content)
    
    def save_structured_config(self, handler, form_data):
        """Save configuration from structured form fields"""
        try:
            # Update global settings
            global_settings = self.backup_config.config.setdefault('global_settings', {})
            
            # Basic settings
            global_settings['scheduler_timezone'] = form_data.get('scheduler_timezone', ['UTC'])[0]
            global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
            global_settings['conflict_check_interval'] = int(form_data.get('conflict_check_interval', ['300'])[0])
            global_settings['delay_notification_threshold'] = int(form_data.get('delay_notification_threshold', ['300'])[0])
            
            # Default schedule times
            default_schedule_times = global_settings.setdefault('default_schedule_times', {})
            default_schedule_times['hourly'] = form_data.get('hourly_default', ['0 * * * *'])[0]
            default_schedule_times['daily'] = form_data.get('daily_default', ['0 3 * * *'])[0]
            default_schedule_times['weekly'] = form_data.get('weekly_default', ['0 3 * * 0'])[0]
            
            # Notification settings
            notification_config = global_settings.setdefault('notification', {})
            notification_config['notify_on_success'] = 'notify_on_success' in form_data
            
            # Telegram settings
            telegram_config = notification_config.setdefault('telegram', {})
            telegram_config['token'] = form_data.get('telegram_token', [''])[0]
            telegram_config['chat_id'] = form_data.get('telegram_chat_id', [''])[0]
            
            # Email settings
            email_config = notification_config.setdefault('email', {})
            email_config['smtp_server'] = form_data.get('email_smtp_server', [''])[0]
            email_config['smtp_port'] = int(form_data.get('email_smtp_port', ['587'])[0])
            email_config['use_tls'] = 'email_use_tls' in form_data
            email_config['use_ssl'] = 'email_use_ssl' in form_data
            email_config['from_email'] = form_data.get('email_from', [''])[0]
            email_config['to_email'] = form_data.get('email_to', [''])[0]
            email_config['username'] = form_data.get('email_username', [''])[0]
            email_config['password'] = form_data.get('email_password', [''])[0]
            
            # Save configuration
            self.backup_config.save_config()
            
            # Redirect back to config page
            self.template_service.send_redirect(handler, '/config')
            
        except Exception as e:
            self.template_service.send_error_response(
                handler, 
                f"Configuration update error: {str(e)}"
            )
    
    def save_raw_config(self, handler, form_data):
        """Save configuration from raw YAML"""
        config_text = form_data.get('config_text', [''])[0]
        
        try:
            # Parse and validate YAML
            new_config = yaml.safe_load(config_text)
            
            if not isinstance(new_config, dict):
                raise ValueError("Configuration must be a valid YAML dictionary")
            
            # Save the new configuration
            self.backup_config.config = new_config
            self.backup_config.save_config()
            
            # Redirect back to raw config page
            self.template_service.send_redirect(handler, '/config/raw')
            
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

    def reload_config(self, handler):
        """Reload configuration from file"""
        try:
            self.backup_config.config = self.backup_config.load_config()
            self.template_service.send_redirect(handler, '/config')
        except Exception as e:
            self.template_service.send_error_response(
                handler,
                f"Failed to reload config: {str(e)}"
            )

    def download_config_backup(self, handler):
        """Download configuration backup"""
        try:
            config_text = yaml.dump(
                self.backup_config.config, 
                default_flow_style=False, 
                indent=2
            )
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backup_config_{timestamp}.yaml"
            
            handler.send_response(200)
            handler.send_header('Content-Type', 'application/x-yaml')
            handler.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            handler.end_headers()
            handler.wfile.write(config_text.encode())
            
        except Exception as e:
            self.template_service.send_error_response(
                handler,
                f"Failed to backup config: {str(e)}"
            )
