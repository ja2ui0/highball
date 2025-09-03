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
# REMAINING CONTENT - All major services have been migrated to domain-specific locations
# =============================================================================

# This file now only contains the DataService facade
# Destination services have been moved to:
# - DestinationTypeService → dests/services/types.py  
# - ResticRepositoryTypeService → dests/services/restic.py