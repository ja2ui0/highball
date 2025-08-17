"""
HTMX Config Management Service
Handles configuration form operations and notification testing for HTMX endpoints
"""
import logging
import html

logger = logging.getLogger(__name__)


class HTMXConfigManager:
    """Manages configuration form operations for HTMX endpoints"""
    
    def __init__(self):
        pass
    
    def render_notification_settings(self, provider, enabled, existing_data=None):
        """
        Render notification settings section based on enabled state
        Provider: 'telegram' or 'email'
        """
        if provider == 'telegram':
            return self._render_telegram_settings(enabled, existing_data)
        elif provider == 'email':
            return self._render_email_settings(enabled, existing_data)
        else:
            return f'<div id="{provider}Settings" class="hidden"></div>'
    
    def render_queue_settings(self, provider, enabled, existing_data=None):
        """
        Render queue settings section based on enabled state
        Provider: 'telegram' or 'email'
        """
        if provider == 'telegram':
            return self._render_telegram_queue_settings(enabled, existing_data)
        elif provider == 'email':
            return self._render_email_queue_settings(enabled, existing_data)
        else:
            return f'<div id="{provider}QueueSettings" class="hidden"></div>'
    
    def _render_telegram_settings(self, enabled, existing_data=None):
        """Render Telegram notification settings"""
        if not enabled:
            return '<div id="telegramSettings" class="path-group hidden"></div>'
        
        data = existing_data or {}
        token = html.escape(data.get('telegram_token', ''))
        chat_id = html.escape(data.get('telegram_chat_id', ''))
        
        return f'''
        <div id="telegramSettings" class="path-group">
            <div class="form-group">
                <label for="telegram_token">Bot Token:</label>
                <input type="text" id="telegram_token" name="telegram_token" 
                       value="{token}" placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11">
                <div class="help-text">Get from @BotFather on Telegram</div>
            </div>
            
            <div class="form-group">
                <label for="telegram_chat_id">Chat ID:</label>
                <input type="text" id="telegram_chat_id" name="telegram_chat_id" 
                       value="{chat_id}" placeholder="-1001234567890">
                <div class="help-text">
                    Get by messaging @userinfobot or create a group, add your bot, and use the negative group ID
                </div>
            </div>
            
            <div class="form-group">
                <button type="button" id="test_telegram" class="button button-warning"
                        hx-post="/htmx/test-telegram" 
                        hx-target="#telegram_test_result"
                        hx-include="[name='telegram_token'], [name='telegram_chat_id']"
                        hx-swap="innerHTML">Send Test Notification</button>
                <div id="telegram_test_result" class="help-text"></div>
            </div>
        </div>
        '''
    
    def _render_email_settings(self, enabled, existing_data=None):
        """Render Email notification settings"""
        if not enabled:
            return '<div id="emailSettings" class="path-group hidden"></div>'
        
        data = existing_data or {}
        smtp_server = html.escape(data.get('email_smtp_server', ''))
        smtp_port = html.escape(data.get('email_smtp_port', '587'))
        from_email = html.escape(data.get('email_from', ''))
        to_email = html.escape(data.get('email_to', ''))
        username = html.escape(data.get('email_username', ''))
        
        # Handle encryption radio buttons
        use_tls = data.get('email_use_tls', True)
        use_ssl = data.get('email_use_ssl', False)
        
        tls_checked = 'checked' if use_tls and not use_ssl else ''
        ssl_checked = 'checked' if use_ssl else ''
        none_checked = 'checked' if not use_tls and not use_ssl else ''
        
        return f'''
        <div id="emailSettings" class="path-group">
            <div class="form-group">
                <label for="email_smtp_server">SMTP Server:</label>
                <input type="text" id="email_smtp_server" name="email_smtp_server" 
                       value="{smtp_server}" placeholder="smtp.gmail.com">
            </div>
            
            <div class="form-group">
                <label for="email_smtp_port">SMTP Port:</label>
                <input type="number" id="email_smtp_port" name="email_smtp_port" 
                       value="{smtp_port}" placeholder="587">
                <div class="help-text">Common ports: 587 (TLS), 465 (SSL), 25 (none)</div>
            </div>
            
            <div class="form-group">
                <label>Encryption:</label>
                <div class="radio-group">
                    <label>
                        <input type="radio" name="email_encryption" value="tls" {tls_checked}> TLS (recommended)
                    </label>
                    <label>
                        <input type="radio" name="email_encryption" value="ssl" {ssl_checked}> SSL
                    </label>
                    <label>
                        <input type="radio" name="email_encryption" value="none" {none_checked}> None
                    </label>
                </div>
            </div>
            
            <div class="form-group">
                <label for="email_from">From Email:</label>
                <input type="email" id="email_from" name="email_from" 
                       value="{from_email}" placeholder="backup@yourcompany.com">
            </div>
            
            <div class="form-group">
                <label for="email_to">To Email:</label>
                <input type="email" id="email_to" name="email_to" 
                       value="{to_email}" placeholder="admin@yourcompany.com">
            </div>
            
            <div class="form-group">
                <label for="email_username">Username:</label>
                <input type="text" id="email_username" name="email_username" 
                       value="{username}" placeholder="username@gmail.com">
                <div class="help-text">SMTP authentication username (often same as from email)</div>
            </div>
            
            <div class="form-group">
                <label for="email_password">Password:</label>
                <input type="password" id="email_password" name="email_password" 
                       placeholder="SMTP password or app-specific password">
                <div class="help-text">Use app-specific password for Gmail/Outlook</div>
            </div>
            
            <div class="form-group">
                <button type="button" id="test_email" class="button button-warning"
                        hx-post="/htmx/test-email" 
                        hx-target="#email_test_result"
                        hx-include="[name^='email_']"
                        hx-swap="innerHTML">Send Test Notification</button>
                <div id="email_test_result" class="help-text"></div>
            </div>
        </div>
        '''
    
    def _render_telegram_queue_settings(self, enabled, existing_data=None):
        """Render Telegram queue settings"""
        if not enabled:
            return '<div id="telegramQueueSettings" class="hidden"></div>'
        
        data = existing_data or {}
        interval = html.escape(str(data.get('telegram_queue_interval', '300')))
        
        return f'''
        <div id="telegramQueueSettings" class="queue-settings">
            <div class="form-group">
                <label for="telegram_queue_interval">Queue Interval (seconds):</label>
                <input type="number" id="telegram_queue_interval" name="telegram_queue_interval" 
                       value="{interval}" min="60" placeholder="300">
                <div class="help-text">Minimum time between notification batches</div>
            </div>
        </div>
        '''
    
    def _render_email_queue_settings(self, enabled, existing_data=None):
        """Render Email queue settings"""
        if not enabled:
            return '<div id="emailQueueSettings" class="hidden"></div>'
        
        data = existing_data or {}
        interval = html.escape(str(data.get('email_queue_interval', '300')))
        
        return f'''
        <div id="emailQueueSettings" class="queue-settings">
            <div class="form-group">
                <label for="email_queue_interval">Queue Interval (seconds):</label>
                <input type="number" id="email_queue_interval" name="email_queue_interval" 
                       value="{interval}" min="60" placeholder="300">
                <div class="help-text">Minimum time between notification batches</div>
            </div>
        </div>
        '''
    
    def render_test_result(self, provider, message, success):
        """Render notification test result"""
        color = 'var(--success-color, #22c55e)' if success else 'var(--error-color, #ef4444)'
        return f'<div style="color: {color}">{html.escape(message)}</div>'