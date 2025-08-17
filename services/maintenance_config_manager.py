"""
Maintenance configuration manager
Handles per-job and global maintenance settings with defaults
"""
from typing import Dict, Any
from services.maintenance_defaults import MaintenanceDefaults


class MaintenanceConfigManager:
    """Service for managing maintenance configuration and defaults"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def is_maintenance_enabled(self, job_name: str) -> bool:
        """Check if maintenance is enabled for job (auto or user)"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Only applicable to Restic jobs
        if job_config.get('dest_type') != 'restic':
            return False
        
        maintenance_mode = self.get_maintenance_mode(job_name)
        return maintenance_mode in ['auto', 'user']
    
    def get_maintenance_mode(self, job_name: str) -> str:
        """Get maintenance mode: 'auto', 'user', or 'off'"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        return job_config.get('restic_maintenance', 'auto')
    
    def get_discard_schedule(self, job_name: str) -> str:
        """Get discard schedule for job (combines forget+prune operations)"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_discard_schedule' in job_config:
            return job_config['maintenance_discard_schedule']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        return maintenance_settings.get('discard_schedule', MaintenanceDefaults.DISCARD_SCHEDULE)
    
    def get_check_schedule(self, job_name: str) -> str:
        """Get check schedule for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_check_schedule' in job_config:
            return job_config['maintenance_check_schedule']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        return maintenance_settings.get('check_schedule', MaintenanceDefaults.CHECK_SCHEDULE)
    
    def get_retention_policy(self, job_name: str) -> Dict[str, Any]:
        """Get retention policy for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'retention_policy' in job_config:
            return job_config['retention_policy']
        
        # Global default policy
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        global_retention = maintenance_settings.get('retention_policy', {})
        
        # Merge with defaults
        default_retention = {
            'keep_last': MaintenanceDefaults.KEEP_LAST,
            'keep_hourly': MaintenanceDefaults.KEEP_HOURLY,
            'keep_daily': MaintenanceDefaults.KEEP_DAILY,
            'keep_weekly': MaintenanceDefaults.KEEP_WEEKLY,
            'keep_monthly': MaintenanceDefaults.KEEP_MONTHLY,
            'keep_yearly': MaintenanceDefaults.KEEP_YEARLY
        }
        
        # Override defaults with global settings
        default_retention.update(global_retention)
        
        return default_retention
    
    def get_check_config(self, job_name: str) -> Dict[str, Any]:
        """Get check configuration for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_check_config' in job_config:
            return job_config['maintenance_check_config']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        global_check = maintenance_settings.get('check_config', {})
        
        # Merge with defaults
        default_check = {
            'read_data_subset': MaintenanceDefaults.CHECK_READ_DATA_SUBSET
        }
        
        default_check.update(global_check)
        return default_check
    
    def get_maintenance_summary(self, job_name: str) -> Dict[str, Any]:
        """Get maintenance status summary for a job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        if job_config.get('dest_type') != 'restic':
            return {'applicable': False, 'reason': 'Not a Restic job'}
        
        auto_maintenance = job_config.get('auto_maintenance', True)
        
        return {
            'applicable': True,
            'auto_maintenance_enabled': auto_maintenance,
            'discard_schedule': self.get_discard_schedule(job_name),
            'check_schedule': self.get_check_schedule(job_name),
            'retention_policy': self.get_retention_policy(job_name)
        }