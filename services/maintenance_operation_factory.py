"""
Maintenance operation factory
Creates MaintenanceOperation objects from job configurations
"""
from typing import Dict, Any
from services.maintenance_operation import MaintenanceOperation
from services.maintenance_config_manager import MaintenanceConfigManager


class MaintenanceOperationFactory:
    """Factory for creating maintenance operations from job configurations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.config_manager = MaintenanceConfigManager(backup_config)
    
    def create_discard_operation(self, job_name: str) -> MaintenanceOperation:
        """Create discard operation for job (combines forget+prune)"""
        job_config = self._get_job_config(job_name)
        base_operation = self._create_base_operation(job_name, job_config, 'discard')
        
        # Add retention configuration
        base_operation.retention_config = self.config_manager.get_retention_policy(job_name)
        
        return base_operation
    
    def create_check_operation(self, job_name: str) -> MaintenanceOperation:
        """Create check operation for job"""
        job_config = self._get_job_config(job_name)
        base_operation = self._create_base_operation(job_name, job_config, 'check')
        
        # Add check configuration
        base_operation.check_config = self.config_manager.get_check_config(job_name)
        
        return base_operation
    
    def _create_base_operation(self, job_name: str, job_config: Dict[str, Any], operation_type: str) -> MaintenanceOperation:
        """Create base maintenance operation from job config"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        # Build repository URL and environment
        repository_url = dest_config.get('repo_uri', dest_config.get('dest_string', ''))
        environment_vars = self._build_environment_vars(dest_config)
        
        # SSH config for remote operations
        ssh_config = None
        if source_config.get('hostname'):
            ssh_config = {
                'hostname': source_config['hostname'],
                'username': source_config.get('username', 'root')
            }
        
        return MaintenanceOperation(
            operation_type=operation_type,
            job_name=job_name,
            repository_url=repository_url,
            environment_vars=environment_vars,
            ssh_config=ssh_config,
            container_runtime=job_config.get('container_runtime', 'docker')
        )
    
    def _get_job_config(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration from backup config"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        return jobs.get(job_name, {})
    
    def _build_environment_vars(self, dest_config: Dict[str, Any]) -> Dict[str, str]:
        """Build environment variables for Restic execution"""
        env_vars = {}
        
        # Repository password
        password = dest_config.get('password', '')
        if password:
            env_vars['RESTIC_PASSWORD'] = password
        
        # Repository-specific environment variables
        repo_type = dest_config.get('repo_type', 'local')
        if repo_type == 'rest':
            # REST server specific variables could go here
            pass
        elif repo_type == 's3':
            # S3 specific variables
            if dest_config.get('aws_access_key_id'):
                env_vars['AWS_ACCESS_KEY_ID'] = dest_config['aws_access_key_id']
            if dest_config.get('aws_secret_access_key'):
                env_vars['AWS_SECRET_ACCESS_KEY'] = dest_config['aws_secret_access_key']
        
        return env_vars