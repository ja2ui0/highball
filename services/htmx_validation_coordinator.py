"""
HTMX Validation Coordinator Service
Coordinates validation operations and delegates to appropriate validators
"""

import logging
from services.ssh_validator import SSHValidator
from services.job_validator import JobValidator
from services.source_path_validator import SourcePathValidator
from services.htmx_validation_renderer import HTMXValidationRenderer

logger = logging.getLogger(__name__)

class HTMXValidationCoordinator:
    """Coordinates validation operations for HTMX endpoints"""
    
    def __init__(self):
        self.ssh_validator = SSHValidator()
        self.job_validator = JobValidator()
        self.renderer = HTMXValidationRenderer()
    
    def validate_ssh_connection(self, form_data):
        """Handle SSH connection validation"""
        try:
            # Extract SSH parameters
            hostname = form_data.get('source_ssh_hostname', [''])[0] or form_data.get('dest_ssh_hostname', [''])[0]
            username = form_data.get('source_ssh_username', [''])[0] or form_data.get('dest_ssh_username', [''])[0]
            path = form_data.get('dest_ssh_path', [''])[0] if 'dest_ssh_path' in form_data else ''
            
            if not hostname or not username:
                return self.renderer.render_error("Please fill in hostname and username")
            
            # Build SSH source string for validation
            if path:
                ssh_source = f"{username}@{hostname}:{path}"
            else:
                ssh_source = f"{username}@{hostname}"
            
            # Perform validation using the correct method
            result = self.ssh_validator.validate_ssh_source(ssh_source)
            
            if result.success:
                # Check for container runtime detection and add hidden field
                details = result.details or {}
                container_runtime_html = ""
                
                # If this is SSH source validation and we detected container runtime, add hidden field
                if (hostname and username and 
                    form_data.get('source_ssh_hostname') and 
                    details.get('container_runtime')):
                    
                    runtime_info = details['container_runtime']
                    runtime = 'podman' if 'podman' in runtime_info.lower() else 'docker'
                    container_runtime_html = f'<input type="hidden" name="container_runtime" value="{runtime}">'
                
                # Enhanced success message with detailed breakdown
                details_list = []
                if details.get('ssh_status'):
                    details_list.append(f"SSH: {details['ssh_status']}")
                if details.get('rsync_status'):
                    details_list.append(f"Rsync: {details['rsync_status']}")
                if details.get('container_runtime'):
                    details_list.append(f"Container: {details['container_runtime']}")
                if details.get('path_status'):
                    details_list.append(f"Path: {details['path_status']}")
                
                details_html = '<br>'.join(details_list) if details_list else ''
                
                success_html = f'''
                <div class="validation-success">
                    <span class="validation-status">[OK] {result.message}</span>
                    {f'<div class="validation-details">{details_html}</div>' if details_html else ''}
                </div>
                {container_runtime_html}
                '''
                
                return success_html
            else:
                return self.renderer.render_error(result.message)
                
        except Exception as e:
            logger.error(f"SSH validation error: {e}")
            return self.renderer.render_error(f"Validation failed: {str(e)}")
    
    def validate_source_paths(self, form_data):
        """Handle source path validation"""
        try:
            # Use existing source path validation logic
            result = self.job_validator.validate_source_paths(form_data)
            
            if result['valid']:
                return self.renderer.render_success("Source paths validated", result.get('details', {}))
            else:
                return self.renderer.render_error(result['error'])
                
        except Exception as e:
            logger.error(f"Source path validation error: {e}")
            return self.renderer.render_error(f"Path validation failed: {str(e)}")
    
    def validate_single_source_path(self, form_data):
        """Validate a single source path with RX/RWX permission checking"""
        try:
            # Extract path from the specific index or first available
            paths = form_data.get('source_paths[]', [])
            if not isinstance(paths, list):
                paths = [paths] if paths else []
            
            path_index = int(form_data.get('path_index', ['0'])[0])
            path = paths[path_index] if path_index < len(paths) else ''
            
            source_type = form_data.get('source_type', [''])[0]
            hostname = form_data.get('source_ssh_hostname', [''])[0] 
            username = form_data.get('source_ssh_username', [''])[0]
            
            if not path:
                return self.renderer.render_error("Please enter a path")
            
            # Build source config for proper validation
            source_config = {
                'source_type': source_type,
                'source_paths': [{'path': path, 'includes': [], 'excludes': []}]
            }
            
            if source_type == 'ssh':
                source_config.update({
                    'hostname': hostname,
                    'username': username
                })
            
            # Use the proper source path validator with RX/RWX checking
            result = SourcePathValidator.validate_source_paths(source_config)
            
            if result['success'] and result['paths_detail']:
                path_result = result['paths_detail'][0]  # First (and only) path
                
                if path_result.get('can_backup') and path_result.get('can_restore_to_source'):
                    return self.renderer.render_success("[OK] Path is RWX", path_result)
                elif path_result.get('can_backup') and not path_result.get('can_restore_to_source'):
                    return self.renderer.render_warning("[WARN] Path is RO - can backup but cannot restore to source", path_result)
                else:
                    return self.renderer.render_error("[ERROR] Insufficient permissions", path_result)
            else:
                # Path validation failed
                if result['paths_detail']:
                    path_result = result['paths_detail'][0]
                    return self.renderer.render_error(f"[ERROR] {path_result.get('message', 'Path validation failed')}")
                else:
                    return self.renderer.render_error(f"[ERROR] {result.get('message', 'Path validation failed')}")
                
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return self.renderer.render_error(f"Validation failed: {str(e)}")