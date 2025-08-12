"""
Job logging service for backup operations - modernized with pathlib
Manages job execution logs and status tracking in /var/log/highball/
"""
import yaml
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional


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
        
        # Ensure directories exist
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
    
    def get_job_log_file(self, job_name: str) -> Path:
        """Get path to individual job log file"""
        return self.jobs_dir / f"{job_name}.log"


class YAMLFileManager:
    """Consolidated YAML file operations eliminating duplication"""
    
    @staticmethod
    def load_yaml_file(file_path: Path, default_value: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generic YAML file loader with error handling"""
        if default_value is None:
            default_value = {}
            
        if not file_path.exists():
            return default_value
        
        try:
            content = file_path.read_text().strip()
            if not content:
                return default_value
            
            data = yaml.safe_load(content)
            return data if data else default_value
            
        except (yaml.YAMLError, IOError) as e:
            print(f"WARNING: Could not load {file_path.name}: {e}")
            return default_value
    
    @staticmethod
    def save_yaml_file(file_path: Path, data: Dict[str, Any]) -> bool:
        """Generic YAML file saver with error handling"""
        try:
            file_path.write_text(yaml.dump(data, default_flow_style=False, indent=2))
            return True
        except IOError as e:
            print(f"ERROR: Could not save {file_path.name}: {e}")
            return False


class JobLogger:
    """Manages job execution logging and status tracking - modernized"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.paths = LogPaths(base_dir) if base_dir else LogPaths()
        self.yaml_manager = YAMLFileManager()
    
    def log_job_execution(self, job_name: str, message: str, level: str = "INFO"):
        """Log detailed job execution information to individual job log file"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        job_log_file = self.paths.get_job_log_file(job_name)
        try:
            # Append to log file
            with job_log_file.open('a') as f:
                f.write(log_entry)
        except IOError as e:
            print(f"ERROR: Could not write to job log {job_log_file}: {e}")
    
    def log_job_status(self, job_name: str, status: str, message: str = ""):
        """Log job status to YAML status file"""
        timestamp = datetime.now().isoformat()
        
        # Load existing status
        status_data = self._load_status_file()
        
        # Update job status
        status_data[job_name] = {
            'last_run': timestamp,
            'status': status,
            'message': message
        }
        
        # Save updated status
        self._save_status_file(status_data)
    
    def get_job_logs(self) -> Dict[str, Any]:
        """Get all job status information"""
        return self._load_status_file()
    
    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """Get status for specific job"""
        status_data = self._load_status_file()
        return status_data.get(job_name, {})
    
    def remove_job_logs(self, job_name: str):
        """Remove all logs for a job (for purge operations)"""
        # Remove status entry
        status_data = self._load_status_file()
        if job_name in status_data:
            del status_data[job_name]
            self._save_status_file(status_data)
        
        # Remove validation state entry
        validation_data = self._load_validation_file()
        if job_name in validation_data:
            del validation_data[job_name]
            self._save_validation_file(validation_data)
        
        # Remove detailed log file
        job_log_file = self.paths.get_job_log_file(job_name)
        if job_log_file.exists():
            try:
                job_log_file.unlink()
            except OSError as e:
                print(f"WARNING: Could not remove job log file {job_log_file}: {e}")
    
    def rename_job_logs(self, old_job_name: str, new_job_name: str):
        """Rename all logs for a job when job name changes"""
        # Rename status entry
        status_data = self._load_status_file()
        if old_job_name in status_data:
            status_data[new_job_name] = status_data.pop(old_job_name)
            self._save_status_file(status_data)
        
        # Rename validation state entry
        validation_data = self._load_validation_file()
        if old_job_name in validation_data:
            validation_data[new_job_name] = validation_data.pop(old_job_name)
            self._save_validation_file(validation_data)
        
        # Rename detailed log file
        old_log_file = self.paths.get_job_log_file(old_job_name)
        new_log_file = self.paths.get_job_log_file(new_job_name)
        if old_log_file.exists():
            try:
                old_log_file.rename(new_log_file)
            except OSError as e:
                print(f"WARNING: Could not rename job log file {old_log_file} to {new_log_file}: {e}")
    
    def log_ssh_validation(self, job_name: str, validation_timestamp: str):
        """Log SSH validation timestamp for a job"""
        validation_data = self._load_validation_file()
        validation_data[job_name] = {
            'source_ssh_validated_at': validation_timestamp
        }
        self._save_validation_file(validation_data)
    
    def get_ssh_validation(self, job_name: str) -> Optional[str]:
        """Get SSH validation timestamp for a job"""
        validation_data = self._load_validation_file()
        return validation_data.get(job_name, {}).get('source_ssh_validated_at')
    
    def log_job_deletion(self, job_name: str, job_config: Dict[str, Any]):
        """Log job deletion to deleted jobs tracking file"""
        deleted_data = self._load_deleted_jobs_file()
        
        # Store job config with deletion timestamp
        job_config_copy = job_config.copy()
        job_config_copy['deleted_at'] = datetime.now().isoformat()
        deleted_data[job_name] = job_config_copy
        
        self._save_deleted_jobs_file(deleted_data)
        
        # Also log the deletion as a status entry
        self.log_job_status(job_name, "deleted", "Job deleted and moved to deletion log")
    
    def get_deleted_jobs(self) -> Dict[str, Any]:
        """Get all deleted jobs from log file"""
        return self._load_deleted_jobs_file()
    
    def restore_deleted_job(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Remove job from deleted jobs log (when restoring)"""
        deleted_data = self._load_deleted_jobs_file()
        if job_name in deleted_data:
            job_config = deleted_data[job_name].copy()
            job_config.pop('deleted_at', None)  # Remove deletion timestamp
            del deleted_data[job_name]
            self._save_deleted_jobs_file(deleted_data)
            
            # Log the restoration
            self.log_job_status(job_name, "restored", "Job restored from deletion log")
            return job_config
        return None
    
    def purge_deleted_job(self, job_name: str) -> bool:
        """Permanently remove job from deleted jobs log"""
        deleted_data = self._load_deleted_jobs_file()
        if job_name in deleted_data:
            del deleted_data[job_name]
            self._save_deleted_jobs_file(deleted_data)
            
            # Log the purge (final status entry)
            self.log_job_status(job_name, "purged", "Job permanently deleted from all logs")
            return True
        return False
    
    # Private methods using consolidated YAML operations
    def _load_status_file(self) -> Dict[str, Any]:
        """Load job status from YAML file"""
        return self.yaml_manager.load_yaml_file(self.paths.status_file)
    
    def _save_status_file(self, status_data: Dict[str, Any]) -> bool:
        """Save job status to YAML file"""
        return self.yaml_manager.save_yaml_file(self.paths.status_file, status_data)
    
    def _load_validation_file(self) -> Dict[str, Any]:
        """Load job validation state from YAML file"""
        return self.yaml_manager.load_yaml_file(self.paths.validation_file)
    
    def _save_validation_file(self, validation_data: Dict[str, Any]) -> bool:
        """Save job validation state to YAML file"""
        return self.yaml_manager.save_yaml_file(self.paths.validation_file, validation_data)
    
    def _load_deleted_jobs_file(self) -> Dict[str, Any]:
        """Load deleted jobs from YAML file"""
        return self.yaml_manager.load_yaml_file(self.paths.deleted_jobs_file)
    
    def _save_deleted_jobs_file(self, deleted_data: Dict[str, Any]) -> bool:
        """Save deleted jobs to YAML file"""
        return self.yaml_manager.save_yaml_file(self.paths.deleted_jobs_file, deleted_data)