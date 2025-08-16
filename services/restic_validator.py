"""
Restic validation orchestrator.
Thin wrapper that delegates to specialized services for validation,
repository operations, and binary management.
"""

from typing import Dict, Any, Optional
from services.restic_repository_service import ResticRepositoryService
from services.binary_checker_service import BinaryCheckerService


class ResticValidator:
    """Validates Restic backup configurations using specialized services"""
    
    @staticmethod
    def validate_restic_destination(parsed_job: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Restic destination configuration"""
        dest_config = parsed_job.get('dest_config', {})
        source_config = parsed_job.get('source_config', {})
        
        # Check required fields
        repo_type = dest_config.get('repo_type')
        if not repo_type:
            return {
                'success': False,
                'message': 'Repository type is required for Restic destinations'
            }
        
        repo_uri = dest_config.get('repo_uri')
        if not repo_uri:
            return {
                'success': False,
                'message': 'Repository URI is required for Restic destinations'
            }
        
        password = dest_config.get('password')
        if not password:
            return {
                'success': False,
                'message': 'Repository password is required for Restic destinations'
            }
        
        # Test repository access
        repo_service = ResticRepositoryService()
        repo_test = repo_service.test_repository_access(parsed_job)
        
        # Check for content analysis if repository exists
        if repo_test.get('repository_status') == 'existing' and repo_test.get('snapshot_count', 0) > 0:
            from services.restic_content_analyzer import ResticContentAnalyzer
            
            content_analysis = ResticContentAnalyzer.compare_source_to_repository(
                dest_config, source_config, parsed_job.get('source_type')
            )
            
            # Merge content analysis with repository test results
            repo_test.update({
                'content_analysis': content_analysis
            })
        
        return repo_test
    
    @staticmethod
    def check_restic_binary(source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check if restic binary is available on source system"""
        return BinaryCheckerService.check_binary_availability('restic', source_config)
    
    @staticmethod
    def check_rclone_binary(source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check if rclone binary is available on source system"""
        return BinaryCheckerService.check_binary_availability('rclone', source_config)
    
    @staticmethod
    def validate_restic_repository_access(dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate Restic repository access"""
        job_config = {
            'dest_config': dest_config,
            'source_config': source_config or {}
        }
        
        repo_service = ResticRepositoryService()
        return repo_service.test_repository_access(job_config)
    
    @staticmethod
    def list_repository_snapshots(job_config: Dict[str, Any]) -> Dict[str, Any]:
        """List all snapshots in a Restic repository"""
        repo_service = ResticRepositoryService()
        return repo_service.list_snapshots(job_config)
    
    @staticmethod
    def initialize_restic_repository(job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        from services.restic_runner import ResticRunner
        
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        # Check required fields first
        repo_type = dest_config.get('repo_type')
        if not repo_type:
            return {
                'success': False,
                'message': 'Repository type is required for Restic destinations'
            }
        
        repo_uri = dest_config.get('repo_uri')
        if not repo_uri:
            return {
                'success': False,
                'message': 'Repository URI is required for Restic destinations'
            }
        
        password = dest_config.get('password')
        if not password:
            return {
                'success': False,
                'message': 'Repository password is required for Restic destinations'
            }
        
        # First check if repository already exists
        repo_service = ResticRepositoryService()
        existing_test = repo_service.test_repository_access(job_config)
        
        if existing_test.get('success') and existing_test.get('repository_status') == 'existing':
            return {
                'success': False,
                'message': f'Repository already exists at {repo_uri}',
                'details': existing_test.get('details', {}),
                'repository_status': 'existing'
            }
        
        try:
            # Use ResticRunner to initialize repository
            runner = ResticRunner()
            
            # Create init command
            init_config = {
                'dest_config': dest_config,
                'source_config': source_config,
                'auto_init': True  # Force initialization
            }
            
            commands = runner.plan_init_repository(init_config)
            
            if not commands:
                return {
                    'success': False,
                    'message': 'Failed to plan repository initialization'
                }
            
            # Execute the init command
            init_command = commands[0]  # Should be just one init command
            
            if source_config.get('hostname'):
                # SSH execution - use container command and let execution service handle SSH
                container_cmd = init_command._build_container_command(init_config)
                from services.command_execution_service import CommandExecutionService
                executor = CommandExecutionService()
                result = executor.execute_container_via_ssh(
                    source_config['hostname'], 
                    source_config['username'], 
                    container_cmd
                )
            else:
                # Local execution
                local_cmd = init_command.to_local_command()
                from services.command_execution_service import CommandExecutionService
                executor = CommandExecutionService()
                result = executor.execute_locally(local_cmd)
            
            if result.success:
                return {
                    'success': True,
                    'message': f'Repository initialized successfully at {repo_uri}',
                    'repository_status': 'initialized',
                    'tested_from': source_config.get('hostname', 'Local container'),
                    'details': {
                        'repo_uri': repo_uri,
                        'repo_type': repo_type
                    }
                }
            else:
                return {
                    'success': False,
                    'message': f'Repository initialization failed: {result.stderr}',
                    'details': result.stderr
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Repository initialization error: {str(e)}'
            }
    
    @staticmethod
    def get_snapshot_statistics(job_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        repo_service = ResticRepositoryService()
        return repo_service.get_snapshot_statistics(job_config, snapshot_id)
    
    @staticmethod
    def browse_snapshot_directory(job_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse files and directories in a Restic snapshot"""
        repo_service = ResticRepositoryService()
        return repo_service.browse_directory(job_config, snapshot_id, path)
    
    @staticmethod
    def init_repository(parsed_job: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        repo_service = ResticRepositoryService()
        return repo_service.init_repository(parsed_job)