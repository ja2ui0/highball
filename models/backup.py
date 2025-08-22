"""
Consolidated Backup Operations Module
Merges all backup provider logic into single module with clean class-based organization
Replaces: restic_runner.py, restic_repository_service.py, restic_argument_builder.py, 
         restic_content_analyzer.py, restic_maintenance_service.py
"""

import subprocess
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import tempfile
from functools import wraps
import shlex
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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
# COMMAND EXECUTION DATA STRUCTURES
# =============================================================================

class CommandInfo(BaseModel):
    """Information about built backup command"""
    exec_argv: List[str]
    log_cmd_str: str
    src_display: str
    dst_display: str

# =============================================================================
# BACKUP CONFIGURATION CLASSES
# =============================================================================

class BackupConfig:
    """Base configuration for backup operations"""
    
    def __init__(self, job_config: Dict[str, Any]):
        self.job_config = job_config
        self.job_name = job_config.get('job_name', 'unknown')
        self.source_config = job_config.get('source_config', {})
        self.dest_config = job_config.get('dest_config', {})
        self.source_type = job_config.get('source_type', 'local')
        self.dest_type = job_config.get('dest_type', 'local')
    
    @property
    def is_restic_backup(self) -> bool:
        """Check if this is a Restic backup job"""
        return self.dest_type == 'restic'
    
    @property
    def is_ssh_source(self) -> bool:
        """Check if source is SSH"""
        return self.source_type == 'ssh'
    
    @property
    def container_runtime(self) -> Optional[str]:
        """Get container runtime for SSH sources"""
        return self.source_config.get('container_runtime')

# =============================================================================
# RESTIC ARGUMENT BUILDER - Command construction
# =============================================================================

