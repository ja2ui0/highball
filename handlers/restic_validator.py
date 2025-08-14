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
        
        repo_location = dest_config.get('repo_location')
        if not repo_location:
            return {
                'success': False,
                'message': 'Repository location is required for Restic destinations'
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
    def get_snapshot_statistics(job_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        repo_service = ResticRepositoryService()
        return repo_service.get_snapshot_statistics(job_config, snapshot_id)
    
    @staticmethod
    def browse_snapshot_directory(job_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse files and directories in a Restic snapshot"""
        repo_service = ResticRepositoryService()
        return repo_service.browse_directory(job_config, snapshot_id, path)