"""
Configuration handler for editing backup settings
"""
import os
import yaml
from datetime import datetime
from services.template_service import TemplateService

class ConfigHandler:
    """Handles configuration editing"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
    
    def _get_available_themes(self):
        """Get list of available themes by scanning theme directory"""
        themes = []
        theme_dir = 'static/themes'
        
        if os.path.exists(theme_dir):
            for file in os.listdir(theme_dir):
                if file.endswith('.css'):
                    theme_name = file[:-4]  # Remove .css extension
                    themes.append(theme_name)
        
        # Always ensure 'dark' is available as fallback
        if 'dark' not in themes:
            themes.append('dark')
        
        return sorted(themes)
    
    def _generate_theme_options(self, current_theme):
        """Generate HTML options for theme selector"""
        themes = self._get_available_themes()
        options = ""
        
        for theme in themes:
            selected = 'selected' if theme == current_theme else ''
            theme_display = theme.title()  # Capitalize first letter
            options += f'<option value="{theme}" {selected}>{theme_display}</option>\n'
        
        return options
    
    def show_config_manager(self, handler):
        """Show structured configuration form"""
        global_settings = self.backup_config.config.get('global_settings', {})
        notification_config = global_settings.get('notification', {})
        
        # Extract current values for form population
        default_schedule_times = global_settings.get('default_schedule_times', {})
        telegram_config = notification_config.get('telegram', {})
        email_config = notification_config.get('email', {})
        
        # Theme selection
        current_theme = global_settings.get('theme', 'dark')
        theme_options = self._generate_theme_options(current_theme)
        
        # Render structured config manager
        html_content = self.template_service.render_template(
            'config_manager.html',
            # Global settings (uppercase to match template)
            SCHEDULER_TIMEZONE=global_settings.get('scheduler_timezone', 'UTC'),
            THEME_OPTIONS=theme_options,
            ENABLE_CONFLICT_AVOIDANCE='checked' if global_settings.get('enable_conflict_avoidance', True) else '',
            CONFLICT_CHECK_INTERVAL=str(global_settings.get('conflict_check_interval', 300)),
            DELAY_NOTIFICATION_THRESHOLD=str(global_settings.get('delay_notification_threshold', 300)),
            
            # Schedule defaults
            HOURLY_DEFAULT=default_schedule_times.get('hourly', '0 * * * *'),
            DAILY_DEFAULT=default_schedule_times.get('daily', '0 3 * * *'), 
            WEEKLY_DEFAULT=default_schedule_times.get('weekly', '0 3 * * 0'),
            MONTHLY_DEFAULT=default_schedule_times.get('monthly', '0 3 1 * *'),
            
            # Telegram settings
            TELEGRAM_ENABLED='checked' if telegram_config.get('enabled', False) else '',
            TELEGRAM_SETTINGS_CLASS='' if telegram_config.get('enabled', False) else 'hidden',
            TELEGRAM_TOKEN=telegram_config.get('token', ''),
            TELEGRAM_CHAT_ID=telegram_config.get('chat_id', ''),
            TELEGRAM_QUEUE_ENABLED='checked' if telegram_config.get('queue_enabled', True) else '',
            TELEGRAM_QUEUE_SETTINGS_CLASS='' if telegram_config.get('queue_enabled', True) else 'hidden',
            TELEGRAM_QUEUE_INTERVAL=str(telegram_config.get('queue_interval_minutes', 5)),
            
            # Email settings
            EMAIL_ENABLED='checked' if email_config.get('enabled', False) else '',
            EMAIL_SETTINGS_CLASS='' if email_config.get('enabled', False) else 'hidden',
            EMAIL_SMTP_SERVER=email_config.get('smtp_server', ''),
            EMAIL_SMTP_PORT=str(email_config.get('smtp_port', 587)),
            EMAIL_TLS_CHECKED='checked' if email_config.get('use_tls', True) and not email_config.get('use_ssl', False) else '',
            EMAIL_SSL_CHECKED='checked' if email_config.get('use_ssl', False) else '',
            EMAIL_NONE_CHECKED='checked' if not email_config.get('use_tls', True) and not email_config.get('use_ssl', False) else '',
            EMAIL_FROM=email_config.get('from_email', ''),
            EMAIL_TO=email_config.get('to_email', ''),
            EMAIL_USERNAME=email_config.get('username', ''),
            EMAIL_PASSWORD=email_config.get('password', ''),
            EMAIL_QUEUE_ENABLED='checked' if email_config.get('queue_enabled', True) else '',
            EMAIL_QUEUE_SETTINGS_CLASS='' if email_config.get('queue_enabled', True) else 'hidden',
            EMAIL_QUEUE_INTERVAL=str(email_config.get('queue_interval_minutes', 15))
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
            
            # Theme setting (only save if not default 'dark')
            theme = form_data.get('theme', ['dark'])[0]
            if theme != 'dark':
                global_settings['theme'] = theme
            elif 'theme' in global_settings:
                # Remove theme key if set back to default
                del global_settings['theme']
            
            global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
            global_settings['conflict_check_interval'] = int(form_data.get('conflict_check_interval', ['300'])[0])
            global_settings['delay_notification_threshold'] = int(form_data.get('delay_notification_threshold', ['300'])[0])
            
            # Default schedule times
            default_schedule_times = global_settings.setdefault('default_schedule_times', {})
            default_schedule_times['hourly'] = form_data.get('hourly_default', ['0 * * * *'])[0]
            default_schedule_times['daily'] = form_data.get('daily_default', ['0 3 * * *'])[0]
            default_schedule_times['weekly'] = form_data.get('weekly_default', ['0 3 * * 0'])[0]
            default_schedule_times['monthly'] = form_data.get('monthly_default', ['0 3 1 * *'])[0]
            
            # Notification settings
            notification_config = global_settings.setdefault('notification', {})
            
            # Telegram settings
            telegram_config = notification_config.setdefault('telegram', {})
            telegram_config['enabled'] = 'enable_telegram' in form_data
            telegram_config['token'] = form_data.get('telegram_token', [''])[0]
            telegram_config['chat_id'] = form_data.get('telegram_chat_id', [''])[0]
            telegram_config['queue_enabled'] = 'telegram_queue_enabled' in form_data
            telegram_config['queue_interval_minutes'] = int(form_data.get('telegram_queue_interval', ['5'])[0])
            
            # Email settings
            email_config = notification_config.setdefault('email', {})
            email_config['enabled'] = 'enable_email' in form_data
            email_config['smtp_server'] = form_data.get('email_smtp_server', [''])[0]
            email_config['smtp_port'] = int(form_data.get('email_smtp_port', ['587'])[0])
            
            # Handle encryption radio buttons
            encryption_choice = form_data.get('email_encryption', ['none'])[0]
            email_config['use_tls'] = encryption_choice == 'tls'
            email_config['use_ssl'] = encryption_choice == 'ssl'
            
            email_config['from_email'] = form_data.get('email_from', [''])[0]
            email_config['to_email'] = form_data.get('email_to', [''])[0]
            email_config['username'] = form_data.get('email_username', [''])[0]
            email_config['password'] = form_data.get('email_password', [''])[0]
            email_config['queue_enabled'] = 'email_queue_enabled' in form_data
            email_config['queue_interval_minutes'] = int(form_data.get('email_queue_interval', ['15'])[0])
            
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
            self.template_service.send_redirect(handler, '/config/raw')
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
