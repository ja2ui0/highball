"""
Notification test handler for testing provider configurations
Handles test notification endpoints for configuration validation
"""
import json
from services.notification_service import NotificationService


class NotificationTestHandler:
    """Handler for notification testing endpoints"""
    
    def __init__(self):
        pass
    
    def test_telegram_notification(self, handler, form_data):
        """Test Telegram notification with provided credentials"""
        try:
            # Extract form data
            token = form_data.get('token', [''])[0]
            chat_id = form_data.get('chat_id', [''])[0]
            
            if not token or not chat_id:
                response = {"success": False, "message": "Bot token and chat ID are required"}
            else:
                # Create temporary config for testing
                test_config = self._create_telegram_test_config(token, chat_id)
                
                # Try to send test notification
                try:
                    mock_config = self._create_mock_backup_config(test_config)
                    notification_service = NotificationService(mock_config)
                    
                    results = notification_service.test_notification_with_results(
                        "Highball Test Notification", 
                        "This is a test notification from Highball Backup Manager. Your Telegram configuration is working correctly!",
                        "info"
                    )
                    
                    # Check results
                    if not results:
                        response = {"success": False, "message": "No notification providers configured"}
                    elif all(result.success for result in results):
                        response = {"success": True, "message": "Test notification sent successfully. Check your Telegram for the message."}
                    else:
                        failed_result = next(result for result in results if not result.success)
                        error_msg = failed_result.error_message or "Unknown error"
                        response = self._format_telegram_error(error_msg)
                        
                except Exception as e:
                    error_msg = str(e)
                    response = self._format_telegram_error(error_msg)
            
            self._send_json_response(handler, response, 200)
            
        except Exception as e:
            response = {"success": False, "message": f"Test failed: {str(e)}"}
            self._send_json_response(handler, response, 500)
    
    def test_email_notification(self, handler, form_data):
        """Test email notification with provided credentials"""
        try:
            # Extract and validate form data
            email_data = self._extract_email_form_data(form_data)
            
            if not email_data['valid']:
                response = {"success": False, "message": email_data['error']}
            else:
                # Create temporary config for testing
                test_config = self._create_email_test_config(email_data)
                
                # Try to send test notification
                try:
                    mock_config = self._create_mock_backup_config(test_config)
                    notification_service = NotificationService(mock_config)
                    
                    results = notification_service.test_notification_with_results(
                        "Highball Test Notification", 
                        "This is a test notification from Highball Backup Manager. Your email configuration is working correctly!",
                        "info"
                    )
                    
                    # Check results
                    if not results:
                        response = {"success": False, "message": "No notification providers configured"}
                    elif all(result.success for result in results):
                        response = {"success": True, "message": "Test notification sent successfully. Check your email inbox."}
                    else:
                        failed_result = next(result for result in results if not result.success)
                        error_msg = failed_result.error_message or "Unknown error"
                        response = self._format_email_error(error_msg)
                        
                except Exception as e:
                    error_msg = str(e)
                    response = self._format_email_error(error_msg)
            
            self._send_json_response(handler, response, 200)
            
        except Exception as e:
            response = {"success": False, "message": f"Test failed: {str(e)}"}
            self._send_json_response(handler, response, 500)
    
    def _extract_email_form_data(self, form_data):
        """Extract and validate email form data"""
        smtp_server = form_data.get('smtp_server', [''])[0]
        from_email = form_data.get('from_email', [''])[0]
        to_email = form_data.get('to_email', [''])[0]
        
        # Validate required fields
        if not all([smtp_server, from_email, to_email]):
            return {'valid': False, 'error': 'SMTP server, from email, and to email are required'}
        
        try:
            smtp_port = int(form_data.get('smtp_port', ['587'])[0])
        except ValueError:
            return {'valid': False, 'error': 'Invalid SMTP port number'}
        
        return {
            'valid': True,
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'from_email': from_email,
            'to_email': to_email,
            'username': form_data.get('username', [''])[0],
            'password': form_data.get('password', [''])[0],
            'encryption': form_data.get('encryption', ['tls'])[0]
        }
    
    def _create_telegram_test_config(self, token, chat_id):
        """Create test configuration for Telegram"""
        return {
            'global_settings': {
                'notification': {
                    'telegram': {
                        'enabled': True,
                        'notify_on_success': False,
                        'token': token,
                        'chat_id': chat_id
                    }
                }
            }
        }
    
    def _create_email_test_config(self, email_data):
        """Create test configuration for Email"""
        return {
            'global_settings': {
                'notification': {
                    'email': {
                        'enabled': True,
                        'notify_on_success': False,
                        'smtp_server': email_data['smtp_server'],
                        'smtp_port': email_data['smtp_port'],
                        'use_tls': email_data['encryption'] == 'tls',
                        'use_ssl': email_data['encryption'] == 'ssl',
                        'from_email': email_data['from_email'],
                        'to_email': email_data['to_email'],
                        'username': email_data['username'],
                        'password': email_data['password']
                    }
                }
            }
        }
    
    def _create_mock_backup_config(self, config):
        """Create mock backup config object for testing"""
        class MockBackupConfig:
            def __init__(self, config):
                self.config = config
        
        return MockBackupConfig(config)
    
    def _format_telegram_error(self, error_msg):
        """Format Telegram-specific error messages"""
        error_lower = error_msg.lower()
        
        if "unauthorized" in error_lower or "token" in error_lower:
            return {"success": False, "message": "Invalid bot token. Check your token from @BotFather."}
        elif "chat not found" in error_lower or "chat_id" in error_lower:
            return {"success": False, "message": "Invalid chat ID. Make sure the bot has been added to the chat."}
        elif "forbidden" in error_lower:
            return {"success": False, "message": "Bot is blocked or doesn't have permission to send messages."}
        else:
            return {"success": False, "message": f"Telegram error: {error_msg}"}
    
    def _format_email_error(self, error_msg):
        """Format email-specific error messages"""
        error_lower = error_msg.lower()
        
        if "authentication failed" in error_lower:
            return {"success": False, "message": "Authentication failed. Check your username and password."}
        elif "connection refused" in error_lower:
            return {"success": False, "message": "Connection refused. Check your SMTP server and port."}
        elif "tls" in error_lower or "ssl" in error_lower:
            return {"success": False, "message": "TLS/SSL error. Check your encryption settings."}
        elif "timeout" in error_lower:
            return {"success": False, "message": "Connection timeout. Check your server address and network."}
        elif "name or service not known" in error_lower:
            return {"success": False, "message": "SMTP server not found. Check your server address."}
        else:
            return {"success": False, "message": f"Email error: {error_msg}"}
    
    def _send_json_response(self, handler, response, status_code):
        """Send JSON response with proper headers"""
        handler.send_response(status_code)
        handler.send_header('Content-Type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps(response).encode())