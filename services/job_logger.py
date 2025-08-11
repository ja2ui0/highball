"""
Job logging service for backup operations
Manages job execution logs and status tracking in /var/log/highball/
"""
import os
import yaml
from datetime import datetime


class JobLogger:
    """Manages job execution logging and status tracking"""
    
    def __init__(self):
        self.log_dir = "/var/log/highball"
        self.jobs_dir = os.path.join(self.log_dir, "jobs")
        self.status_file = os.path.join(self.log_dir, "job_status.yaml")
        self.validation_file = os.path.join(self.log_dir, "job_validation.yaml")
        self.deleted_jobs_file = os.path.join(self.log_dir, "deleted_jobs.yaml")
        self._ensure_log_directories()
    
    def _ensure_log_directories(self):
        """Create log directories if they don't exist"""
        os.makedirs(self.jobs_dir, exist_ok=True)
    
    def log_job_execution(self, job_name, message, level="INFO"):
        """Log detailed job execution information to individual job log file"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        job_log_file = os.path.join(self.jobs_dir, f"{job_name}.log")
        with open(job_log_file, 'a') as f:
            f.write(log_entry)
    
    def log_job_status(self, job_name, status, message=""):
        """Log job status to YAML status file (replaces config backup_logs)"""
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
    
    def get_job_logs(self):
        """Get all job status information (replaces JobManager.get_job_logs)"""
        return self._load_status_file()
    
    def get_job_status(self, job_name):
        """Get status for specific job"""
        status_data = self._load_status_file()
        return status_data.get(job_name, {})
    
    def remove_job_logs(self, job_name):
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
        job_log_file = os.path.join(self.jobs_dir, f"{job_name}.log")
        if os.path.exists(job_log_file):
            os.remove(job_log_file)
    
    def rename_job_logs(self, old_job_name, new_job_name):
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
        old_log_file = os.path.join(self.jobs_dir, f"{old_job_name}.log")
        new_log_file = os.path.join(self.jobs_dir, f"{new_job_name}.log")
        if os.path.exists(old_log_file):
            os.rename(old_log_file, new_log_file)

    def log_ssh_validation(self, job_name, validation_timestamp):
        """Log SSH validation timestamp for a job"""
        validation_data = self._load_validation_file()
        validation_data[job_name] = {
            'source_ssh_validated_at': validation_timestamp
        }
        self._save_validation_file(validation_data)
    
    def get_ssh_validation(self, job_name):
        """Get SSH validation timestamp for a job"""
        validation_data = self._load_validation_file()
        return validation_data.get(job_name, {}).get('source_ssh_validated_at')
    
    def _load_status_file(self):
        """Load job status from YAML file"""
        if not os.path.exists(self.status_file):
            return {}
        
        try:
            with open(self.status_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                
                status_data = yaml.safe_load(content)
                return status_data if status_data else {}
                
        except (yaml.YAMLError, IOError) as e:
            print(f"WARNING: Could not load job status file: {e}")
            return {}
    
    def _save_status_file(self, status_data):
        """Save job status to YAML file"""
        try:
            with open(self.status_file, 'w') as f:
                yaml.dump(status_data, f, default_flow_style=False, indent=2)
        except IOError as e:
            print(f"ERROR: Could not save job status file: {e}")
    
    def _load_validation_file(self):
        """Load job validation state from YAML file"""
        if not os.path.exists(self.validation_file):
            return {}
        
        try:
            with open(self.validation_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                
                validation_data = yaml.safe_load(content)
                return validation_data if validation_data else {}
                
        except (yaml.YAMLError, IOError) as e:
            print(f"WARNING: Could not load job validation file: {e}")
            return {}
    
    def _save_validation_file(self, validation_data):
        """Save job validation state to YAML file"""
        try:
            with open(self.validation_file, 'w') as f:
                yaml.dump(validation_data, f, default_flow_style=False, indent=2)
        except IOError as e:
            print(f"ERROR: Could not save job validation file: {e}")
    
    def log_job_deletion(self, job_name, job_config):
        """Log job deletion to deleted jobs tracking file"""
        deleted_data = self._load_deleted_jobs_file()
        
        # Store job config with deletion timestamp
        job_config_copy = job_config.copy()
        job_config_copy['deleted_at'] = datetime.now().isoformat()
        deleted_data[job_name] = job_config_copy
        
        self._save_deleted_jobs_file(deleted_data)
        
        # Also log the deletion as a status entry
        self.log_job_status(job_name, "deleted", f"Job deleted and moved to deletion log")
    
    def get_deleted_jobs(self):
        """Get all deleted jobs from log file"""
        return self._load_deleted_jobs_file()
    
    def restore_deleted_job(self, job_name):
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
    
    def purge_deleted_job(self, job_name):
        """Permanently remove job from deleted jobs log"""
        deleted_data = self._load_deleted_jobs_file()
        if job_name in deleted_data:
            del deleted_data[job_name]
            self._save_deleted_jobs_file(deleted_data)
            
            # Log the purge (final status entry)
            self.log_job_status(job_name, "purged", "Job permanently deleted from all logs")
            return True
        return False
    
    def _load_deleted_jobs_file(self):
        """Load deleted jobs from YAML file"""
        if not os.path.exists(self.deleted_jobs_file):
            return {}
        
        try:
            with open(self.deleted_jobs_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                
                deleted_data = yaml.safe_load(content)
                return deleted_data if deleted_data else {}
                
        except (yaml.YAMLError, IOError) as e:
            print(f"WARNING: Could not load deleted jobs file: {e}")
            return {}
    
    def _save_deleted_jobs_file(self, deleted_data):
        """Save deleted jobs to YAML file"""
        try:
            with open(self.deleted_jobs_file, 'w') as f:
                yaml.dump(deleted_data, f, default_flow_style=False, indent=2)
        except IOError as e:
            print(f"ERROR: Could not save deleted jobs file: {e}")