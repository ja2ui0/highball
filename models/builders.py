"""
Backup Command Builders
Extracted from models/backup.py - contains command building logic for various backup operations
"""

from typing import List, Dict, Any, Optional


class ResticArgumentBuilder:
    """Builds Restic command arguments for various operations"""
    
    @staticmethod
    def build_backup_args(config, dry_run: bool = False) -> List[str]:
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