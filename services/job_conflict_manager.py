"""
Runtime job conflict detection and management
Prevents backup jobs from running simultaneously when they share resources
"""
import os
import time
from datetime import datetime


class RuntimeConflictManager:
    """Manages runtime job conflicts by checking for running jobs"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def get_job_resources(self, job_config):
        """Extract source and destination resources from job config"""
        sources = set()
        destinations = set()
        
        # Extract source resources
        if job_config.get('source_type') == 'ssh':
            source_config = job_config.get('source_config', {})
            hostname = source_config.get('hostname')
            if hostname:
                sources.add(hostname.lower())
        
        # Extract destination resources  
        dest_type = job_config.get('dest_type')
        dest_config = job_config.get('dest_config', {})
        
        if dest_type in ['ssh', 'rsyncd']:
            hostname = dest_config.get('hostname')
            if hostname:
                destinations.add(hostname.lower())
        
        return sources, destinations
    
    def is_conflict_avoidance_enabled(self):
        """Check if runtime conflict avoidance is enabled"""
        global_settings = self.backup_config.config.get('global_settings', {})
        return global_settings.get('enable_conflict_avoidance', True)
    
    def get_conflict_check_interval(self):
        """Get conflict check interval in seconds"""
        global_settings = self.backup_config.config.get('global_settings', {})
        return global_settings.get('conflict_check_interval', 300)  # 5 minutes default
    
    def register_running_job(self, job_name):
        """Register a job as currently running using process tracker"""
        from services.job_process_tracker import JobProcessTracker
        
        tracker = JobProcessTracker()
        tracker.register_job(job_name)
    
    def unregister_running_job(self, job_name):
        """Remove a job from the running jobs list using process tracker"""
        from services.job_process_tracker import JobProcessTracker
        
        tracker = JobProcessTracker()
        tracker.unregister_job(job_name)
    
    def get_running_jobs(self):
        """Get list of currently running jobs using process tracker"""
        from services.job_process_tracker import JobProcessTracker
        
        tracker = JobProcessTracker()
        return tracker.get_verified_running_jobs()
    
    def has_conflicting_jobs_running(self, job_name, job_config):
        """Check if there are conflicting jobs currently running"""
        if not self.is_conflict_avoidance_enabled():
            return False
        
        running_jobs = self.get_running_jobs()
        if not running_jobs:
            return False
        
        # Get resources for the job we want to run
        target_sources, target_destinations = self.get_job_resources(job_config)
        
        # Check each running job for resource conflicts
        all_jobs = self.backup_config.get_backup_jobs()
        
        for running_job_name in running_jobs:
            if running_job_name == job_name:
                continue  # Skip self
            
            running_job_config = all_jobs.get(running_job_name)
            if not running_job_config:
                continue  # Job no longer exists in config
            
            running_sources, running_destinations = self.get_job_resources(running_job_config)
            
            # Check for resource conflicts (shared source OR destination)
            if (target_sources & running_sources) or (target_destinations & running_destinations):
                shared_sources = target_sources & running_sources
                shared_destinations = target_destinations & running_destinations
                print(f"INFO: Job '{job_name}' waiting - conflicts with running job '{running_job_name}' "
                      f"(shared sources: {shared_sources}, shared destinations: {shared_destinations})")
                return True
        
        return False