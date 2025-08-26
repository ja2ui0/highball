"""
Origins Schema Definitions
Schemas for SSH hosts, local sources, and origin-related form validation
"""

# =============================================================================
# SOURCE TYPE SCHEMAS
# =============================================================================

SOURCE_TYPE_SCHEMAS = {
    'local': {
        'display_name': 'Local Filesystem',
        'description': 'Backup from local filesystem paths',
        'always_available': True,
        'requires': [],
        'fields': {},  # No additional connection fields needed
        'required_fields': []  # No required connection fields
    },
    'ssh': {
        'display_name': 'SSH Remote',
        'description': 'Backup from remote SSH host',
        'always_available': True,
        'requires': ['ssh'],
        'fields': {
            'hostname': {'config_key': 'hostname', 'required': True},
            'username': {'config_key': 'username', 'required': True}
        },
        'required_fields': ['hostname', 'username']
    }
}

# =============================================================================
# SOURCE PATH SCHEMA
# =============================================================================

SOURCE_PATH_SCHEMA = {
    'display_name': 'Source Path',
    'description': 'Configure backup source with path and optional include/exclude patterns',
    'fields': [
        {
            'name': 'path',
            'type': 'text',
            'label': 'Path',
            'help': 'Directory or file path to backup',
            'placeholder': '/path/to/backup',
            'required': True
        },
        {
            'name': 'includes',
            'type': 'textarea',
            'label': 'Include Patterns (optional)',
            'help': 'Glob patterns for files to include. Leave empty to include all files.',
            'placeholder': '**/*.jpg\ndocuments/**\nconfig.ini',
            'required': False,
            'rows': 3
        },
        {
            'name': 'excludes', 
            'type': 'textarea',
            'label': 'Exclude Patterns (optional)',
            'help': 'Glob patterns for files to exclude from backup.',
            'placeholder': '**/*.tmp\ncache/**\n*.log',
            'required': False,
            'rows': 3
        }
    ]
}

# =============================================================================
# SSH ORIGIN SCHEMA
# =============================================================================

SSH_ORIGIN_SCHEMA = {
    'display_name': 'SSH Origin Configuration',
    'description': 'Configure SSH host connection details and authentication method',
    'fields': [
        {
            'name': 'friendly_name',
            'type': 'text',
            'label': 'Friendly Name',
            'help': 'Display name for this SSH origin (e.g. "Vegas PC", "Production Server")',
            'placeholder': 'My Server',
            'required': True,
            'max_length': 100
        },
        {
            'name': 'ssh_hostname',
            'type': 'text',
            'label': 'SSH Hostname',
            'help': 'SSH server hostname or IP address',
            'placeholder': 'server.home.arpa',
            'required': True
        },
        {
            'name': 'ssh_port',
            'type': 'number',
            'label': 'SSH Port',
            'help': 'SSH port number (default: 22)',
            'placeholder': '22',
            'default': '22',
            'min': 1,
            'max': 65535
        },
        {
            'name': 'ssh_timeout',
            'type': 'number',
            'label': 'Connection Timeout',
            'help': 'SSH connection timeout in seconds',
            'placeholder': '5',
            'default': '5',
            'min': 1,
            'max': 60
        },
        {
            'name': 'ssh_username',
            'type': 'text',
            'label': 'SSH Username',
            'help': 'Username for SSH authentication',
            'placeholder': 'username',
            'required': True
        },
        {
            'name': 'ssh_highball',
            'type': 'checkbox',
            'label': 'Auto-populate Highball SSH keys',
            'help': 'Use Highball\'s managed SSH keypair. Requires password during setup to install public key.',
            'default': True
        },
        {
            'name': 'ssh_password',
            'type': 'password',
            'label': 'SSH Password (for key installation)',
            'help': 'Temporary password for ssh-copy-id key installation. Not stored after setup.',
            'placeholder': 'password',
            'conditional': {
                'show_when': 'ssh_highball',
                'value': True
            }
        }
    ]
}

# =============================================================================
# SSH ORIGIN VALIDATION SCHEMA
# =============================================================================

SSH_ORIGIN_VALIDATION_SCHEMA = {
    'display_name': 'SSH Origin Validation',
    'description': 'SSH connection validation and capability detection results',
    'fields': [
        {
            'name': 'connection_success',
            'type': 'status',
            'label': 'SSH Connection',
            'help': 'Whether SSH connection was successful'
        },
        {
            'name': 'rsync_available',
            'type': 'status',
            'label': 'rsync Available',
            'help': 'Whether rsync is installed and available on the target host'
        },
        {
            'name': 'container_runtime',
            'type': 'text',
            'label': 'Container Runtime',
            'help': 'Detected container runtime (docker, podman, or null if none available)'
        },
        {
            'name': 'validation_message',
            'type': 'text',
            'label': 'Validation Details',
            'help': 'Additional details about the validation process'
        }
    ]
}