"""
Unified Job Management Service
Consolidates job logging, process tracking, and conflict management
Replaces: job_logger.py, job_process_tracker.py, job_conflict_manager.py
"""
import os
import yaml
import subprocess
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Set


# =============================================================================
# **DATA STRUCTURES** - Shared configuration and path management
# =============================================================================

@dataclass
class LogPaths:
    """Centralized log path management using pathlib"""
    base_dir: Path = Path("/var/log/highball")
    
    def __post_init__(self):
        """Initialize derived paths and ensure directories exist"""
        self.jobs_dir = self.base_dir / "jobs"
        self.status_file = self.base_dir / "job_status.yaml"
        self.validation_file = self.base_dir / "job_validation.yaml"
        self.deleted_jobs_file = self.base_dir / "deleted_jobs.yaml"
        self.running_jobs_file = self.base_dir / "running_jobs.txt"
        
        # Ensure directories exist
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
    
    def log_job_execution(self, job_name: str, message: str, level: str = "INFO"):
        """Logging concern: write execution message to job log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}"
        
        try:
            log_file = self.log_paths.get_job_log_file(job_name)
            with log_file.open('a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"ERROR: Failed to write to job log for {job_name}: {e}")
    
    def log_job_status(self, job_name: str, status: str, details: str = ""):
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
    
    def register_job(self, job_name: str):
        """Process concern: register a job as currently running with timestamp"""
        try:
            with self.log_paths.running_jobs_file.open('a') as f:
                f.write(f"{job_name}:{datetime.now().isoformat()}\n")
        except Exception as e:
            print(f"WARNING: Could not register running job {job_name}: {e}")
    
    def unregister_job(self, job_name: str):
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
    
    def cleanup_stale_entries(self):
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
# **CONFLICT DETECTION CONCERN** - Resource conflict analysis and resolution
# =============================================================================

class JobConflictManager:
    """Conflict management functionality - ONLY handles resource conflict detection"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.process_tracker = JobProcessTracker()
    
    def get_job_resources(self, job_config: Dict[str, Any]) -> Dict[str, Set[str]]:
        """Conflict concern: extract resource identifiers from job configuration"""
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
        
        if dest_type == 'ssh':
            hostname = dest_config.get('hostname')
            if hostname:
                destinations.add(hostname.lower())
        elif dest_type == 'rsyncd':
            hostname = dest_config.get('hostname')
            if hostname:
                destinations.add(hostname.lower())
        elif dest_type == 'restic':
            repo_uri = dest_config.get('repo_uri', '')
            if repo_uri:
                destinations.add(repo_uri)
        
        return {'sources': sources, 'destinations': destinations}
    
    def check_for_conflicts(self, job_name: str) -> List[str]:
        """Conflict concern: detect if job conflicts with currently running jobs"""
        # Get this job's config
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name)
        if not job_config:
            return []
        
        job_resources = self.get_job_resources(job_config)
        running_jobs = self.process_tracker.get_running_jobs()
        conflicts = []
        
        for running_job in running_jobs:
            if running_job == job_name:
                continue  # Skip self
            
            running_job_config = jobs.get(running_job)
            if not running_job_config:
                continue
            
            running_resources = self.get_job_resources(running_job_config)
            
            # Check for overlapping resources
            if (job_resources['sources'] & running_resources['sources'] or
                job_resources['destinations'] & running_resources['destinations']):
                conflicts.append(running_job)
        
        return conflicts
    
    def wait_for_conflicts_to_resolve(self, job_name: str, max_wait_seconds: int = 300) -> bool:
        """Conflict concern: wait for conflicting jobs to complete"""
        start_time = datetime.now()
        
        while True:
            conflicts = self.check_for_conflicts(job_name)
            if not conflicts:
                return True  # No conflicts, can proceed
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= max_wait_seconds:
                return False  # Timeout
            
            print(f"Job {job_name} waiting for conflicts to resolve: {conflicts}")
            time.sleep(10)  # Wait 10 seconds before checking again


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates all job management concerns
# =============================================================================

class JobManagementService:
    """Unified job management service - ONLY coordinates between specialized concerns"""
    
    def __init__(self, backup_config=None):
        self.backup_config = backup_config
        self.logger = JobLogger()
        self.process_tracker = JobProcessTracker()
        self.conflict_manager = JobConflictManager(backup_config) if backup_config else None
    
    # **LOGGING DELEGATION** - Pure delegation to logging concern
    def log_execution(self, job_name: str, message: str, level: str = "INFO"):
        """Delegation: log execution message"""
        self.logger.log_job_execution(job_name, message, level)
    
    def log_status(self, job_name: str, status: str, details: str = ""):
        """Delegation: update job status"""
        self.logger.log_job_status(job_name, status, details)
    
    def get_status(self, job_name: str) -> Dict[str, Any]:
        """Delegation: get current job status"""
        return self.logger.get_job_status(job_name)
    
    def get_log_entries(self, job_name: str, max_lines: int = 100) -> List[str]:
        """Delegation: get recent log entries"""
        return self.logger.get_job_log_entries(job_name, max_lines)
    
    # **PROCESS TRACKING DELEGATION** - Pure delegation to tracking concern
    def register_running_job(self, job_name: str):
        """Delegation: register running job"""
        self.process_tracker.register_job(job_name)
    
    def unregister_running_job(self, job_name: str):
        """Delegation: unregister running job"""
        self.process_tracker.unregister_job(job_name)
    
    def get_running_jobs(self) -> List[str]:
        """Delegation: get running jobs list"""
        return self.process_tracker.get_running_jobs()
    
    def cleanup_stale_jobs(self):
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