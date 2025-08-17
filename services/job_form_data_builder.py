"""
Job Form Data Builder Service
Handles creation and population of JobFormData from various sources
"""
from typing import Dict, Any
from .form_data_service import JobFormData, SourceConfig, DestConfig, ResticConfig, MaintenanceConfig


class JobFormDataBuilder:
    """Builder for creating JobFormData from job configurations"""
    
    @classmethod
    def from_job_config(cls, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Create JobFormData from existing job configuration"""
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
        
        # Build maintenance config
        maintenance = cls._build_maintenance_config(job_config.get('maintenance_config', {}))
        
        return JobFormData(
            is_edit=True,
            job_name=job_name,
            source=source,
            dest=dest,
            restic=restic,
            maintenance=maintenance,
            schedule_type=schedule_type,
            cron_pattern=cron_pattern,
            includes='',  # Legacy field - includes/excludes now in source_paths
            excludes='',  # Legacy field - includes/excludes now in source_paths
            enabled=job_config.get('enabled', True),
            respect_conflicts=job_config.get('respect_conflicts', True),
            notifications=job_config.get('notifications', [])
        )
    
    @classmethod
    def from_form_submission(cls, form_data: Dict[str, Any]) -> JobFormData:
        """Create JobFormData from form submission to preserve user input on errors"""
        
        # Helper to safely get form values
        def get_form_value(key, default=''):
            values = form_data.get(key, [default])
            return values[0] if values else default
        
        # Parse source paths from arrays
        source_paths_raw = form_data.get('source_paths[]', [])
        source_includes_raw = form_data.get('source_includes[]', [])
        source_excludes_raw = form_data.get('source_excludes[]', [])
        
        source_paths = []
        for i, path in enumerate(source_paths_raw):
            path = path.strip()
            if not path:  # Skip empty paths
                continue
                
            includes = source_includes_raw[i] if i < len(source_includes_raw) else ''
            excludes = source_excludes_raw[i] if i < len(source_excludes_raw) else ''
            
            source_paths.append({
                'path': path,
                'includes': [line.strip() for line in includes.split('\n') if line.strip()],
                'excludes': [line.strip() for line in excludes.split('\n') if line.strip()]
            })
        
        # Build source config
        source = SourceConfig(
            source_type=get_form_value('source_type'),
            local_path=get_form_value('source_local_path'),
            ssh_hostname=get_form_value('source_ssh_hostname'),
            ssh_username=get_form_value('source_ssh_username'),
            ssh_path=get_form_value('source_ssh_path'),
            source_paths=source_paths
        )
        
        # Build dest config
        dest = DestConfig(
            dest_type=get_form_value('dest_type'),
            local_path=get_form_value('dest_local_path'),
            ssh_hostname=get_form_value('dest_ssh_hostname'),
            ssh_username=get_form_value('dest_ssh_username'),
            ssh_path=get_form_value('dest_ssh_path'),
            rsyncd_hostname=get_form_value('dest_rsyncd_hostname'),
            rsyncd_share=get_form_value('dest_rsyncd_share'),
            rsync_options=get_form_value('dest_rsync_options')
        )
        
        # Build restic config
        restic = ResticConfig(
            repo_type=get_form_value('restic_repo_type'),
            local_path=get_form_value('restic_local_path'),
            rest_hostname=get_form_value('restic_rest_hostname'),
            rest_port=get_form_value('restic_rest_port', '8000'),
            rest_path=get_form_value('restic_rest_path'),
            rest_use_https=get_form_value('restic_rest_use_https') == 'on',
            rest_username=get_form_value('restic_rest_username'),
            rest_password=get_form_value('restic_rest_password'),
            s3_endpoint=get_form_value('restic_s3_endpoint'),
            s3_bucket=get_form_value('restic_s3_bucket'),
            s3_prefix=get_form_value('restic_s3_prefix'),
            aws_access_key=get_form_value('restic_aws_access_key'),
            aws_secret_key=get_form_value('restic_aws_secret_key'),
            rclone_remote=get_form_value('restic_rclone_remote'),
            rclone_path=get_form_value('restic_rclone_path'),
            sftp_hostname=get_form_value('restic_sftp_hostname'),
            sftp_username=get_form_value('restic_sftp_username'),
            sftp_path=get_form_value('restic_sftp_path'),
            password=get_form_value('restic_password')
        )
        
        # Build maintenance config
        maintenance = MaintenanceConfig(
            restic_maintenance=get_form_value('restic_maintenance', 'auto')
        )
        
        # Parse schedule
        schedule_type = get_form_value('schedule', 'manual')
        cron_pattern = get_form_value('cron_pattern') if schedule_type == 'cron' else ''
        
        return JobFormData(
            is_edit=False,
            job_name=get_form_value('job_name'),
            source=source,
            dest=dest,
            restic=restic,
            maintenance=maintenance,
            schedule_type=schedule_type,
            cron_pattern=cron_pattern,
            enabled=get_form_value('enabled') == 'on',
            respect_conflicts=get_form_value('respect_conflicts') == 'on'
        )
    
    @classmethod
    def for_new_job(cls) -> JobFormData:
        """Create JobFormData for new job creation"""
        return JobFormData(is_edit=False)
    
    @staticmethod
    def _parse_schedule(schedule: str) -> tuple[str, str]:
        """Parse schedule into type and cron pattern"""
        known_schedule_types = ['manual', 'hourly', 'daily', 'weekly', 'monthly']
        if ' ' in schedule and schedule not in known_schedule_types:
            return 'cron', schedule
        return schedule, ''
    
    @staticmethod
    def _build_restic_config(dest_type: str, dest_config: Dict[str, Any]) -> ResticConfig:
        """Build Restic configuration from destination config"""
        if dest_type != 'restic':
            return ResticConfig()
        
        # Extract repo-type specific data
        repo_type = dest_config.get('repo_type', '')
        
        return ResticConfig(
            repo_type=repo_type,
            password=dest_config.get('password', ''),
            local_path=dest_config.get('repo_uri', '') if repo_type == 'local' else '',
            rest_hostname=dest_config.get('rest_hostname', ''),
            rest_port=dest_config.get('rest_port', '8000'),
            rest_path=dest_config.get('rest_path', ''),
            rest_use_https=dest_config.get('rest_use_https', True),
            rest_username=dest_config.get('rest_username', ''),
            rest_password=dest_config.get('rest_password', ''),
            s3_endpoint=dest_config.get('s3_endpoint', 's3.amazonaws.com'),
            s3_bucket=dest_config.get('s3_bucket', ''),
            s3_prefix=dest_config.get('s3_prefix', ''),
            aws_access_key=dest_config.get('aws_access_key', ''),
            aws_secret_key=dest_config.get('aws_secret_key', ''),
            rclone_remote=dest_config.get('rclone_remote', ''),
            rclone_path=dest_config.get('rclone_path', ''),
            sftp_hostname=dest_config.get('sftp_hostname', ''),
            sftp_username=dest_config.get('sftp_username', ''),
            sftp_path=dest_config.get('sftp_path', ''),
        )
    
    @staticmethod
    def _build_maintenance_config(maintenance_config: Dict[str, Any]) -> MaintenanceConfig:
        """Build maintenance configuration from job config"""
        retention_policy = maintenance_config.get('retention_policy', {})
        
        return MaintenanceConfig(
            restic_maintenance=maintenance_config.get('restic_maintenance', 'auto'),
            maintenance_discard_schedule=maintenance_config.get('maintenance_discard_schedule', ''),
            maintenance_check_schedule=maintenance_config.get('maintenance_check_schedule', ''),
            keep_last=retention_policy.get('keep_last'),
            keep_hourly=retention_policy.get('keep_hourly'),
            keep_daily=retention_policy.get('keep_daily'),
            keep_weekly=retention_policy.get('keep_weekly'),
            keep_monthly=retention_policy.get('keep_monthly'),
            keep_yearly=retention_policy.get('keep_yearly'),
        )
    
    @staticmethod
    def should_show_restic_option(backup_config):
        """Check if Restic option should be available in UI (implicit enablement)"""
        jobs = backup_config.get_backup_jobs()
        return any(job.get('dest_type') == 'restic' for job in jobs.values())