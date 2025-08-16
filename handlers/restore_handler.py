"""
Restore handler for processing backup restore requests (Refactored)
Thin HTTP coordinator that delegates to specialized services
"""
import json
from typing import Dict, Any, List
from services.restore_execution_service import RestoreExecutionService
from services.restore_overwrite_checker import RestoreOverwriteChecker


class RestoreHandler:
    """Handles backup restore operations - thin HTTP coordinator"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.execution_service = RestoreExecutionService()
        self.overwrite_checker = RestoreOverwriteChecker()
    
    def process_restore_request(self, handler, form_data):
        """Process restore request from job inspect page"""
        try:
            # Parse and validate form data
            restore_config = self._parse_restore_form_data(form_data)
            if 'error' in restore_config:
                return self._send_error_response(handler, restore_config['error'])
            
            # Get job configuration
            job_config = self._get_job_config(restore_config['job_name'])
            if 'error' in job_config:
                return self._send_error_response(handler, job_config['error'])
            
            # Validate job type
            if job_config.get('dest_type', '') != 'restic':
                return self._send_error_response(handler, f'Restore not supported for job type: {job_config.get("dest_type", "")}')
            
            # Check for active restore
            if self.execution_service.is_restore_active(restore_config['job_name']):
                return self._send_error_response(handler, f'Restore already in progress for job: {restore_config["job_name"]}')
            
            # Execute based on dry run flag
            if restore_config.get('dry_run', False):
                result = self.execution_service.execute_dry_run(job_config, restore_config)
                return self._send_json_response(handler, result)
            else:
                self.execution_service.start_background_restore(job_config, restore_config)
                return self._send_json_response(handler, {
                    'success': True,
                    'message': f'Restore started for job: {restore_config["job_name"]}',
                    'job_name': restore_config['job_name']
                })
                
        except Exception as e:
            return self._send_error_response(handler, f'Restore request failed: {str(e)}')
    
    def check_restore_overwrites(self, handler, form_data):
        """Check if restore would overwrite existing files at source"""
        try:
            # Parse form data
            job_name = self._safe_get_form_value(form_data, 'job_name')
            snapshot_id = self._safe_get_form_value(form_data, 'snapshot_id')
            select_all = self._safe_get_form_value(form_data, 'select_all') == 'on'
            selected_paths = form_data.get('selected_paths', [''])
            restore_target = self._safe_get_form_value(form_data, 'restore_target', 'highball')
            
            # Validate required fields
            if not job_name:
                return self._send_json_response(handler, {'hasOverwrites': False, 'error': 'Job name required'})
            
            # Get job configuration
            job_config = self._get_job_config(job_name)
            if 'error' in job_config:
                return self._send_json_response(handler, {'hasOverwrites': False, 'error': job_config['error']})
            
            source_config = job_config.get('source_config', {})
            source_type = job_config.get('source_type', '')
            
            # Get paths to check based on restore selection
            check_paths = self._determine_check_paths(source_config, select_all, selected_paths)
            
            # Check for overwrites using the overwrite checker service
            has_overwrites = self.overwrite_checker.check_restore_overwrites(
                restore_target, source_type, source_config, check_paths, select_all
            )
            
            return self._send_json_response(handler, {'hasOverwrites': has_overwrites})
            
        except Exception as e:
            return self._send_json_response(handler, {'hasOverwrites': False, 'error': str(e)})
    
    def get_restore_status(self, job_name: str) -> Dict[str, Any]:
        """Get current restore status for a job"""
        return self.execution_service.get_restore_status(job_name)
    
    def _parse_restore_form_data(self, form_data: Dict[str, List[str]]) -> Dict[str, Any]:
        """Parse and validate restore form data"""
        # Extract form fields
        job_name = self._safe_get_form_value(form_data, 'job_name')
        snapshot_id = self._safe_get_form_value(form_data, 'snapshot_id')
        restore_target = self._safe_get_form_value(form_data, 'restore_target', 'highball')
        dry_run = self._safe_get_form_value(form_data, 'dry_run') == 'on'
        select_all = self._safe_get_form_value(form_data, 'select_all') == 'on'
        selected_paths = form_data.get('selected_paths', [''])
        password = self._safe_get_form_value(form_data, 'password', '')
        
        # Validate required fields
        if not job_name:
            return {'error': 'Job name is required'}
        
        if not snapshot_id and not select_all:
            return {'error': 'Snapshot ID is required'}
        
        # Build configuration
        return {
            'job_name': job_name,
            'snapshot_id': snapshot_id,
            'restore_target': restore_target,
            'dry_run': dry_run,
            'select_all': select_all,
            'selected_paths': [path for path in selected_paths if path.strip()],
            'password': password
        }
    
    def _get_job_config(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration with error handling"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        if job_name not in jobs:
            return {'error': f'Job not found: {job_name}'}
        
        job_config = jobs[job_name]
        # Add job name to config for services that need it
        job_config['name'] = job_name
        return job_config
    
    def _determine_check_paths(self, source_config: Dict[str, Any], select_all: bool, selected_paths: List[str]) -> List[str]:
        """Determine which paths to check for overwrites"""
        if select_all:
            # For select all, check job's source paths
            source_paths = source_config.get('source_paths', [])
            check_paths = []
            for path_config in source_paths:
                if isinstance(path_config, dict):
                    check_paths.append(path_config.get('path', ''))
                else:
                    check_paths.append(str(path_config))
            return check_paths
        else:
            # For specific selection, check selected paths
            return [path for path in selected_paths if path.strip()]
    
    def _safe_get_form_value(self, form_data: Dict[str, List[str]], key: str, default: str = '') -> str:
        """Safely get form value with default"""
        return form_data.get(key, [default])[0] if form_data.get(key) else default
    
    def _send_json_response(self, handler, data: Dict[str, Any]):
        """Send JSON response"""
        handler.send_response(200)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        
        response = json.dumps(data, indent=2)
        handler.wfile.write(response.encode('utf-8'))
    
    def _send_error_response(self, handler, error_message: str):
        """Send error response"""
        error_data = {
            'success': False,
            'error': error_message
        }
        self._send_json_response(handler, error_data)