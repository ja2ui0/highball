"""
Unified Data Services
Consolidates form data building and snapshot introspection
Replaces: job_form_data_builder.py, snapshot_introspection_service.py
"""
from typing import Dict, List, Optional, Any
from models.forms import JobFormData, SourceConfig, DestConfig, ResticConfig, NotificationConfig
from origins.schema import SOURCE_PATH_SCHEMA
from services.execution import ExecutionService, OperationType


# =============================================================================
# **FORM DATA BUILDING CONCERN** - JobFormData creation and population
# =============================================================================





# =============================================================================
# **SNAPSHOT INTROSPECTION CONCERN** - Discovery of paths and metadata from snapshots
# =============================================================================



# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates form building and introspection
# =============================================================================

class DataService:
    """Unified data service - ONLY coordinates form building and introspection concerns"""
    
    def __init__(self):
        from jobs.services.define import JobFormDataBuilder
        self.form_builder = JobFormDataBuilder()
        from jobs.services.restore import SnapshotIntrospectionService
        self.introspection = SnapshotIntrospectionService()
    
    # **FORM BUILDING DELEGATION** - Pure delegation to building concern
    def build_job_form_data_from_config(self, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from job config"""
        return self.form_builder.from_job_config(job_name, job_config)
    
    def build_job_form_data_from_form(self, form_data: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from form submission"""
        return self.form_builder.from_form_data(form_data)
    
    # **INTROSPECTION DELEGATION** - Pure delegation to introspection concern
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """Delegation: get snapshot source paths"""
        return self.introspection.get_snapshot_source_paths(
            snapshot_id, repository_url, dest_config, ssh_config, container_runtime
        )
    
    def get_snapshot_metadata(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> Dict[str, Any]:
        """Delegation: get snapshot metadata"""
        return self.introspection.get_snapshot_metadata(
            snapshot_id, repository_url, dest_config, ssh_config, container_runtime
        )


# =============================================================================
# DESTINATION TYPE SERVICE - following notification service pattern
# =============================================================================

class DestinationTypeService:
    """Service for managing destination type availability and options"""
    
    def get_available_destination_types(self, source_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get list of available destination types with their metadata"""
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
        available_types = []
        
        for dest_type, schema in DESTINATION_TYPE_SCHEMAS.items():
            if self._is_destination_available(dest_type, schema, source_config):
                available_types.append({
                    'value': dest_type,
                    'display_name': schema['display_name'],
                    'description': schema['description']
                })
        
        return available_types
    
    def _is_destination_available(self, dest_type: str, schema: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a destination type is available"""
        
        # Always available types
        if schema.get('always_available', False):
            return True
        
        # Check specific availability function if defined
        if 'availability_check' in schema:
            check_method = getattr(self, schema['availability_check'], None)
            if check_method:
                return check_method(source_config)
        
        # Default: assume available if no specific check
        return True
    
    def check_restic_availability(self, source_config: Optional[Dict[str, Any]] = None) -> bool:
        """Check if Restic is available as a destination type"""
        try:
            # For SSH sources, check container runtime availability on source
            if source_config and source_config.get('hostname'):
                container_runtime = source_config.get('container_runtime')
                return container_runtime in ['docker', 'podman']
            
            # For local sources, always available (Highball container has restic)
            return True
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error checking restic availability: {e}")
            return False

class ResticRepositoryTypeService:
    """Service for managing restic repository type availability and options"""
    
    def get_available_repository_types(self) -> List[Dict[str, Any]]:
        """Get list of available restic repository types with their metadata"""
        from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        available_types = []
        
        for repo_type, schema in RESTIC_REPOSITORY_TYPE_SCHEMAS.items():
            if self._is_repository_type_available(repo_type, schema):
                available_types.append({
                    'value': repo_type,
                    'display_name': schema['display_name'],
                    'description': schema['description']
                })
        
        return available_types
    
    def _is_repository_type_available(self, repo_type: str, schema: Dict[str, Any]) -> bool:
        """Check if a repository type is available"""
        # All repository types are always available - no special requirements
        return schema.get('always_available', True)