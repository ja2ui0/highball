"""
Origin SSH Service
SSH-specific workflows, validations, and key management for origins domain
"""

import logging
import json
import os
from typing import Dict, Any

from shared.handlers.templating import TemplateService
from shared.services.ssh import SSHWorkflowService

logger = logging.getLogger(__name__)

# =============================================================================
# **ORIGIN SSH SERVICE** - Domain-specific SSH operations
# =============================================================================

class OriginSSHService:
    """Service for origin-specific SSH operations and validations"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.ssh_workflow_service = SSHWorkflowService()
    
    def render_validation_status(self, result: Dict[str, Any]) -> str:
        """Render SSH source validation status with rsync and container engine details"""
        details = []
        
        # SSH connection always appears first when present (success or failure)
        if result.get('ssh_status') == 'OK':
            details.append("SSH connection successful")
            
            # Show rsync status with version (source validation only)
            rsync_status = result.get('rsync_status', '')
            if rsync_status and rsync_status != 'Not found':
                details.append(f"Rsync: {rsync_status}")
            elif rsync_status == 'Not found':
                details.append("Rsync: Not found")
            
            # Show container engine (source validation only)
            podman_status = result.get('podman_status', '')
            docker_status = result.get('docker_status', '')
            
            if podman_status and podman_status != 'Not found':
                details.append(f"Container Engine: {podman_status}")
            elif docker_status and docker_status != 'Not found':
                details.append(f"Container Engine: {docker_status}")
            else:
                details.append("Container Engine: Not found")
        
        # Determine status class and label
        if result.get('valid', False):
            status_class = 'success'
            status_label = '[OK]'
        else:
            status_class = 'error'
            status_label = '[ERROR]'
        
        # Build message from details or error
        if details:
            # Pass details as a list for proper formatting in template
            message = None
        else:
            # Use appropriate message based on validation result
            if result.get('valid', False):
                message = result.get('message', 'Validation successful')
            else:
                message = result.get('error', 'Validation failed')
            details = None
        
        # Use template service to render the result
        return self.template_service.render_template('partials/validation_result.html', 
                                       status_class=status_class,
                                       status_label=status_label,
                                       message=message,
                                       details=details)
    
    def push_keys_and_validate_workflow(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow: push keys -> validate connection -> detect capabilities"""
        # Delegate to shared SSH workflow service
        return self.ssh_workflow_service.push_keys_and_validate_workflow(hostname, username, password, use_password)
    
    def push_keys_and_validate_with_session(self, session_id: str, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow with session progress tracking using persistent storage"""
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        
        # Get the result from the SSH workflow service
        result = self.push_keys_and_validate_workflow(hostname, username, password, use_password)
        
        # Update session progress with service result
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                # Split the service's validation message into progress steps
                if result.get('validation_message'):
                    progress_lines = result['validation_message'].split('\n')
                    session_data['progress'] = progress_lines
                else:
                    session_data['progress'].append('" SSH validation completed')
                
                # Save updated progress
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
            except (json.JSONDecodeError, IOError):
                pass  # Ignore session update errors
        
        return result
    
    def validate_origin_string(self, origin_string: str) -> Dict[str, Any]:
        """Validate SSH origin configuration from username@hostname string"""
        # Parse origin string (format: username@hostname)
        if '@' not in origin_string:
            return {
                'valid': False,
                'error': 'Invalid format. Expected: username@hostname'
            }
        
        username, hostname = origin_string.split('@', 1)
        ssh_config = {'username': username, 'hostname': hostname}
        
        # Use unified validation service
        from jobs.services.validate import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        return result

    def get_auth_method_template_data(self, use_highball_auth: bool) -> Dict[str, Any]:
        """Get template name and context data for SSH auth method toggle"""
        if use_highball_auth:
            # Checkbox checked: show password field for automatic key installation
            return {
                'template': 'partials/ssh_auth_highball.html',
                'context': {}
            }
        else:
            # Checkbox unchecked: show manual key copy instructions
            return {
                'template': 'partials/ssh_auth_user.html',
                'context': {
                    'highball_public_key': self.get_highball_public_key()
                }
            }

    def get_highball_public_key(self) -> str:
        """Read Highball public key content"""
        try:
            with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
                return f.read().strip()
        except Exception as e:
            return f"Error reading public key: {str(e)}"