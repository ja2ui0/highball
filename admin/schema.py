"""
Admin Schema Definitions
Schemas for global system configuration, notification providers, and administrative settings
"""

# =============================================================================
# NOTIFICATION PROVIDER FIELD SCHEMAS
# =============================================================================

PROVIDER_FIELD_SCHEMAS = {
    'telegram': {
        'display_name': 'Telegram',
        'required_fields': ['token', 'chat_id'],
        'fields': [
            {
                'name': 'enabled',
                'type': 'checkbox',
                'label': 'Enable Telegram notifications',
                'help': 'Globally enable or disable Telegram notifications'
            },
            {
                'name': 'token',
                'type': 'text',
                'label': 'Bot Token',
                'help': 'Get from @BotFather on Telegram',
                'placeholder': '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz',
                'required': True
            },
            {
                'name': 'chat_id', 
                'type': 'text',
                'label': 'Chat ID',
                'help': 'Chat or group ID where notifications will be sent',
                'placeholder': '-1001234567890',
                'required': True
            }
        ],
        'sections': [
            {
                'name': 'queue_settings',
                'title': 'Queue Settings',
                'fields': [
                    {
                        'name': 'queue_enabled',
                        'type': 'checkbox',
                        'label': 'Enable notification queueing',
                        'help': 'Spam prevention - batches messages to avoid frequent notifications'
                    },
                    {
                        'name': 'queue_interval_minutes',
                        'type': 'number',
                        'label': 'Minimum time between messages (minutes)',
                        'help': 'Messages will be batched and sent no more frequently than this interval',
                        'placeholder': '5',
                        'min': 1,
                        'max': 1440
                    }
                ]
            }
        ]
    },
    'email': {
        'display_name': 'Email',
        'required_fields': ['smtp_server', 'smtp_port', 'from_email', 'to_email'],
        'fields': [
            {
                'name': 'enabled',
                'type': 'checkbox',
                'label': 'Enable email notifications',
                'help': 'Globally enable or disable email notifications'
            }
        ],
        'sections': [
            {
                'name': 'smtp_config',
                'title': 'SMTP Configuration', 
                'fields': [
                    {
                        'name': 'smtp_server',
                        'type': 'text',
                        'label': 'SMTP Server',
                        'placeholder': 'smtp.gmail.com',
                        'required': True
                    },
                    {
                        'name': 'smtp_port',
                        'type': 'number',
                        'label': 'SMTP Port',
                        'help': '587 for TLS, 465 for SSL, 25 for plain',
                        'placeholder': '587',
                        'required': True
                    },
                    {
                        'name': 'encryption',
                        'type': 'select',
                        'label': 'Encryption',
                        'help': 'Encryption method for SMTP connection',
                        'default': 'tls',
                        'options': [
                            {'value': 'tls', 'label': 'TLS', 'config_field': 'use_tls'},
                            {'value': 'ssl', 'label': 'SSL', 'config_field': 'use_ssl'}, 
                            {'value': 'none', 'label': 'None'}
                        ]
                    },
                    {
                        'name': 'from_email',
                        'type': 'email',
                        'label': 'From Email',
                        'placeholder': 'backup@yourcompany.com',
                        'required': True
                    },
                    {
                        'name': 'to_email',
                        'type': 'email', 
                        'label': 'To Email',
                        'placeholder': 'admin@yourcompany.com',
                        'required': True
                    },
                    {
                        'name': 'username',
                        'type': 'text',
                        'label': 'SMTP Username',
                        'help': 'Usually your email address',
                        'placeholder': 'your.email@gmail.com'
                    },
                    {
                        'name': 'password',
                        'type': 'password',
                        'label': 'SMTP Password', 
                        'help': 'Use app password for Gmail',
                        'placeholder': 'your-app-password'
                    }
                ]
            },
            {
                'name': 'queue_settings',
                'title': 'Queue Settings',
                'fields': [
                    {
                        'name': 'queue_enabled',
                        'type': 'checkbox',
                        'label': 'Enable notification queueing',
                        'help': 'Spam prevention - batches messages to avoid frequent notifications'
                    },
                    {
                        'name': 'queue_interval_minutes',
                        'type': 'number',
                        'label': 'Minimum time between messages (minutes)',
                        'help': 'Messages will be batched and sent no more frequently than this interval',
                        'placeholder': '15',
                        'min': 1,
                        'max': 1440
                    }
                ]
            }
        ]
    }
}