"""
Backup conflict handler
Manages job conflicts and delay tracking
"""
import time
from services.job_logger import JobLogger


class BackupConflictHandler:
    """Handles conflict detection and resolution for backup jobs"""

    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.job_logger = JobLogger()

    def wait_for_conflicts_to_resolve(self, job_name, job_config):
        """
        Wait for conflicting jobs to finish and return delay information.
        Returns dict with conflict info or None if no conflicts.
        """
        from services.job_conflict_manager import RuntimeConflictManager
        
        conflict_manager = RuntimeConflictManager(self.backup_config)
        
        # Check if this job should respect conflicts (default to True if not specified)
        should_respect_conflicts = job_config.get('respect_conflicts', True)
        if not should_respect_conflicts:
            return None

        # Track conflict delay for logging and notifications
        wait_start_time = None
        conflicting_jobs = []
        
        # Wait for any conflicting jobs to finish
        while conflict_manager.has_conflicting_jobs_running(job_name, job_config):
            if wait_start_time is None:
                wait_start_time = time.time()
                running_jobs = conflict_manager.get_running_jobs()
                conflicting_jobs = list(running_jobs)
                conflicting_resources = self._get_conflicting_resources(job_config, running_jobs, conflict_manager)
                
                print(f"INFO: Job '{job_name}' delayed due to resource conflicts with: {', '.join(running_jobs)}")
                print(f"INFO: Conflicting resources: {conflicting_resources}")
                
                # Log initial conflict detection
                conflict_msg = f"Job delayed waiting for conflicting jobs: {', '.join(running_jobs)}"
                self.job_logger.log_job_status(job_name, "waiting-conflict", conflict_msg)
            
            check_interval = conflict_manager.get_conflict_check_interval()
            print(f"INFO: Job '{job_name}' waiting {check_interval} seconds for conflicting jobs to finish")
            time.sleep(check_interval)
        
        # Calculate total wait time and log if there was a delay
        if wait_start_time is not None:
            total_wait_time = time.time() - wait_start_time
            delay_msg = f"Job waited {total_wait_time:.1f} seconds due to resource conflicts before starting"
            print(f"INFO: {delay_msg}")
            self.job_logger.log_job_status(job_name, "conflict-resolved", delay_msg)
            
            return {
                'total_wait_time': total_wait_time,
                'conflicting_jobs': conflicting_jobs
            }
        
        return None

    def register_running_job(self, job_name):
        """Register job as currently running"""
        from services.job_conflict_manager import RuntimeConflictManager
        conflict_manager = RuntimeConflictManager(self.backup_config)
        conflict_manager.register_running_job(job_name)

    def unregister_running_job(self, job_name):
        """Unregister job from running list"""
        from services.job_conflict_manager import RuntimeConflictManager
        conflict_manager = RuntimeConflictManager(self.backup_config)
        conflict_manager.unregister_running_job(job_name)

    def _get_conflicting_resources(self, job_config, running_jobs, conflict_manager):
        """Get description of conflicting resources"""
        job_sources, job_destinations = conflict_manager.get_job_resources(job_config)
        
        conflicts = []
        for running_job in running_jobs:
            if running_job in self.backup_config.config.get("backup_jobs", {}):
                running_config = self.backup_config.config["backup_jobs"][running_job]
                running_sources, running_destinations = conflict_manager.get_job_resources(running_config)
                
                shared_sources = job_sources.intersection(running_sources)
                shared_destinations = job_destinations.intersection(running_destinations)
                
                if shared_sources:
                    conflicts.append(f"shared sources: {', '.join(shared_sources)}")
                if shared_destinations:
                    conflicts.append(f"shared destinations: {', '.join(shared_destinations)}")
        
        return "; ".join(conflicts) if conflicts else "unknown resource conflict"