class ResticArgumentBuilder:
    """Builds Restic command arguments for various operations"""
    
    @staticmethod
    def build_backup_args(config: BackupConfig, dry_run: bool = False) -> List[str]:
        """Build backup command arguments"""
        args = ['backup']  # Add backup command
        
        # Source paths
        source_paths = config.source_config.get('source_paths', [])
        for path_config in source_paths:
            args.append(path_config['path'])
        
        # Exclude patterns only (restic doesn't support --include)
        for path_config in source_paths:
            for exclude in path_config.get('excludes', []):
                args.extend(['--exclude', exclude])
        
        # Additional options
        args.extend(['--verbose', '--json'])
        
        if dry_run:
            args.append('--dry-run')
        
        # Job name tag
        args.extend(['--tag', f'job:{config.job_name}'])
        args.extend(['--tag', f'hostname:{config.source_config.get("hostname", "localhost")}'])
        
        return args
    
    @staticmethod
    def build_list_args(repo_uri: str, filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """Build snapshot list command arguments"""
        args = ['-r', repo_uri, 'snapshots', '--json']
        
        if filters:
            if filters.get('job_name'):
                args.extend(['--tag', f'job:{filters["job_name"]}'])
            if filters.get('hostname'):
                args.extend(['--tag', f'hostname:{filters["hostname"]}'])
            if filters.get('latest'):
                args.append('--latest')
                args.append('1')
        
        return args
    
    @staticmethod
    def build_restore_args(repo_uri: str, snapshot_id: str, target_path: str, 
                          include_patterns: List[str] = None, dry_run: bool = False) -> List[str]:
        """Build restore command arguments"""
        args = ['-r', repo_uri, 'restore', snapshot_id, '--target', target_path]
        
        if include_patterns:
            for pattern in include_patterns:
                args.extend(['--include', pattern])
        
        if dry_run:
            args.append('--dry-run')
        
        args.extend(['--verbose', '--verify'])
        
        return args
    
    @staticmethod
    def build_maintenance_args(repo_uri: str, operation: str, config: Dict[str, Any] = None) -> List[str]:
        """Build maintenance operation arguments"""
        args = ['-r', repo_uri]
        
        if operation == 'forget':
            args.append('forget')
            if config:
                retention = config.get('retention_policy', {})
                if retention.get('keep_last'):
                    args.extend(['--keep-last', str(retention['keep_last'])])
                if retention.get('keep_hourly'):
                    args.extend(['--keep-hourly', str(retention['keep_hourly'])])
                if retention.get('keep_daily'):
                    args.extend(['--keep-daily', str(retention['keep_daily'])])
                if retention.get('keep_weekly'):
                    args.extend(['--keep-weekly', str(retention['keep_weekly'])])
                if retention.get('keep_monthly'):
                    args.extend(['--keep-monthly', str(retention['keep_monthly'])])
                if retention.get('keep_yearly'):
                    args.extend(['--keep-yearly', str(retention['keep_yearly'])])
            args.append('--prune')
            
        elif operation == 'check':
            args.append('check')
            if config and config.get('read_data_subset'):
                args.extend(['--read-data-subset', config['read_data_subset']])
                
        elif operation == 'prune':
            args.append('prune')
            
        return args
    
    @staticmethod
    def build_environment(dest_config: Dict[str, Any]) -> Dict[str, str]:
        """Build complete environment for restic operations with all credentials"""
        import os
        env = os.environ.copy()
        
        # Always required
        env['RESTIC_PASSWORD'] = dest_config['password']
        
        # Add S3 credentials if S3 repository
        if dest_config.get('repo_type') == 's3':
            if 's3_access_key' in dest_config:
                env['AWS_ACCESS_KEY_ID'] = dest_config['s3_access_key']
            if 's3_secret_key' in dest_config:
                env['AWS_SECRET_ACCESS_KEY'] = dest_config['s3_secret_key']
        
        # Future: Add other cloud provider credentials here
        # elif dest_config.get('repo_type') == 'azure':
        #     env['AZURE_ACCOUNT_NAME'] = dest_config.get('azure_account_name', '')
        #     env['AZURE_ACCOUNT_KEY'] = dest_config.get('azure_account_key', '')
        
        return env
    
    @staticmethod 
    def build_ssh_environment_flags(dest_config: Dict[str, Any]) -> List[str]:
        """Build environment flags for SSH container commands"""
        flags = []
        
        # Always required
        flags.extend(['-e', f'RESTIC_PASSWORD={dest_config["password"]}'])
        
        # Add S3 credentials if S3 repository
        if dest_config.get('repo_type') == 's3':
            if 's3_access_key' in dest_config:
                flags.extend(['-e', f'AWS_ACCESS_KEY_ID={dest_config["s3_access_key"]}'])
            if 's3_secret_key' in dest_config:
                flags.extend(['-e', f'AWS_SECRET_ACCESS_KEY={dest_config["s3_secret_key"]}'])
        
        # Future: Add other cloud provider credentials here
        # elif dest_config.get('repo_type') == 'azure':
        #     flags.extend(['-e', f'AZURE_ACCOUNT_NAME={dest_config.get("azure_account_name", "")}'])
        #     flags.extend(['-e', f'AZURE_ACCOUNT_KEY={dest_config.get("azure_account_key", "")}'])
        
        return flags

# =============================================================================
# RESTIC SERVICE ERROR HANDLING
# =============================================================================

def handle_restic_service_errors(operation_name: str):
    """Decorator to handle common restic service operation errors consistently"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Restic {operation_name} error: {e}")
                return {
                    'success': False,
                    'error': f'{operation_name} operation failed: {str(e)}'
                }
        return wrapper
    return decorator

# =============================================================================
# RESTIC REPOSITORY SERVICE - Repository operations
# =============================================================================

class ResticRepositoryService:
    """Handles Restic repository operations and management"""
    
    def __init__(self):
        self.command_builder = ResticArgumentBuilder()
        from services.execution import ResticExecutionService
        self.restic_executor = ResticExecutionService()
    
    def _validate_required_fields(self, dest_config: Dict[str, Any]) -> None:
        """Validate required fields exist or raise exception with actionable message"""
        from models.backup import DESTINATION_TYPE_SCHEMAS
        
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        for field in required_fields:
            if not dest_config.get(field):
                raise ValueError(f'{schema.get("display_name", "Restic")} repository missing {field}')
        
        # If we reach here, all validation passed
    
    @handle_restic_service_errors("repository access test")
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access and get status information"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Execute using unified ResticExecutionService
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=['snapshots', '--json'],
            source_config=source_config,
            operation_type='ui',
            timeout=30
        )
        
        if result.returncode == 0:
            # Repository exists and is accessible
            try:
                snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                snapshot_count = len(snapshots)
                
                latest_backup = None
                if snapshots:
                    # Get most recent snapshot
                    latest_snapshot = max(snapshots, key=lambda s: s['time'])
                    latest_backup = latest_snapshot['time']
                
                return {
                    'success': True,
                    'repository_status': 'existing' if snapshot_count > 0 else 'empty',
                    'snapshot_count': snapshot_count,
                    'latest_backup': latest_backup,
                    'repository_uri': repo_uri
                }
            except json.JSONDecodeError:
                return {
                    'success': True,
                    'repository_status': 'empty',
                    'snapshot_count': 0,
                    'repository_uri': repo_uri
                }
            else:
                # Check if repository doesn't exist vs other error
                if 'unable to open config file' in result.stderr or 'repository does not exist' in result.stderr:
                    return {
                        'success': False,
                        'error': 'Repository does not exist - needs initialization',
                        'needs_init': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Repository access failed: {result.stderr}'
                    }
    
    @handle_restic_service_errors("repository initialization")
    def initialize_repository(self, dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Execute using unified ResticExecutionService
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=['init'],
            source_config=source_config,
            operation_type='init',
            timeout=60
        )
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': 'Repository initialized successfully'
            }
        else:
            return {
                'success': False,
                'error': f'Repository initialization failed: {result.stderr}'
            }

    def run_backup_unified(self, dest_config: Dict[str, Any], source_config: Dict[str, Any], backup_args: List[str]) -> Dict[str, Any]:
        """Run backup using unified ResticExecutionService (supports same_as_origin)"""
        try:
            # Execute using unified ResticExecutionService
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=backup_args,
                source_config=source_config,
                operation_type='backup'
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Backup completed successfully',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': f'Backup failed: {result.stderr}',
                    'output': result.stdout
                }
                
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return {
                'success': False,
                'error': f'Backup execution failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot listing")
    def list_snapshots(self, dest_config: Dict[str, Any], filters: Dict[str, Any] = None, source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List repository snapshots with optional filtering"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Build command args
        args = self.command_builder.build_list_args(repo_uri, filters)
        # Remove 'restic' and repo args since ResticExecutionService handles them
        command_args = []
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if arg == '-r':
                skip_next = True  # skip the repo URI
                continue
            command_args.append(arg)
        
        # Execute using unified ResticExecutionService  
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=command_args,
            source_config=source_config,
            operation_type='ui',
            timeout=30
        )
        
        if result.returncode == 0:
                try:
                    raw_snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    # Format snapshots for backup browser expectations
                    formatted_snapshots = []
                    for snapshot in raw_snapshots:
                        formatted_snapshot = {
                            'full_id': snapshot.get('id', ''),
                            'id': snapshot.get('short_id', snapshot.get('id', '')[:8] if snapshot.get('id') else ''),
                            'time': snapshot.get('time', ''),
                            'username': snapshot.get('username', ''),
                            'hostname': snapshot.get('hostname', ''),
                            'paths': snapshot.get('paths', []),
                            'summary': snapshot.get('summary', {}),
                            'tree': snapshot.get('tree', ''),
                            'program_version': snapshot.get('program_version', '')
                        }
                        formatted_snapshots.append(formatted_snapshot)
                    
                    return {
                        'success': True,
                        'snapshots': formatted_snapshots,
                        'count': len(formatted_snapshots)
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'snapshots': [],
                        'count': 0
                    }
        else:
            return {
                'success': False,
                'error': f'Failed to list snapshots: {result.stderr}'
            }
    
    @handle_restic_service_errors("SSH snapshot listing")
    def list_snapshots_with_ssh(self, dest_config: Dict[str, Any], source_config: Dict[str, Any], filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List snapshots with SSH execution support (like working code)"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Check if we should use SSH execution
        # For same_as_origin repositories, always use SSH (repository is on origin host)
        if (dest_config.get('repo_type') == 'same_as_origin' or 
            (source_config and source_config.get('hostname') and source_config.get('username'))):
            return self._list_snapshots_via_ssh(repo_uri, password, source_config, dest_config)
        else:
            # Fall back to local execution
            return self.list_snapshots(dest_config, filters)
    
    def _execute_template_variables(self, variables: Dict[str, str], context: Dict[str, Any]) -> Dict[str, str]:
        """Execute template variable transformations"""
        resolved = {}
        for var_name, template in variables.items():
            if template.startswith('remove_prefix '):
                # Format: "remove_prefix rest: {repo_uri}"
                parts = template.split(' ', 2)
                prefix = parts[1]
                source_var = parts[2].strip('{}')
                source_value = context.get(source_var, '')
                resolved[var_name] = source_value[len(prefix):] if source_value.startswith(prefix) else source_value
            elif template.startswith('dirname '):
                # Format: "dirname {local_path}"
                source_var = template.split(' ', 1)[1].strip('{}')
                source_value = context.get(source_var, '')
                from pathlib import Path
                resolved[var_name] = str(Path(source_value).parent)
            else:
                # Direct template substitution
                resolved[var_name] = template.format(**context)
        return resolved

    def _quick_repository_check(self, repo_uri: str, dest_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Schema-driven quick check for repository accessibility"""
        repo_type = dest_config.get('repo_type')
        
        if not repo_type or repo_type not in RESTIC_REPOSITORY_TYPE_SCHEMAS:
            return True, "Unknown repository type, skipping check"
        
        schema = RESTIC_REPOSITORY_TYPE_SCHEMAS[repo_type]
        quick_check = schema.get('quick_check')
        
        if not quick_check:
            return True, "No quick check defined for this repository type"
        
        try:
            # Prepare context with repo_uri and all dest_config fields
            context = dict(dest_config)
            context['repo_uri'] = repo_uri
            
            # Check if we should skip due to empty required fields
            skip_if_empty = quick_check.get('skip_if_empty', [])
            for field in skip_if_empty:
                if not context.get(field):
                    return True, f"Skipping check: {field} not specified"
            
            # Execute template variables if defined
            variables = quick_check.get('variables', {})
            if variables:
                resolved_vars = self._execute_template_variables(variables, context)
                context.update(resolved_vars)
            
            # Build command with template substitution
            command_template = quick_check['command']
            command = [arg.format(**context) for arg in command_template]
            
            # Prepare environment variables
            env = os.environ.copy()
            env_template = quick_check.get('env', {})
            for env_key, env_value in env_template.items():
                env[env_key] = env_value.format(**context)
            
            # Execute command
            timeout = quick_check.get('timeout', 10)
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
            
            # Check expected results
            if 'expected_returncode' in quick_check:
                expected_code = quick_check['expected_returncode']
                success = result.returncode == expected_code
                if success:
                    return success, f"Command returned {result.returncode} (expected: {expected_code})"
                else:
                    error_details = f"Command returned {result.returncode} (expected: {expected_code})"
                    if result.stderr:
                        error_details += f" - stderr: {result.stderr.strip()}"
                    if result.stdout:
                        error_details += f" - stdout: {result.stdout.strip()}"
                    return success, error_details
            
            elif 'expected_stdout' in quick_check:
                expected_out = quick_check['expected_stdout']
                actual_out = result.stdout.strip()
                success = actual_out == expected_out
                return success, f"Output: '{actual_out}' (expected: '{expected_out}')"
            
            else:
                # Default: success if returncode is 0
                success = result.returncode == 0
                return success, f"Command {'succeeded' if success else 'failed'} (code: {result.returncode})"
                
        except subprocess.TimeoutExpired:
            return False, f"Quick check timed out after {quick_check.get('timeout', 10)}s"
        except Exception as e:
            return False, f"Quick check failed: {str(e)}"

    def _list_snapshots_via_ssh(self, repo_uri: str, password: str, source_config: Dict[str, Any], dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """List snapshots via SSH execution using unified ResticExecutionService"""
        import json
        
        # Quick pre-check using schema-driven approach
        check_success, check_message = self._quick_repository_check(repo_uri, dest_config)
        if not check_success:
            return {
                'success': False,
                'error': f'Repository endpoint check failed: {check_message}'
            }
        
        # Use ResticExecutionService for unified SSH execution (supports same_as_origin volume mounting)
        try:
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=['snapshots', '--json'],
                source_config=source_config,
                operation_type='ui',  # UI operation but uses SSH for same_as_origin
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    raw_snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    # Format snapshots for backup browser expectations
                    formatted_snapshots = []
                    for snapshot in raw_snapshots:
                        formatted_snapshot = {
                            'full_id': snapshot.get('id', ''),
                            'id': snapshot.get('short_id', snapshot.get('id', '')[:8] if snapshot.get('id') else ''),
                            'time': snapshot.get('time', ''),
                            'username': snapshot.get('username', ''),
                            'hostname': snapshot.get('hostname', ''),
                            'paths': snapshot.get('paths', []),
                            'summary': snapshot.get('summary', {}),
                            'tree': snapshot.get('tree', ''),
                            'program_version': snapshot.get('program_version', '')
                        }
                        formatted_snapshots.append(formatted_snapshot)
                    
                    return {
                        'success': True,
                        'snapshots': formatted_snapshots,
                        'count': len(formatted_snapshots)
                    }
                except json.JSONDecodeError:
                    return {
                        'success': False,
                        'error': 'Invalid JSON response from restic'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Restic command failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Snapshot listing timed out'
            }
        except Exception as e:
            logger.error(f"SSH execution error: {e}")
            return {
                'success': False,
                'error': f'SSH execution failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot statistics")
    def get_snapshot_statistics(self, dest_config: Dict[str, Any], snapshot_id: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Always execute locally for UI operations per working pattern
        env = ResticArgumentBuilder.build_environment(dest_config)
        
        # Get snapshot statistics using local restic
        cmd = ['restic', '-r', repo_uri, 'stats', snapshot_id, '--json']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            try:
                stats = json.loads(result.stdout) if result.stdout.strip() else {}
                return {
                    'success': True,
                    'stats': stats,  # backup browser expects 'stats' not 'statistics'
                    'snapshot_id': snapshot_id
                }
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Invalid JSON response from restic stats'
                }
        else:
            return {
                'success': False,
                'error': f'Stats command failed: {result.stderr}'
            }
    
    @handle_restic_service_errors("repository unlock")
    def unlock_repository(self, dest_config: Dict[str, Any], source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Unlock a restic repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Check if we should use SSH execution (same pattern as other operations)
        if source_config and source_config.get('hostname') and source_config.get('username'):
            return self._unlock_repository_via_ssh(dest_config, source_config)
        else:
            # Fall back to local execution
            return self._unlock_repository_local(dest_config)
    
    def _unlock_repository_local(self, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Unlock repository using local restic execution"""
        try:
            repo_uri = dest_config.get('repo_uri')
            
            # Set environment using centralized builder
            env = ResticArgumentBuilder.build_environment(dest_config)
            
            # Build unlock command
            cmd = ['restic', '-r', repo_uri, 'unlock']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository unlocked successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Unlock failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Repository unlock timed out'
            }
        except Exception as e:
            logger.error(f"Local unlock error: {e}")
            return {
                'success': False,
                'error': f'Local unlock failed: {str(e)}'
            }
    
    def _unlock_repository_via_ssh(self, dest_config: Dict[str, Any], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Unlock repository via SSH execution (for consistency with other operations)"""
        try:
            repo_uri = dest_config.get('repo_uri')
            hostname = source_config.get('hostname')
            username = source_config.get('username')
            container_runtime = source_config.get('container_runtime', 'docker')
            
            # Build SSH + container command with proper credentials
            env_flags = ResticArgumentBuilder.build_ssh_environment_flags(dest_config)
            cmd = [
                'ssh', f'{username}@{hostname}',
                container_runtime, 'run', '--rm'
            ] + env_flags + [
                'restic/restic:0.18.0',
                '-r', repo_uri, 'unlock'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository unlocked successfully via SSH'
                }
            else:
                return {
                    'success': False,
                    'error': f'SSH unlock failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'SSH unlock timed out'
            }
        except Exception as e:
            logger.error(f"SSH unlock error: {e}")
            return {
                'success': False,
                'error': f'SSH unlock failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot directory browsing")
    def browse_snapshot_directory(self, dest_config: Dict[str, Any], snapshot_id: str, path: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Browse directory contents in a specific snapshot"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Always execute locally for UI operations per working pattern
        env = ResticArgumentBuilder.build_environment(dest_config)
        
        # Clean path for restic ls command
        clean_path = path.strip('/') if path and path != '/' else ''
        
        # List directory contents using local restic (EXACT working command)
        cmd = ['restic', '-r', repo_uri, 'ls', snapshot_id, '--json', path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            # Parse using EXACT working method
            return self._parse_directory_listing(result.stdout, path)
        else:
            return {
                'success': False,
                'error': f'Directory listing failed: {result.stderr}'
            }
    
    def _parse_directory_listing(self, json_output: str, current_path: str) -> Dict[str, Any]:
        """Parse restic ls JSON output into directory listing (EXACT copy from working version)"""
        try:
            lines = json_output.strip().split('\n')
            items = []
            
            # Add parent directory entry if not at root
            if current_path and current_path != '/':
                parent_path = os.path.dirname(current_path) if current_path != '/' else '/'
                items.append({
                    'name': '..',
                    'type': 'parent',
                    'path': parent_path,
                    'size': None
                })
            
            # Parse each JSON line 
            for line in lines:
                if not line.strip():
                    continue
                    
                try:
                    item = json.loads(line)
                    name = item.get('name', '')
                    item_type = item.get('type', 'file')
                    size = item.get('size')
                    full_path = item.get('path', os.path.join(current_path, name))
                    
                    # Skip the current directory entry, empty names, and self-references
                    if (name == '.' or name == current_path or name == '' or 
                        full_path == current_path or 
                        (current_path != '/' and name == os.path.basename(current_path))):
                        continue
                    
                    items.append({
                        'name': name,
                        'type': 'directory' if item_type == 'dir' else 'file',
                        'path': full_path,
                        'size': size
                    })
                    
                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
            
            return {
                'success': True,
                'contents': items,
                'current_path': current_path,
                'total_items': len(items)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to parse directory listing: {str(e)}'
            }

# =============================================================================
# RESTIC CONTENT ANALYZER - Repository content analysis
# =============================================================================

class ResticContentAnalyzer:
    """Analyzes Restic repository content and provides insights"""
    
    def __init__(self):
        self.repository_service = ResticRepositoryService()
    
    def analyze_repository_content(self, dest_config: Dict[str, Any], job_name: str = None) -> Dict[str, Any]:
        """Analyze repository content for a specific job"""
        try:
            # Get snapshots for this job
            filters = {'job_name': job_name} if job_name else None
            snapshots_result = self.repository_service.list_snapshots(dest_config, filters)
            
            if not snapshots_result['success']:
                return snapshots_result
            
            snapshots = snapshots_result['snapshots']
            
            if not snapshots:
                return {
                    'success': True,
                    'analysis': {
                        'snapshot_count': 0,
                        'size_stats': None,
                        'frequency_stats': None,
                        'latest_snapshot': None
                    }
                }
            
            # Analyze snapshot metadata
            analysis = {
                'snapshot_count': len(snapshots),
                'size_stats': self._analyze_size_trends(snapshots),
                'frequency_stats': self._analyze_backup_frequency(snapshots),
                'latest_snapshot': self._get_latest_snapshot_info(snapshots)
            }
            
            return {
                'success': True,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
            return {
                'success': False,
                'error': f'Content analysis failed: {str(e)}'
            }
    
    def _analyze_size_trends(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze backup size trends"""
        if not snapshots:
            return None
        
        sizes = []
        for snapshot in snapshots:
            if 'summary' in snapshot and 'total_bytes_processed' in snapshot['summary']:
                sizes.append(snapshot['summary']['total_bytes_processed'])
        
        if not sizes:
            return None
        
        return {
            'average_size': sum(sizes) / len(sizes),
            'min_size': min(sizes),
            'max_size': max(sizes),
            'latest_size': sizes[-1] if sizes else 0
        }
    
    def _analyze_backup_frequency(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze backup frequency patterns"""
        if len(snapshots) < 2:
            return None
        
        # Sort by time
        sorted_snapshots = sorted(snapshots, key=lambda s: s['time'])
        
        intervals = []
        for i in range(1, len(sorted_snapshots)):
            prev_time = datetime.fromisoformat(sorted_snapshots[i-1]['time'].replace('Z', '+00:00'))
            curr_time = datetime.fromisoformat(sorted_snapshots[i]['time'].replace('Z', '+00:00'))
            intervals.append((curr_time - prev_time).total_seconds())
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            return {
                'average_interval_hours': avg_interval / 3600,
                'min_interval_hours': min(intervals) / 3600,
                'max_interval_hours': max(intervals) / 3600
            }
        
        return None
    
    def _get_latest_snapshot_info(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get detailed info about the latest snapshot"""
        if not snapshots:
            return None
        
        latest = max(snapshots, key=lambda s: s['time'])
        
        return {
            'id': latest.get('short_id', latest.get('id', 'unknown')),
            'time': latest['time'],
            'hostname': latest.get('hostname'),
            'paths': latest.get('paths', []),
            'tags': latest.get('tags', [])
        }

# =============================================================================
# RESTIC RUNNER - Backup execution
# =============================================================================

class ResticRunner:
    """Executes Restic backup operations with proper environment and error handling"""
    
    def __init__(self):
        self.argument_builder = ResticArgumentBuilder()
        self.repository_service = ResticRepositoryService()
    
    def run_backup(self, config: BackupConfig, dry_run: bool = False) -> Dict[str, Any]:
        """Execute Restic backup with comprehensive error handling"""
        try:
            # Validate configuration
            if not config.is_restic_backup:
                return {
                    'success': False,
                    'error': 'Not a Restic backup configuration'
                }
            
            # Build backup command
            backup_args = self.argument_builder.build_backup_args(config, dry_run)
            
            # Determine execution context (local vs SSH with container)
            if config.is_ssh_source and config.container_runtime:
                return self._run_container_backup(config, backup_args, dry_run)
            else:
                return self._run_local_backup(config, backup_args, dry_run)
                
        except Exception as e:
            logger.error(f"Backup execution error: {e}")
            return {
                'success': False,
                'error': f'Backup execution failed: {str(e)}'
            }
    
    def _run_local_backup(self, config: BackupConfig, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup locally"""
        try:
            # Set environment using centralized builder
            env = ResticArgumentBuilder.build_environment(config.dest_config)
            
            # Execute backup
            cmd = ['restic', 'backup'] + backup_args
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
                env=env
            )
            
            return self._process_backup_result(result, dry_run)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Backup operation timeout (1 hour limit)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Local backup failed: {str(e)}'
            }
    
    def _run_container_backup(self, config: BackupConfig, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup using container on remote SSH host"""
        try:
            # Use existing container service for backup operations  
            from services.binaries import ContainerService
            from services.execution import ExecutionService
            
            container_service = ContainerService()
            exec_service = ExecutionService()
            
            # Extract configuration
            repository_url = config.dest_config['repo_uri']
            source_paths = [path['path'] for path in config.source_config.get('source_paths', [])]
            environment_vars = ResticArgumentBuilder.build_environment(config.dest_config)
            
            # Add dry-run to backup args if needed
            if dry_run and '--dry-run' not in backup_args:
                backup_args = backup_args + ['--dry-run']
            
            # Build container command using existing service
            container_command = container_service.build_backup_container_command(
                repository_url=repository_url,
                source_paths=source_paths,
                environment_vars=environment_vars,
                backup_args=backup_args
            )
            
            # Execute via SSH using existing execution service
            source_config = config.source_config
            result = exec_service.execute_ssh_command(
                hostname=source_config['hostname'],
                username=source_config['username'],
                command=container_command
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Container backup completed successfully',
                    'output': result.stdout,
                    'dry_run': dry_run
                }
            else:
                return {
                    'success': False,
                    'error': f'Container backup failed: {result.stderr}',
                    'output': result.stdout
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Container backup failed: {str(e)}'
            }
    
    def _process_backup_result(self, result: subprocess.CompletedProcess, dry_run: bool) -> Dict[str, Any]:
        """Process backup command result"""
        if result.returncode == 0:
            # Parse JSON output if available
            backup_stats = self._parse_backup_output(result.stdout)
            
            return {
                'success': True,
                'message': 'Backup completed successfully' if not dry_run else 'Dry run completed successfully',
                'stats': backup_stats,
                'output': result.stdout,
                'dry_run': dry_run
            }
        else:
            return {
                'success': False,
                'error': f'Backup failed: {result.stderr}',
                'output': result.stdout,
                'return_code': result.returncode
            }
    
    def _parse_backup_output(self, output: str) -> Dict[str, Any]:
        """Parse JSON output from Restic backup"""
        try:
            lines = output.strip().split('\n')
            for line in reversed(lines):  # Start from the end
                if line.strip().startswith('{'):
                    data = json.loads(line)
                    if data.get('message_type') == 'summary':
                        return {
                            'files_new': data.get('files_new', 0),
                            'files_changed': data.get('files_changed', 0),
                            'files_unmodified': data.get('files_unmodified', 0),
                            'dirs_new': data.get('dirs_new', 0),
                            'dirs_changed': data.get('dirs_changed', 0),
                            'data_added': data.get('data_added', 0),
                            'total_bytes_processed': data.get('total_bytes_processed', 0)
                        }
        except (json.JSONDecodeError, KeyError):
            pass
        
        return {}

# =============================================================================
# RESTIC MAINTENANCE SERVICE - Repository maintenance
# =============================================================================

class ResticMaintenanceService:
    """Handles Restic repository maintenance operations"""
    
    def __init__(self):
        self.argument_builder = ResticArgumentBuilder()
    
    @handle_restic_service_errors("maintenance operation")
    def run_maintenance_operation(self, dest_config: Dict[str, Any], operation: str, 
                                config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run maintenance operation on repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Set environment using centralized builder
        env = ResticArgumentBuilder.build_environment(dest_config)
        
        # Build command
        args = self.argument_builder.build_maintenance_args(repo_uri, operation, config)
        cmd = ['restic'] + args
        
        # Execute maintenance operation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
            env=env
        )
        
        if result.returncode == 0:
            return {
                'success': True,
                'operation': operation,
                'message': f'{operation.capitalize()} operation completed successfully',
                'output': result.stdout
            }
        else:
            return {
                'success': False,
                'operation': operation,
                'error': f'{operation.capitalize()} operation failed: {result.stderr}',
                'output': result.stdout
            }

# =============================================================================
# UNIFIED BACKUP SERVICE - Main interface
# =============================================================================

class BackupService:
    """Unified backup service - single entry point for all backup operations"""
    
    def __init__(self):
        self.restic_runner = ResticRunner()
        self.repository_service = ResticRepositoryService()
        self.content_analyzer = ResticContentAnalyzer()
        self.maintenance_service = ResticMaintenanceService()
    
    def execute_backup(self, job_config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Execute backup operation using unified ResticExecutionService"""
        config = BackupConfig(job_config)
        
        if config.is_restic_backup:
            # Use ResticRepositoryService which has ResticExecutionService integration
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Build backup arguments using the existing argument builder
            backup_args = self.restic_runner.argument_builder.build_backup_args(config, dry_run)
            
            # Use ResticRepositoryService for proper SSH execution
            return self.repository_service.run_backup_unified(dest_config, source_config, backup_args)
        else:
            return {
                'success': False,
                'error': f'Backup type {config.dest_type} not supported by unified service'
            }
    
    def test_repository(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access"""
        return self.repository_service.test_repository_access(job_config)
    
    def initialize_repository(self, dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initialize new repository"""
        return self.repository_service.initialize_repository(dest_config, source_config)
    
    def list_snapshots(self, dest_config: Dict[str, Any], filters: Dict[str, Any] = None, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """List repository snapshots with SSH support"""
        # Pass source_config to repository service for SSH execution
        if hasattr(self.repository_service, 'list_snapshots_with_ssh'):
            return self.repository_service.list_snapshots_with_ssh(dest_config, source_config, filters)
        else:
            return self.repository_service.list_snapshots(dest_config, filters)
    
    def analyze_content(self, dest_config: Dict[str, Any], job_name: str = None) -> Dict[str, Any]:
        """Analyze repository content"""
        return self.content_analyzer.analyze_repository_content(dest_config, job_name)
    
    def run_maintenance(self, dest_config: Dict[str, Any], operation: str, 
                       config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run maintenance operation"""
        return self.maintenance_service.run_maintenance_operation(dest_config, operation, config)
    
    def get_snapshot_statistics(self, dest_config: Dict[str, Any], snapshot_id: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        return self.repository_service.get_snapshot_statistics(dest_config, snapshot_id, source_config)
    
    def unlock_repository(self, dest_config: Dict[str, Any], source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Unlock a locked restic repository"""
        return self.repository_service.unlock_repository(dest_config, source_config)
    
    def browse_snapshot_directory(self, dest_config: Dict[str, Any], snapshot_id: str, path: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Browse directory contents in a specific snapshot"""
        return self.repository_service.browse_snapshot_directory(dest_config, snapshot_id, path, source_config)

# Export the unified service as the main interface
backup_service = BackupService()