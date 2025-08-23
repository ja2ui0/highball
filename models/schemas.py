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

DESTINATION_TYPE_SCHEMAS = {
    'local': {
        'display_name': 'Local Path',
        'description': 'Store backups on local filesystem',
        'always_available': True,
        'requires': [],
        'fields': {
            'dest_path': {'config_key': 'path'}
        },
        'required_fields': ['path']
    },
    'ssh': {
        'display_name': 'Rsync (SSH)',
        'description': 'Remote backup using rsync over SSH',
        'always_available': True,
        'requires': ['rsync', 'ssh'],
        'fields': {
            'dest_hostname': {'config_key': 'hostname'},
            'dest_username': {'config_key': 'username'}, 
            'dest_path': {'config_key': 'dest_path'}
        },
        'required_fields': ['hostname', 'username', 'dest_path']
    },
    'rsyncd': {
        'display_name': 'Rsync Daemon',
        'description': 'Remote backup using rsync daemon protocol',
        'always_available': True,
        'requires': ['rsync'],
        'fields': {
            'rsyncd_hostname': {'config_key': 'hostname'},
            'rsyncd_share': {'config_key': 'share'}
        },
        'required_fields': ['hostname', 'share']
    },
    'restic': {
        'display_name': 'Restic Repository',
        'description': 'Encrypted, deduplicated backup repository',
        'always_available': False,  # depends on binary availability
        'requires': ['restic'],
        'requires_container_runtime': True,
        'availability_check': 'check_restic_availability',
        'fields': {
            'repo_type': {'config_key': 'repo_type', 'required': True},
            'repo_uri': {'config_key': 'repo_uri', 'required': True},
            'password': {'config_key': 'password', 'secret': True, 'env_var': 'RESTIC_PASSWORD'}
        },
        'required_fields': ['repo_type', 'repo_uri', 'password']
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
                'name': 'rest_hostname',
                'type': 'text',
                'label': 'REST Server Hostname',
                'help': 'Hostname or IP address of the REST server',
                'placeholder': 'rest-server.example.com',
                'required': True
            },
            {
                'name': 'rest_port',
                'type': 'number',
                'label': 'REST Server Port',
                'help': 'Port number (default: 8000)',
                'placeholder': '8000',
                'default': '8000',
                'min': 1,
                'max': 65535
            },
            {
                'name': 'rest_path',
                'type': 'text',
                'label': 'Repository Path',
                'help': 'Path to the repository on the REST server',
                'placeholder': '/my-backup-repo'
            },
            {
                'name': 'rest_use_root',
                'type': 'checkbox',
                'label': 'Use Repository Root',
                'help': 'Connect to repository served directly from server root (no additional path)',
                'default': False
            },
            {
                'name': 'rest_use_https',
                'type': 'checkbox',
                'label': 'Use HTTPS',
                'help': 'Use HTTPS instead of HTTP (recommended for production)',
                'default': False
            },
            {
                'name': 'rest_username',
                'type': 'text',
                'label': 'Username (Optional)',
                'help': 'HTTP Basic Auth username if server requires authentication',
                'placeholder': 'username'
            },
            {
                'name': 'rest_password',
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
                'name': 's3_bucket',
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
                'name': 's3_prefix',
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
                'name': 's3_region',
                'type': 'text',
                'label': 'AWS Region (optional)',
                'help': 'AWS region (defaults to us-east-1). Not required for non-AWS S3-compatible services like Cloudflare R2, MinIO',
                'placeholder': 'us-east-1',
                'required': False,
                'default': 'us-east-1'
            },
            {
                'name': 's3_access_key',
                'type': 'text',
                'label': 'Access Key ID',
                'help': 'AWS Access Key ID for authentication',
                'placeholder': 'AKIAIOSFODNN7EXAMPLE',
                'required': True,
                'secret': True,
                'env_var': 'S3_ACCESS_KEY_ID'
            },
            {
                'name': 's3_secret_key',
                'type': 'password',
                'label': 'Secret Access Key',
                'help': 'AWS Secret Access Key for authentication',
                'placeholder': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'required': True,
                'secret': True,
                'env_var': 'S3_SECRET_ACCESS_KEY'
            },
            {
                'name': 's3_endpoint',
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
                'name': 'sftp_hostname',
                'type': 'text',
                'label': 'SFTP Host',
                'help': 'SFTP server hostname',
                'placeholder': 'sftp.example.com',
                'required': True
            },
            {
                'name': 'sftp_username',
                'type': 'text',
                'label': 'SFTP Username',
                'help': 'Username for SFTP authentication',
                'placeholder': 'username',
                'required': True
            },
            {
                'name': 'sftp_path',
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
                'name': 'rclone_remote',
                'type': 'text',
                'label': 'rclone Remote',
                'help': 'rclone remote name (configure with "rclone config")',
                'placeholder': 'myremote',
                'required': True
            },
            {
                'name': 'rclone_path',
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
                'name': 'origin_repo_path',
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