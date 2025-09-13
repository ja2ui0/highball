"""
Jobs Restic Service
Job-scoped restic operations with proper host+path filtering
"""

import logging
from typing import Dict, Any, Optional, Tuple
from shared.handlers.errors import handle_service_errors
from jobs.services.config import JobConfigService

logger = logging.getLogger(__name__)


class ResticJobValidator:
    """Job validation for restic operations"""

    def __init__(self):
        self.job_config = JobConfigService()

    def validate_job(self, job_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Validate job exists and return config, or return error"""
        if not job_name:
            return None, {'success': False, 'error': 'Job name is required'}

        jobs = self.job_config.get_backup_jobs()
        if job_name not in jobs:
            return None, {'success': False, 'error': f"Job '{job_name}' not found"}

        return jobs[job_name], None


class ResticJobSnapshots:
    """Job-scoped snapshot operations with host+path filtering"""

    def __init__(self):
        self.validator = ResticJobValidator()

    @handle_service_errors("List snapshots")
    def list_snapshots(self, job_name: str):
        """List snapshots for a job - filtered by job's host+paths"""
        job_config, error = self.validator.validate_job(job_name)
        if error:
            return error

        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        filters = {'job_name': job_name}

        from jobs.services.backup import backup_service
        result = backup_service.list_snapshots(dest_config, filters, source_config)
        return result

    @handle_service_errors("Get snapshot stats")
    def get_snapshot_stats(self, job_name: str, snapshot_id: str):
        """Get statistics for a specific snapshot - job-scoped"""
        if not snapshot_id:
            return {'success': False, 'error': 'Snapshot ID is required'}

        job_config, error = self.validator.validate_job(job_name)
        if error:
            return error

        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})

        from jobs.services.backup import backup_service
        result = backup_service.get_snapshot_statistics(dest_config, snapshot_id, source_config)
        return result

    @handle_service_errors("Browse directory")
    def browse_directory(self, job_name: str, snapshot_id: str, path: str = '/'):
        """Browse directory contents in a snapshot - job-scoped"""
        if not snapshot_id:
            return {'success': False, 'error': 'Snapshot ID is required'}

        job_config, error = self.validator.validate_job(job_name)
        if error:
            return error

        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})

        from jobs.services.backup import backup_service
        result = backup_service.browse_snapshot_directory(dest_config, snapshot_id, path, source_config)
        return result


# Service instances for import
restic_job_validator = ResticJobValidator()
restic_job_snapshots = ResticJobSnapshots()