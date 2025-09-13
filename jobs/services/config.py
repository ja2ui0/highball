"""
Jobs Config Service
Handle job CRUD operations with deleted/restore logic (compat mode)
"""

import os
import glob
import yaml
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

from shared.services.config import ConfigIOService, ConfigReader


class JobConfigService:
    """Handle job configuration CRUD operations"""

    def __init__(self):
        self.shared = ConfigIOService()
        self.config_reader = ConfigReader()

    def get_backup_jobs(self) -> Dict[str, Any]:
        """Get all backup jobs - read directly from disk for real-time updates"""
        return self.config_reader.get_backup_jobs()

    def get_backup_job(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get specific backup job - read directly from disk"""
        return self.config_reader.get_backup_job(job_name)

    def add_backup_job(self, job_name: str, job_config: Dict[str, Any]) -> bool:
        """Add or update a backup job using new file hierarchy"""
        return self.save_job(job_name, job_config)

    def save_job(self, job_name: str, job_config: Dict[str, Any]) -> bool:
        """Save a backup job config file"""
        try:
            # Ensure directory exists
            jobs_dir = "/config/local/jobs"
            os.makedirs(jobs_dir, exist_ok=True)

            # Write config file atomically
            config_file = f"/config/local/jobs/{job_name}.yaml"
            self.shared.save_yaml(config_file, job_config)

            return True

        except Exception as e:
            print(f"Error saving job {job_name}: {str(e)}")
            return False

    def delete_backup_job(self, job_name: str) -> bool:
        """Delete a backup job (move files to deleted/ subdirectories)"""
        try:
            # Check if job exists
            jobs = self._load_backup_jobs()
            if job_name not in jobs:
                return False

            # Ensure deleted directory exists
            deleted_jobs_dir = "/config/local/jobs/deleted"
            os.makedirs(deleted_jobs_dir, exist_ok=True)

            # File paths
            config_file = f"/config/local/jobs/{job_name}.yaml"
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"

            # Add deleted_on timestamp to job config
            if os.path.exists(config_file):
                job_config = self.shared.load_yaml(config_file)
                if job_config:
                    job_config['deleted_on'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

                    # Write updated config to deleted location
                    self.shared.save_yaml(deleted_config_file, job_config)

                    # Remove original config file
                    os.remove(config_file)

            return True

        except Exception as e:
            print(f"Error deleting job {job_name}: {str(e)}")
            return False

    def restore_deleted_job(self, job_name: str) -> bool:
        """Restore a deleted job (move files back from deleted/ subdirectories)"""
        try:
            # Check if deleted job exists
            deleted_jobs = self._load_deleted_jobs()
            if job_name not in deleted_jobs:
                return False

            # Check if job name conflicts with existing active job
            active_jobs = self._load_backup_jobs()
            if job_name in active_jobs:
                print(f"Error: Job name '{job_name}' already exists in active jobs")
                return False

            # File paths
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"
            config_file = f"/config/local/jobs/{job_name}.yaml"

            # Restore config file
            if os.path.exists(deleted_config_file):
                job_config = self.shared.load_yaml(deleted_config_file)
                if job_config:
                    # Remove deleted_on timestamp
                    if 'deleted_on' in job_config:
                        del job_config['deleted_on']

                    # Write restored config to active location
                    self.shared.save_yaml(config_file, job_config)

                    # Remove from deleted location
                    os.remove(deleted_config_file)

            return True

        except Exception as e:
            print(f"Error restoring job {job_name}: {str(e)}")
            return False

    def purge_job(self, job_name: str) -> bool:
        """Permanently delete a job from deleted/ directories (irreversible)"""
        try:
            # Check if deleted job exists
            deleted_jobs = self._load_deleted_jobs()
            if job_name not in deleted_jobs:
                return False

            # File path for deleted job
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"

            # Remove config file
            if os.path.exists(deleted_config_file):
                os.remove(deleted_config_file)

            return True

        except Exception as e:
            print(f"Error purging job {job_name}: {str(e)}")
            return False

    def get_deleted_jobs(self) -> Dict[str, Any]:
        """Get all deleted jobs"""
        return self.config_reader.get_deleted_jobs()


