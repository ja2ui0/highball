"""
Unified Job Management Service
Consolidates job logging, process tracking, and conflict management
Replaces: job_logger.py, job_process_tracker.py, job_conflict_manager.py
"""
import os
import yaml
import subprocess
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any, Optional, List, Set


# =============================================================================
# **DATA STRUCTURES** - Shared configuration and path management
# =============================================================================

class LogPaths(BaseModel):
    """Centralized log path management using pathlib"""
    base_dir: Path = Path("/var/log/highball")
    
    @property
    def jobs_dir(self) -> Path:
        """Get jobs directory path"""
        return self.base_dir / "jobs"
    
    @property  
    def status_file(self) -> Path:
        """Get status file path"""
        return self.base_dir / "job_status.yaml"
        
    @property
    def validation_file(self) -> Path:
        """Get validation file path"""
        return self.base_dir / "job_validation.yaml"
        
    @property
    def deleted_jobs_file(self) -> Path:
        """Get deleted jobs file path"""
        return self.base_dir / "deleted_jobs.yaml"
        
    @property
    def running_jobs_file(self) -> Path:
        """Get running jobs file path"""
        return self.base_dir / "running_jobs.txt"
    
    def model_post_init(self, __context) -> None:
        """Ensure directories exist"""
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
    
    def get_job_log_file(self, job_name: str) -> Path:
        """Get path to individual job log file"""
        return self.jobs_dir / f"{job_name}.log"


# =============================================================================
# **JOB LOGGING CONCERN** - Log entries and status tracking
# =============================================================================

