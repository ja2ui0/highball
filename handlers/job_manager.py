"""
Job CRUD operations
Handles creating, updating, deleting, and restoring backup jobs
"""
from datetime import datetime

class JobManager:
    """Manages backup job CRUD operations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def create_job(self, job_name, job_config):
        """Create a new backup job"""
        self.backup_config.add_backup_job(job_name, job_config)
    
    def get_job(self, job_name):
        """Get a specific backup job"""
        return self.backup_config.get_backup_job(job_name)
    
    def get_all_jobs(self):
        """Get all active backup jobs"""
        return self.backup_config.get_backup_jobs()
    
    def get_deleted_jobs(self):
        """Get all deleted backup jobs"""
        return self.backup_config.config.get('deleted_jobs', {})
    
    def get_job_logs(self):
        """Get backup job logs"""
        return self.backup_config.config.get('backup_logs', {})
    
    def delete_job(self, job_name):
        """Soft delete a backup job (move to deleted_jobs)"""
        jobs = self.get_all_jobs()
        if job_name not in jobs:
            return False
        
        # Move to deleted section with timestamp
        job_config = jobs[job_name].copy()
        job_config['deleted_at'] = datetime.now().isoformat()
        
        # Create deleted_jobs section if needed
        if 'deleted_jobs' not in self.backup_config.config:
            self.backup_config.config['deleted_jobs'] = {}
        
        # Move job
        self.backup_config.config['deleted_jobs'][job_name] = job_config
        del self.backup_config.config['backup_jobs'][job_name]
        self.backup_config.save_config()
        return True
    
    def restore_job(self, job_name):
        """Restore job from deleted_jobs back to active jobs"""
        deleted_jobs = self.get_deleted_jobs()
        if job_name not in deleted_jobs:
            return False
        
        # Remove deletion timestamp and restore
        job_config = deleted_jobs[job_name].copy()
        job_config.pop('deleted_at', None)
        
        self.backup_config.config['backup_jobs'][job_name] = job_config
        del self.backup_config.config['deleted_jobs'][job_name]
        self.backup_config.save_config()
        return True
    
    def purge_job(self, job_name):
        """Permanently delete job from deleted_jobs"""
        deleted_jobs = self.get_deleted_jobs()
        if job_name not in deleted_jobs:
            return False
        
        del self.backup_config.config['deleted_jobs'][job_name]
        
        # Also remove logs
        backup_logs = self.backup_config.config.get('backup_logs', {})
        if job_name in backup_logs:
            del self.backup_config.config['backup_logs'][job_name]
        
        self.backup_config.save_config()
        return True
