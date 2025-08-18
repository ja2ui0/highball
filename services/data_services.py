"""
Unified Data Services
Consolidates form data building and snapshot introspection
Replaces: job_form_data_builder.py, snapshot_introspection_service.py
"""
from typing import Dict, List, Optional, Any
from models.forms import JobFormData, SourceConfig, DestConfig, ResticConfig, NotificationConfig
from services.execution import ExecutionService


# =============================================================================
# **FORM DATA BUILDING CONCERN** - JobFormData creation and population
# =============================================================================

class JobFormDataBuilder:
    """Form data building - ONLY handles JobFormData creation from various sources"""
    
    @classmethod
    def from_job_config(cls, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Building concern: create JobFormData from existing job configuration"""
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        
        # Parse schedule
        schedule_type, cron_pattern = cls._parse_schedule(job_config.get('schedule', 'manual'))
        
        # Build structured configuration
        source = SourceConfig(
            source_type=job_config.get('source_type', ''),
            local_path=source_config.get('path', ''),
            ssh_hostname=source_config.get('hostname', ''),
            ssh_username=source_config.get('username', ''),
            ssh_path=source_config.get('path', ''),
            source_paths=source_config.get('source_paths', [])  # Multi-path support
        )
        
        dest = DestConfig(
            dest_type=job_config.get('dest_type', ''),
            local_path=dest_config.get('path', ''),
            ssh_hostname=dest_config.get('hostname', ''),
            ssh_username=dest_config.get('username', ''),
            ssh_path=dest_config.get('path', ''),
            rsyncd_hostname=dest_config.get('hostname', ''),
            rsyncd_share=dest_config.get('share', ''),
            rsync_options=dest_config.get('rsync_options', ''),
        )
        
        # Build Restic config only if needed
        restic = cls._build_restic_config(job_config.get('dest_type'), dest_config)
        
        # Build notification configs
        notifications = cls._build_notification_configs(job_config.get('notifications', []))
        
        return JobFormData(
            job_name=job_name,
            source_config=source,
            dest_config=dest,
            restic_config=restic,
            schedule=job_config.get('schedule', 'manual'),
            enabled=job_config.get('enabled', True),
            respect_conflicts=job_config.get('respect_conflicts', True),
            auto_maintenance=job_config.get('auto_maintenance', True),
            notifications=notifications
        )
    
    @classmethod
    def from_form_data(cls, form_data: Dict[str, Any]) -> JobFormData:
        """Building concern: create JobFormData from form submission"""
        # Parse schedule
        schedule = form_data.get('schedule', 'manual')
        if schedule == 'cron':
            cron_pattern = form_data.get('cron_pattern', '').strip()
            if cron_pattern:
                schedule = cron_pattern
        
        return JobFormData(
            job_name=form_data.get('job_name', ''),
            schedule=schedule,
            enabled=form_data.get('enabled', False),
            respect_conflicts=form_data.get('respect_conflicts', True),
            auto_maintenance=form_data.get('auto_maintenance', True)
        )
    
    @classmethod
    def _parse_schedule(cls, schedule_value: str) -> tuple:
        """Building concern: parse schedule into type and pattern"""
        if not schedule_value or schedule_value in ['manual', 'hourly', 'daily', 'weekly', 'monthly']:
            return schedule_value or 'manual', ''
        else:
            # Custom cron pattern
            return 'cron', schedule_value
    
    @classmethod
    def _build_restic_config(cls, dest_type: str, dest_config: Dict[str, Any]) -> ResticConfig:
        """Building concern: build Restic configuration from destination config"""
        if dest_type != 'restic':
            return ResticConfig()
        
        # Extract Restic-specific configuration
        return ResticConfig(
            repo_type=dest_config.get('repo_type', ''),
            password=dest_config.get('password', ''),
            local_path=dest_config.get('local_path', ''),
            rest_hostname=dest_config.get('rest_hostname', ''),
            rest_port=dest_config.get('rest_port', '8000'),
            rest_path=dest_config.get('rest_path', ''),
            rest_use_https=dest_config.get('rest_use_https', True),
            s3_bucket=dest_config.get('s3_bucket', ''),
            s3_region=dest_config.get('s3_region', ''),
            s3_prefix=dest_config.get('s3_prefix', ''),
            sftp_hostname=dest_config.get('sftp_hostname', ''),
            sftp_path=dest_config.get('sftp_path', ''),
            rclone_config=dest_config.get('rclone_config', '')
        )
    
    @classmethod
    def _build_notification_configs(cls, notifications: List[Dict[str, Any]]) -> List[NotificationConfig]:
        """Building concern: build notification configurations"""
        configs = []
        for notification in notifications:
            config = NotificationConfig(
                provider_type=notification.get('provider', ''),
                notify_on_success=notification.get('notify_on_success', False),
                notify_on_failure=notification.get('notify_on_failure', True),
                success_message=notification.get('success_message', ''),
                failure_message=notification.get('failure_message', '')
            )
            configs.append(config)
        return configs


# =============================================================================
# **SNAPSHOT INTROSPECTION CONCERN** - Discovery of paths and metadata from snapshots
# =============================================================================

class SnapshotIntrospectionService:
    """Snapshot introspection - ONLY handles discovery of snapshot contents and metadata"""
    
    def __init__(self):
        self.executor = ExecutionService()
        self.timeout = 30  # seconds for introspection commands
    
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """Introspection concern: get original source paths that were backed up in a snapshot"""
        try:
            if ssh_config:
                # Execute via SSH using container (restic not installed on remote hosts)
                result = self._execute_via_ssh(
                    snapshot_id, repository_url, environment_vars,
                    ssh_config, container_runtime
                )
            else:
                # Execute locally
                result = self._execute_locally(
                    snapshot_id, repository_url, environment_vars
                )
            
            if result.get('success'):
                return self._parse_snapshot_paths(result.get('stdout', ''))
            else:
                print(f"WARNING: Failed to introspect snapshot {snapshot_id}: {result.get('error')}")
                return []
                
        except Exception as e:
            print(f"ERROR: Snapshot introspection failed for {snapshot_id}: {str(e)}")
            return []
    
    def get_snapshot_metadata(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> Dict[str, Any]:
        """Introspection concern: get detailed metadata for a snapshot"""
        try:
            # Build show command for metadata
            show_command = [
                container_runtime, 'run', '--rm',
                '-e', f'RESTIC_PASSWORD={environment_vars.get("RESTIC_PASSWORD", "")}',
                'restic/restic:0.18.0',
                '-r', repository_url,
                'snapshots', '--json', snapshot_id
            ]
            
            if ssh_config:
                result = self.executor.execute_ssh_command(
                    ssh_config['hostname'],
                    ssh_config['username'],
                    show_command
                )
            else:
                result = self.executor.execute_local_command(show_command)
            
            if result.returncode == 0:
                import json
                snapshots = json.loads(result.stdout)
                if snapshots and len(snapshots) > 0:
                    return snapshots[0]
            
            return {}
            
        except Exception as e:
            print(f"ERROR: Snapshot metadata retrieval failed for {snapshot_id}: {str(e)}")
            return {}
    
    def _execute_via_ssh(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Dict[str, str],
        container_runtime: str
    ) -> Dict[str, Any]:
        """Introspection concern: execute snapshot command via SSH using container"""
        try:
            # Build container command for listing snapshot root paths
            list_command = [
                container_runtime, 'run', '--rm',
                '-e', f'RESTIC_PASSWORD={environment_vars.get("RESTIC_PASSWORD", "")}',
                'restic/restic:0.18.0',
                '-r', repository_url,
                'ls', snapshot_id, '--long'
            ]
            
            result = self.executor.execute_ssh_command(
                ssh_config['hostname'],
                ssh_config['username'],
                list_command
            )
            
            if result.returncode == 0:
                return {'success': True, 'stdout': result.stdout}
            else:
                return {'success': False, 'error': result.stderr}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_locally(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str]
    ) -> Dict[str, Any]:
        """Introspection concern: execute snapshot command locally"""
        try:
            # Use restic directly for local execution
            list_command = [
                'restic', '-r', repository_url,
                'ls', snapshot_id, '--long'
            ]
            
            result = self.executor.execute_local_command(
                list_command,
                environment_vars=environment_vars
            )
            
            if result.returncode == 0:
                return {'success': True, 'stdout': result.stdout}
            else:
                return {'success': False, 'error': result.stderr}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _parse_snapshot_paths(self, ls_output: str) -> List[str]:
        """Introspection concern: parse restic ls output to extract original source paths"""
        paths = []
        lines = ls_output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Parse restic ls --long output
            # Format: permissions size date time path
            parts = line.split()
            if len(parts) >= 5:
                # The path is the last part
                path = ' '.join(parts[4:])
                
                # Only include top-level directories as source paths
                if path and not path.startswith('.'):
                    # Remove leading slash and extract top-level directory
                    clean_path = path.lstrip('/')
                    if '/' in clean_path:
                        top_level = '/' + clean_path.split('/')[0]
                    else:
                        top_level = '/' + clean_path
                    
                    if top_level not in paths:
                        paths.append(top_level)
        
        return sorted(paths)


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates form building and introspection
# =============================================================================

class DataService:
    """Unified data service - ONLY coordinates form building and introspection concerns"""
    
    def __init__(self):
        self.form_builder = JobFormDataBuilder()
        self.introspection = SnapshotIntrospectionService()
    
    # **FORM BUILDING DELEGATION** - Pure delegation to building concern
    def build_job_form_data_from_config(self, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from job config"""
        return self.form_builder.from_job_config(job_name, job_config)
    
    def build_job_form_data_from_form(self, form_data: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from form submission"""
        return self.form_builder.from_form_data(form_data)
    
    # **INTROSPECTION DELEGATION** - Pure delegation to introspection concern
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """Delegation: get snapshot source paths"""
        return self.introspection.get_snapshot_source_paths(
            snapshot_id, repository_url, environment_vars, ssh_config, container_runtime
        )
    
    def get_snapshot_metadata(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> Dict[str, Any]:
        """Delegation: get snapshot metadata"""
        return self.introspection.get_snapshot_metadata(
            snapshot_id, repository_url, environment_vars, ssh_config, container_runtime
        )


# Legacy compatibility
job_form_data_builder = DataService()
snapshot_introspection_service = DataService()