class JobLogger:
    """Job logging functionality - ONLY handles log file operations"""
    
    def __init__(self):
        self.log_paths = LogPaths()
    
    def log_job_execution(self, job_name: str, message: str, level: str = "INFO") -> None:
        """Logging concern: write execution message to job log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}"
        
        try:
            log_file = self.log_paths.get_job_log_file(job_name)
            with log_file.open('a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"ERROR: Failed to write to job log for {job_name}: {e}")
    
    def log_job_status(self, job_name: str, status: str, details: str = "") -> None:
        """Logging concern: update job status in YAML status file"""
        try:
            status_data = {}
            if self.log_paths.status_file.exists():
                with self.log_paths.status_file.open('r') as f:
                    status_data = yaml.safe_load(f) or {}
            
            status_data[job_name] = {
                'status': status,
                'details': details,
                'timestamp': datetime.now().isoformat(),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with self.log_paths.status_file.open('w') as f:
                yaml.dump(status_data, f, default_flow_style=False, sort_keys=True)
                
        except Exception as e:
            print(f"ERROR: Failed to update job status for {job_name}: {e}")
    
    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """Logging concern: read current status for a job from YAML"""
        try:
            if not self.log_paths.status_file.exists():
                return {}
            
            with self.log_paths.status_file.open('r') as f:
                status_data = yaml.safe_load(f) or {}
            
            return status_data.get(job_name, {})
        except Exception as e:
            print(f"ERROR: Failed to read job status for {job_name}: {e}")
            return {}
    
    def get_job_log_entries(self, job_name: str, max_lines: int = 100) -> List[str]:
        """Logging concern: read recent log entries from job log file"""
        try:
            log_file = self.log_paths.get_job_log_file(job_name)
            if not log_file.exists():
                return []
            
            with log_file.open('r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Return last N lines
            return [line.strip() for line in lines[-max_lines:]]
        except Exception as e:
            print(f"ERROR: Failed to read job log for {job_name}: {e}")
            return []


# =============================================================================
# **PROCESS TRACKING CONCERN** - Running job registration and verification
# =============================================================================

class JobProcessTracker:
    """Process tracking functionality - ONLY handles running job state"""
    
    def __init__(self):
        self.log_paths = LogPaths()
        self.max_job_age_hours = 24
    
    def register_job(self, job_name: str) -> None:
        """Process concern: register a job as currently running with timestamp"""
        try:
            with self.log_paths.running_jobs_file.open('a') as f:
                f.write(f"{job_name}:{datetime.now().isoformat()}\n")
        except Exception as e:
            print(f"WARNING: Could not register running job {job_name}: {e}")
    
    def unregister_job(self, job_name: str) -> None:
        """Process concern: remove a job from the running jobs tracking"""
        try:
            if not self.log_paths.running_jobs_file.exists():
                return
            
            # Read all lines and filter out the job
            with self.log_paths.running_jobs_file.open('r') as f:
                lines = f.readlines()
            
            # Write back all lines except the one for this job
            with self.log_paths.running_jobs_file.open('w') as f:
                for line in lines:
                    if not line.strip().startswith(f"{job_name}:"):
                        f.write(line)
        except Exception as e:
            print(f"WARNING: Could not unregister running job {job_name}: {e}")
    
    def get_running_jobs(self) -> List[str]:
        """Process concern: get list of currently registered running jobs"""
        try:
            if not self.log_paths.running_jobs_file.exists():
                return []
            
            with self.log_paths.running_jobs_file.open('r') as f:
                lines = f.readlines()
            
            running_jobs = []
            current_time = datetime.now()
            
            for line in lines:
                line = line.strip()
                if ':' in line:
                    job_name, timestamp_str = line.split(':', 1)
                    try:
                        job_time = datetime.fromisoformat(timestamp_str)
                        # Only include jobs that aren't too old
                        if (current_time - job_time).total_seconds() < self.max_job_age_hours * 3600:
                            running_jobs.append(job_name)
                    except ValueError:
                        # Skip malformed entries
                        continue
            
            return running_jobs
        except Exception as e:
            print(f"WARNING: Could not read running jobs: {e}")
            return []
    
    def cleanup_stale_entries(self) -> None:
        """Process concern: remove entries for jobs that are too old"""
        try:
            if not self.log_paths.running_jobs_file.exists():
                return
            
            current_time = datetime.now()
            valid_lines = []
            
            with self.log_paths.running_jobs_file.open('r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if ':' in line:
                    job_name, timestamp_str = line.split(':', 1)
                    try:
                        job_time = datetime.fromisoformat(timestamp_str)
                        # Keep entries that aren't too old
                        if (current_time - job_time).total_seconds() < self.max_job_age_hours * 3600:
                            valid_lines.append(line + '\n')
                    except ValueError:
                        # Skip malformed entries
                        continue
            
            # Write back only valid entries
            with self.log_paths.running_jobs_file.open('w') as f:
                f.writelines(valid_lines)
                
        except Exception as e:
            print(f"WARNING: Could not cleanup stale job entries: {e}")




# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates all job management concerns
# =============================================================================

class JobManagementService:
    """Unified job management service - ONLY coordinates between specialized concerns"""
    
    def __init__(self, backup_config=None):
        self.backup_config = backup_config
        self.logger = JobLogger()
        self.process_tracker = JobProcessTracker()
        from shared.services.ssh import JobConflictManager
        self.conflict_manager = JobConflictManager(backup_config) if backup_config else None
    
    # **LOGGING DELEGATION** - Pure delegation to logging concern
    def log_execution(self, job_name: str, message: str, level: str = "INFO") -> None:
        """Delegation: log execution message"""
        self.logger.log_job_execution(job_name, message, level)
    
    def log_status(self, job_name: str, status: str, details: str = "") -> None:
        """Delegation: update job status"""
        self.logger.log_job_status(job_name, status, details)
    
    def get_status(self, job_name: str) -> Dict[str, Any]:
        """Delegation: get current job status"""
        return self.logger.get_job_status(job_name)
    
    def get_log_entries(self, job_name: str, max_lines: int = 100) -> List[str]:
        """Delegation: get recent log entries"""
        return self.logger.get_job_log_entries(job_name, max_lines)
    
    # **PROCESS TRACKING DELEGATION** - Pure delegation to tracking concern
    def register_running_job(self, job_name: str) -> None:
        """Delegation: register running job"""
        self.process_tracker.register_job(job_name)
    
    def unregister_running_job(self, job_name: str) -> None:
        """Delegation: unregister running job"""
        self.process_tracker.unregister_job(job_name)
    
    def get_running_jobs(self) -> List[str]:
        """Delegation: get running jobs list"""
        return self.process_tracker.get_running_jobs()
    
    def cleanup_stale_jobs(self) -> None:
        """Delegation: cleanup stale entries"""
        self.process_tracker.cleanup_stale_entries()
    
    # **CONFLICT MANAGEMENT DELEGATION** - Pure delegation to conflict concern
    def check_conflicts(self, job_name: str) -> List[str]:
        """Delegation: check for job conflicts"""
        if not self.conflict_manager:
            return []
        return self.conflict_manager.check_for_conflicts(job_name)
    
    def wait_for_conflicts_to_resolve(self, job_name: str, max_wait_seconds: int = 300) -> bool:
        """Delegation: wait for conflicts to resolve"""
        if not self.conflict_manager:
            return True
        return self.conflict_manager.wait_for_conflicts_to_resolve(job_name, max_wait_seconds)
    
    # **BACKUP ORCHESTRATION** - Complete backup execution with management
    def run_backup_job_async(self, job_name: str, job_config: Optional[Dict[str, Any]] = None, dry_run: bool = False) -> None:
        """Execute backup operation asynchronously with full orchestration"""
        from datetime import datetime
        from jobs.services.backup import backup_service
        from dests.services.rsync import rsync_service
        from jobs.services.notify import NotificationService
        import logging
        
        if not job_config and self.backup_config:
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                self.log_status(job_name, 'failed', f"Job '{job_name}' not found")
                return
            job_config = jobs[job_name]
            job_config['job_name'] = job_name
        
        if not job_config:
            self.log_status(job_name, 'failed', 'No job configuration available')
            return
            
        start_time = datetime.now()
        logger = logging.getLogger(__name__)
        
        try:
            # Register running job
            self.register_running_job(job_name)
            
            # Log job start
            self.log_execution(job_name, f"Starting backup job (dry_run={dry_run})")
            
            # Execute backup based on destination type
            dest_type = job_config.get('dest_type')
            
            if dest_type == 'restic':
                result = backup_service.execute_backup(job_config, dry_run)
            elif dest_type in ['ssh', 'local', 'rsyncd']:
                result = rsync_service.execute_backup(job_config, dry_run)
            else:
                result = {
                    'success': False,
                    'error': f'Unsupported destination type: {dest_type}'
                }
            
            # Calculate duration
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Log result
            if result['success']:
                self.log_status(job_name, 'completed', f"Backup completed in {duration_seconds:.2f}s")
                
                # Send success notifications if not dry run
                if not dry_run:
                    notification_service = NotificationService()
                    notification_service.notify_job_success(job_name, duration_seconds, job_config)
            else:
                self.log_status(job_name, 'failed', result['error'])
                
                # Send failure notifications
                notification_service = NotificationService()
                notification_service.notify_job_failure(job_name, result['error'], job_config)
            
        except Exception as e:
            logger.error(f"Async backup error for {job_name}: {e}")
            self.log_status(job_name, 'failed', str(e))
            
            notification_service = NotificationService()
            notification_service.notify_job_failure(job_name, str(e), job_config)
        
        finally:
            # Unregister running job
            self.unregister_running_job(job_name)


# =============================================================================
# **SYSTEM LOGGING CONCERN** - System log retrieval from various sources
# =============================================================================

class SystemLoggingService:
    """System logging functionality - ONLY handles system log retrieval"""
    
    def get_system_logs(self, log_type: str) -> List[str]:
        """Get system logs by type"""
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if log_type == 'app':
                # Application logs from docker
                import subprocess
                result = subprocess.run(['docker', 'logs', '--tail', '100', 'highball'], 
                                      capture_output=True, text=True, timeout=10)
                return result.stdout.split('\n') if result.returncode == 0 else ['Log retrieval failed']
            
            elif log_type == 'system':
                # System logs
                log_files = ['/var/log/syslog', '/var/log/messages']
                for log_file in log_files:
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                        return lines[-100:]  # Last 100 lines
                return ['No system logs found']
            
            elif log_type in ['job_status', 'validation', 'running_jobs', 'deleted_jobs']:
                # Highball operational logs
                log_file = f'/var/log/highball/{log_type}.yaml'
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    return [content] if content.strip() else ['Empty log file']
                return ['Log file not found']
            
            else:
                return ['Unknown log type']
                
        except Exception as e:
            logger.error(f"Get logs error: {e}")
            return [f'Error retrieving logs: {str(e)}']


# =============================================================================
# **JOB OPERATIONS CONCERN** - Job CRUD operations and lifecycle management
# =============================================================================

def handle_operations_errors(operation_name: str):
    """Decorator to handle job operation errors consistently"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"{operation_name} operation error: {e}")
                return {
                    'success': False,
                    'error': f'{operation_name} operation failed: {str(e)}'
                }
        return wrapper
    return decorator


