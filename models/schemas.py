"""
Backup Schema Definitions
Extracted from models/backup.py - contains all schema dictionaries for form generation and validation
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
# DESTINATION TYPE SCHEMAS
# =============================================================================

# Base schema for all destination types - shared fields
DESTINATION_BASE_SCHEMA = {
    'friendly_name': {'config_key': 'friendly_name', 'required': False},
    'uri': {'config_key': 'uri', 'required': True, 'auto_generated': True},
    'hostname': {'config_key': 'hostname', 'required': True},
    'port': {'config_key': 'port', 'required': True}
}

DESTINATION_TYPE_SCHEMAS = {
    'rsync': {
        'display_name': 'Rsync (SSH)',
        'description': 'Remote backup using rsync over SSH',
        'always_available': True,
        'requires': ['rsync', 'ssh'],
        'fields': {
            'friendly_name': {'config_key': 'friendly_name', 'required': False},
            'uri': {'config_key': 'uri', 'required': True, 'auto_generated': True},
            'hostname': {'config_key': 'hostname', 'required': True},
            'port': {'config_key': 'port', 'required': True, 'default': 22},
            'username': {'config_key': 'username', 'required': True},
            'path': {'config_key': 'path', 'required': True}
        },
        'required_fields': ['hostname', 'port', 'username', 'path']
    },
    'rsyncd': {
        'display_name': 'Rsync Daemon',
        'description': 'Remote backup using rsync daemon protocol',
        'always_available': True,
        'requires': ['rsync'],
        'fields': {
            'friendly_name': {'config_key': 'friendly_name', 'required': False},
            'uri': {'config_key': 'uri', 'required': True, 'auto_generated': True},
            'hostname': {'config_key': 'hostname', 'required': True},
            'port': {'config_key': 'port', 'required': True, 'default': 873},
            'username': {'config_key': 'username', 'required': False},
            'password': {'config_key': 'password', 'required': False, 'secret': True, 'env_var': 'RSYNCD_PASSWORD'},
            'share': {'config_key': 'share', 'required': True}
        },
        'required_fields': ['hostname', 'port', 'share']
    },
    'restic': {
        'display_name': 'Restic Repository',
        'description': 'Encrypted, deduplicated backup repository',
        'always_available': False,
        'requires': ['restic'],
        'requires_container_runtime': True,
        'availability_check': 'check_restic_availability',
        'fields': {
            'friendly_name': {'config_key': 'friendly_name', 'required': False},
            'uri': {'config_key': 'uri', 'required': True, 'auto_generated': True},
            'hostname': {'config_key': 'hostname', 'required': True},
            'port': {'config_key': 'port', 'required': True},
            'type': {'config_key': 'type', 'required': True},
            'password': {'config_key': 'password', 'required': True, 'secret': True, 'env_var': 'RESTIC_PASSWORD'}
        },
        'required_fields': ['hostname', 'port', 'type', 'password']
    }
}

# =============================================================================
# RESTIC REPOSITORY TYPE SCHEMAS
# =============================================================================

RESTIC_REPOSITORY_TYPE_SCHEMAS = {
    'local': {
        'display_name': 'Local Path',
        'description': 'Store repository on local filesystem',
        'always_available': True,
        'quick_check': {
            'command': ['test', '-d', '{local_path_parent}'],
            'expected_returncode': 0,
            'timeout': 3,
            'variables': {
                'local_path_parent': 'dirname {local_path}'
            }
        },
        'fields': [
            {
                'name': 'local_path',
                'type': 'text',
                'label': 'Local Repository Path',
                'help': 'Local filesystem path where the repository will be stored',
                'placeholder': '/path/to/repository',
                'required': True
            }
        ]
    },
    'rest': {
        'display_name': 'REST Server',
        'description': 'Store repository on REST server',
        'always_available': True,
        'quick_check': {
            'command': ['restic', '-r', '{repo_uri}', 'check', '--read-data-subset=0.1%'],
            'expected_returncode': 0,
            'timeout': 10,
            'env': {
                'RESTIC_PASSWORD': '{password}'
            }
        },
        'fields': [
            {
                'name': 'hostname',
                'type': 'text',
                'label': 'REST Server Hostname',
                'help': 'Hostname or IP address of the REST server',
                'placeholder': 'rest-server.example.com',
                'required': True
            },
            {
                'name': 'port',
                'type': 'number',
                'label': 'REST Server Port',
                'help': 'Port number (default: 8000)',
                'placeholder': '8000',
                'default': '8000',
                'min': 1,
                'max': 65535
            },
            {
                'name': 'path',
                'type': 'text',
                'label': 'Repository Path',
                'help': 'Path to the repository on the REST server',
                'placeholder': '/my-backup-repo'
            },
            {
                'name': 'use_root',
                'type': 'checkbox',
                'label': 'Use Repository Root',
                'help': 'Connect to repository served directly from server root (no additional path)',
                'default': False
            },
            {
                'name': 'use_https',
                'type': 'checkbox',
                'label': 'Use HTTPS',
                'help': 'Use HTTPS instead of HTTP (recommended for production)',
                'default': False
            },
            {
                'name': 'username',
                'type': 'text',
                'label': 'Username (Optional)',
                'help': 'HTTP Basic Auth username if server requires authentication',
                'placeholder': 'username'
            },
            {
                'name': 'password',
                'type': 'password',
                'label': 'Password (Optional)',
                'help': 'HTTP Basic Auth password if server requires authentication',
                'placeholder': 'password',
                'secret': True,
                'env_var': 'HTPASSWD'
            }
        ]
    },
    's3': {
        'display_name': 'Amazon S3',
        'description': 'Store repository in Amazon S3 bucket',
        'always_available': True,
        'quick_check': {
            'command': ['curl', '--max-time', '3', '-s', '-I', '{s3_endpoint}'],
            'expected_returncode': 0,
            'timeout': 5,
            'skip_if_empty': ['s3_endpoint']
        },
        'fields': [
            {
                'name': 'bucket',
                'type': 'text',
                'label': 'S3 Bucket',
                'help': 'Amazon S3 bucket name',
                'placeholder': 'my-backup-bucket',
                'required': True,
                'htmx_trigger': 'input delay:300ms',
                'htmx_post': '/htmx/restic-uri-preview',
                'htmx_target': '#uri_preview_container',
                'htmx_include': "[name='restic_repo_type'], [name^='s3_']"
            },
            {
                'name': 'prefix',
                'type': 'text',
                'label': 'S3 Key Prefix (optional)',
                'help': 'Optional prefix for repository keys within the bucket',
                'placeholder': 'backups/',
                'htmx_trigger': 'input delay:300ms',
                'htmx_post': '/htmx/restic-uri-preview',
                'htmx_target': '#uri_preview_container',
                'htmx_include': "[name='restic_repo_type'], [name^='s3_']"
            },
            {
                'name': 'region',
                'type': 'text',
                'label': 'AWS Region (optional)',
                'help': 'AWS region (defaults to us-east-1). Not required for non-AWS S3-compatible services like Cloudflare R2, MinIO',
                'placeholder': 'us-east-1',
                'required': False,
                'default': 'us-east-1'
            },
            {
                'name': 'access_key',
                'type': 'text',
                'label': 'Access Key ID',
                'help': 'AWS Access Key ID for authentication',
                'placeholder': 'AKIAIOSFODNN7EXAMPLE',
                'required': True,
                'secret': True,
                'env_var': 'S3_ACCESS_KEY_ID'
            },
            {
                'name': 'secret_key',
                'type': 'password',
                'label': 'Secret Access Key',
                'help': 'AWS Secret Access Key for authentication',
                'placeholder': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'required': True,
                'secret': True,
                'env_var': 'S3_SECRET_ACCESS_KEY'
            },
            {
                'name': 'endpoint',
                'type': 'text',
                'label': 'S3 Endpoint',
                'help': 'AWS: https://s3.us-east-1.amazonaws.com | Cloudflare R2: your account endpoint | MinIO/other: custom endpoint',
                'placeholder': 'https://s3.us-east-1.amazonaws.com',
                'htmx_trigger': 'input delay:300ms',
                'htmx_post': '/htmx/restic-uri-preview',
                'htmx_target': '#uri_preview_container',
                'htmx_include': "[name='restic_repo_type'], [name^='s3_']"
            }
        ]
    },
    'sftp': {
        'display_name': 'SFTP',
        'description': 'Store repository via SFTP',
        'always_available': True,
        'quick_check': {
            'command': ['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes', '{sftp_username}@{sftp_hostname}', 'echo', 'connected'],
            'expected_stdout': 'connected',
            'timeout': 5
        },
        'fields': [
            {
                'name': 'hostname',
                'type': 'text',
                'label': 'SFTP Host',
                'help': 'SFTP server hostname',
                'placeholder': 'sftp.example.com',
                'required': True
            },
            {
                'name': 'username',
                'type': 'text',
                'label': 'SFTP Username',
                'help': 'Username for SFTP authentication',
                'placeholder': 'username',
                'required': True
            },
            {
                'name': 'path',
                'type': 'text',
                'label': 'SFTP Path',
                'help': 'Path on the SFTP server',
                'placeholder': '/backups/repo',
                'required': True
            }
        ]
    },
    'rclone': {
        'display_name': 'rclone Remote',
        'description': 'Store repository via rclone remote',
        'always_available': True,
        'quick_check': {
            'command': ['rclone', 'lsd', '{rclone_remote}:', '--max-depth', '1'],
            'expected_returncode': 0,
            'timeout': 10
        },
        'fields': [
            {
                'name': 'remote',
                'type': 'text',
                'label': 'rclone Remote',
                'help': 'rclone remote name (configure with "rclone config")',
                'placeholder': 'myremote',
                'required': True
            },
            {
                'name': 'path',
                'type': 'text',
                'label': 'Remote Path',
                'help': 'Path within the rclone remote',
                'placeholder': 'backup/repo',
                'required': True
            }
        ]
    },
    'same_as_origin': {
        'display_name': 'Path on Origin Host',
        'description': 'Store repository on the same host as the backup origin (useful for file rollbacks)',
        'always_available': True,
        'quick_check': {
            'command': ['test', '-w', '{origin_repo_path_parent}'],
            'expected_returncode': 0,
            'timeout': 5,
            'variables': {
                'origin_repo_path_parent': 'dirname {origin_repo_path}'
            }
        },
        'fields': [
            {
                'name': 'path',
                'type': 'text',
                'label': 'Repository Path on Origin Host',
                'help': 'Path where the repository will be stored on the origin host (requires write permissions)',
                'placeholder': '/tmp/restic-repo',
                'required': True
            }
        ]
    }
}

# =============================================================================
# SOURCE PATH SCHEMA
# =============================================================================

# Source path schema for universal path/include/exclude handling across all providers
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
# MAINTENANCE MODE SCHEMAS
# =============================================================================

# Maintenance mode schemas for dynamic form generation
MAINTENANCE_MODE_SCHEMAS = {
    'auto': {
        'display_name': 'Auto (Recommended)',
        'description': 'Use safe defaults for maintenance schedules and retention',
        'help_text': 'Automatic maintenance uses safe defaults: daily cleanup at 3am, weekly integrity checks Sunday 2am, keeps last 7 snapshots plus 7 daily, 4 weekly, 6 monthly.',
        'fields': []
    },
    'user': {
        'display_name': 'User Configured',
        'description': 'Configure custom maintenance schedules and retention policies',
        'help_text': 'Configure your own maintenance schedules and retention policies. These will override the defaults when saved.',
        'fields': [
            {
                'name': 'maintenance_discard_schedule',
                'type': 'text',
                'label': 'Discard Schedule (Cron)',
                'help': 'When to run cleanup (forget + prune operations)',
                'placeholder': '0 3 * * *',
                'default': '0 3 * * *'
            },
            {
                'name': 'maintenance_check_schedule',
                'type': 'text',
                'label': 'Check Schedule (Cron)',
                'help': 'When to run integrity checks',
                'placeholder': '0 2 * * 0',
                'default': '0 2 * * 0'
            },
            {
                'name': 'keep_last',
                'type': 'number',
                'label': 'Keep Last',
                'help': 'Always keep this many recent snapshots',
                'default': '7',
                'min': 1,
                'max': 100
            },
            {
                'name': 'keep_hourly',
                'type': 'number',
                'label': 'Keep Hourly',
                'help': 'Keep this many hourly snapshots',
                'default': '6',
                'min': 0,
                'max': 100
            },
            {
                'name': 'keep_daily',
                'type': 'number',
                'label': 'Keep Daily',
                'help': 'Keep this many daily snapshots',
                'default': '7',
                'min': 0,
                'max': 100
            },
            {
                'name': 'keep_weekly',
                'type': 'number',
                'label': 'Keep Weekly',
                'help': 'Keep this many weekly snapshots',
                'default': '4',
                'min': 0,
                'max': 100
            },
            {
                'name': 'keep_monthly',
                'type': 'number',
                'label': 'Keep Monthly',
                'help': 'Keep this many monthly snapshots',
                'default': '6',
                'min': 0,
                'max': 100
            },
            {
                'name': 'keep_yearly',
                'type': 'number',
                'label': 'Keep Yearly',
                'help': 'Keep this many yearly snapshots',
                'default': '0',
                'min': 0,
                'max': 100
            }
        ]
    },
    'off': {
        'display_name': 'Disabled',
        'description': 'Disable automatic maintenance completely',
        'help_text': 'Repository maintenance is disabled. This may cause your repository to grow without bounds and potential corruption may go undetected. Only disable if you handle maintenance externally.',
        'fields': []
    }
}

# =============================================================================
# JOB NOTIFICATION SCHEMA
# =============================================================================

# Job-level notification configuration schema (per provider)
JOB_NOTIFICATION_SCHEMA = {
    'display_name': 'Notification Configuration',
    'description': 'Configure when and how to receive notifications for this job',
    'fields': [
        {
            'name': 'notify_on_success',
            'type': 'checkbox',
            'label': 'Notify on Success',
            'help': 'Send notification when backup completes successfully',
            'default': False
        },
        {
            'name': 'success_message',
            'type': 'text',
            'label': 'Custom Success Message (optional)',
            'help': 'Custom message template. Variables: {job_name}, {duration}',
            'placeholder': "Job '{job_name}' completed successfully in {duration}",
            'required': False,
            'conditional': {
                'show_when': 'notify_on_success',
                'value': True
            }
        },
        {
            'name': 'notify_on_failure',
            'type': 'checkbox',
            'label': 'Notify on Failure',
            'help': 'Send notification when backup fails',
            'default': True
        },
        {
            'name': 'failure_message',
            'type': 'text',
            'label': 'Custom Failure Message (optional)',
            'help': 'Custom message template. Variables: {job_name}, {error_message}',
            'placeholder': "Job '{job_name}' failed: {error_message}",
            'required': False,
            'conditional': {
                'show_when': 'notify_on_failure',
                'value': True
            }
        },
        {
            'name': 'notify_on_maintenance_failure',
            'type': 'checkbox',
            'label': 'Notify on Maintenance Failure',
            'help': 'Send notification when repository maintenance operations fail',
            'default': False
        }
    ]
}

# =============================================================================
# JOB SCHEDULE SCHEMA
# =============================================================================

# Job schedule configuration schema
JOB_SCHEDULE_SCHEMA = {
    'display_name': 'Schedule Configuration',
    'description': 'Configure when the backup job should run',
    'schedule_options': [
        {
            'value': 'manual',
            'label': 'Manual Only',
            'description': 'Job will only run when manually triggered'
        },
        {
            'value': 'hourly',
            'label': 'Hourly',
            'description': 'Run every hour at the top of the hour',
            'cron_pattern': '0 * * * *'
        },
        {
            'value': 'daily',
            'label': 'Daily',
            'description': 'Run once per day at 3:00 AM',
            'cron_pattern': '0 3 * * *'
        },
        {
            'value': 'weekly',
            'label': 'Weekly',
            'description': 'Run once per week on Sunday at 3:00 AM',
            'cron_pattern': '0 3 * * 0'
        },
        {
            'value': 'monthly',
            'label': 'Monthly',
            'description': 'Run on the first day of each month at 3:00 AM',
            'cron_pattern': '0 3 1 * *'
        },
        {
            'value': 'custom',
            'label': 'Custom Cron Pattern',
            'description': 'Define a custom schedule using cron syntax'
        }
    ],
    'fields': [
        {
            'name': 'schedule',
            'type': 'select',
            'label': 'Schedule',
            'help': 'When should this backup job run?',
            'required': True,
            'default': 'manual'
        },
        {
            'name': 'cron_pattern',
            'type': 'text',
            'label': 'Cron Pattern',
            'help': 'Custom cron schedule (minute hour day month weekday)',
            'placeholder': '0 3 * * *',
            'conditional': {
                'show_when': 'schedule',
                'value': 'custom'
            }
        },
        {
            'name': 'enabled',
            'type': 'checkbox',
            'label': 'Enabled',
            'help': 'When enabled, this job will run according to its schedule',
            'default': True
        },
        {
            'name': 'respect_conflicts',
            'type': 'checkbox',
            'label': 'Wait for conflicting jobs (recommended)',
            'help': 'When enabled, this job will wait for other jobs using the same source or destination to finish',
            'default': True
        }
    ]
}

# =============================================================================
# DESTINATION MANAGEMENT SCHEMAS
# =============================================================================

# Destination form schema for add/edit destination forms
DESTINATION_SCHEMA = {
    'display_name': 'Destination Configuration',
    'description': 'Configure destination connection details and storage type',
    'fields': [
        {
            'name': 'friendly_name',
            'type': 'text',
            'label': 'Friendly Name',
            'help': 'Display name for this destination (e.g. "My NAS", "Cloud Storage")',
            'placeholder': 'My Destination',
            'required': True,
            'max_length': 100
        },
        {
            'name': 'dest_type',
            'type': 'select',
            'label': 'Destination Type',
            'help': 'Type of destination storage',
            'required': True,
            'options': [
                {'value': 'rsync', 'label': 'Rsync (SSH)'},
                {'value': 'rsyncd', 'label': 'Rsync Daemon'},
                {'value': 'restic', 'label': 'Restic Repository'}
            ]
        },
        {
            'name': 'hostname',
            'type': 'text',
            'label': 'Hostname',
            'help': 'Hostname or IP address of the destination server',
            'placeholder': 'server.example.com',
            'required': True
        },
        {
            'name': 'port',
            'type': 'number',
            'label': 'Port',
            'help': 'Port number (auto-filled based on type)',
            'required': True,
            'min': 1,
            'max': 65535
        }
    ]
}

# Destination validation result schema
DESTINATION_VALIDATION_SCHEMA = {
    'display_name': 'Destination Validation',
    'description': 'Destination connectivity validation and capability detection results',
    'fields': [
        {
            'name': 'connection_success',
            'type': 'status',
            'label': 'Connection',
            'help': 'Whether destination connection was successful'
        },
        {
            'name': 'uri_generated',
            'type': 'text',
            'label': 'Generated URI',
            'help': 'Auto-generated URI for this destination configuration'
        },
        {
            'name': 'validation_message',
            'type': 'text',
            'label': 'Validation Details',
            'help': 'Additional details about the validation process'
        }
    ]
}

# =============================================================================
# SSH ORIGIN MANAGEMENT SCHEMAS
# =============================================================================

# SSH origin form schema for add/edit origin forms
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
            'label': 'Use Highball SSH key (recommended)',
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
        },
        {
            'name': 'ssh_pubkey',
            'type': 'textarea',
            'label': 'SSH Public Key',
            'help': 'Your SSH public key (ssh-rsa, ssh-ed25519, etc.)',
            'placeholder': 'ssh-rsa AAAAB3NzaC1yc2EAAAA...',
            'rows': 3,
            'conditional': {
                'show_when': 'ssh_highball',
                'value': False
            }
        },
        {
            'name': 'requires_passphrase',
            'type': 'checkbox',
            'label': 'Requires passphrase',
            'help': 'Check if your private key requires a passphrase',
            'default': False,
            'conditional': {
                'show_when': 'ssh_highball',
                'value': False
            }
        },
        {
            'name': 'ssh_passphrase',
            'type': 'password',
            'label': 'SSH Key Passphrase',
            'help': 'Passphrase for your private SSH key',
            'placeholder': 'passphrase',
            'conditional': {
                'show_when': 'requires_passphrase',
                'value': True
            }
        }
    ]
}

# SSH origin validation result schema
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