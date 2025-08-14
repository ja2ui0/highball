"""
Abstract base class for backup repository services.
Defines common interface for Restic, Borg, Kopia providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class RepositoryService(ABC):
    """Abstract base class for backup repository operations"""
    
    @abstractmethod
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test if repository is accessible and get basic info"""
        pass
    
    @abstractmethod
    def list_snapshots(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """List all snapshots in the repository"""
        pass
    
    @abstractmethod
    def get_snapshot_statistics(self, job_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        pass
    
    @abstractmethod
    def browse_directory(self, job_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse files and directories in a snapshot"""
        pass
    
    def _should_use_ssh(self, source_config: Optional[Dict[str, Any]]) -> bool:
        """Determine if SSH execution should be used"""
        return source_config and source_config.get('hostname') and source_config.get('username')
    
    def _format_error_response(self, error_message: str) -> Dict[str, Any]:
        """Standard error response format"""
        return {
            'success': False,
            'error': error_message
        }
    
    def _format_success_response(self, data: Any) -> Dict[str, Any]:
        """Standard success response format"""
        return {
            'success': True,
            **data
        }