class JobOperationsService:
    """Service for job CRUD operations and lifecycle management"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    @handle_operations_errors("Save job")
    def save_job(self, job_name: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save job configuration to persistent storage"""
        if not job_name:
            return {'success': False, 'error': 'Job name is required'}
        
        if not job_config:
            return {'success': False, 'error': 'Job configuration is required'}
        
        success = self.backup_config.save_job(job_name, job_config)
        
        if success:
            return {'success': True, 'message': f"Job '{job_name}' saved successfully"}
        else:
            return {'success': False, 'error': 'Failed to save job configuration'}
    
    @handle_operations_errors("Delete job")
    def delete_job(self, job_name: str) -> Dict[str, Any]:
        """Move job to deleted jobs (soft delete)"""
        if not job_name:
            return {'success': False, 'error': 'Job name is required'}
        
        success = self.backup_config.delete_backup_job(job_name)
        
        if success:
            return {'success': True, 'message': f"Job '{job_name}' deleted successfully"}
        else:
            return {'success': False, 'error': f"Failed to delete job '{job_name}'"}
    
    @handle_operations_errors("Purge job")
    def purge_job(self, job_name: str) -> Dict[str, Any]:
        """Permanently remove job from deleted jobs (hard delete)"""
        if not job_name:
            return {'success': False, 'error': 'Job name is required'}
        
        success = self.backup_config.purge_job(job_name)
        
        if success:
            return {'success': True, 'message': f"Job '{job_name}' permanently purged"}
        else:
            return {'success': False, 'error': f"Failed to purge job '{job_name}'"}
    
    @handle_operations_errors("Restore job")
    def restore_job(self, job_name: str) -> Dict[str, Any]:
        """Restore job from deleted jobs back to active jobs"""
        if not job_name:
            return {'success': False, 'error': 'Job name is required'}
        
        success = self.backup_config.restore_deleted_job(job_name)
        
        if success:
            return {'success': True, 'message': f"Job '{job_name}' restored successfully"}
        else:
            return {'success': False, 'error': f"Failed to restore job '{job_name}'"}