"""
Origin SSH Service
SSH-specific workflows, validations, and key management for origins domain
"""

import logging
import json
import os
import subprocess
from typing import Dict, Any
from datetime import datetime

from shared.handlers.templating import TemplateService
from shared.services.ssh import SSHWorkflowService
from shared.services.ssh import SSHCommandFactory
from shared.handlers.errors import handle_service_errors

logger = logging.getLogger(__name__)

# =============================================================================
# **ORIGIN SSH SERVICE** - Domain-specific SSH operations
# =============================================================================

class OriginSSHService:
    """Service for origin-specific SSH operations and validations"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.ssh_workflow_service = SSHWorkflowService()
        self.ssh_factory = SSHCommandFactory()
        self._validation_cache = {}
        self.cache_duration = 1800  # 30 minutes
    
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
    
    def run_validation_workflow(self, session_id: str, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete validation workflow with session progress tracking"""
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        
        # Get the result from the SSH workflow service (handles both push_keys AND validate)
        result = self.ssh_workflow_service.push_keys_and_validate_workflow(hostname, username, password, use_password)
        
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
                    session_data['progress'].append('• SSH validation completed')
                
                # Save updated progress
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
            except (json.JSONDecodeError, IOError):
                pass  # Ignore session update errors
        
        return result

    @handle_service_errors("Validate SSH source")
    def validate_ssh_source(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SSH source configuration with capability detection"""
        hostname = source_config.get('hostname', '')
        username = source_config.get('username', '')
        
        if not hostname or not username:
            return {'valid': False, 'error': 'Hostname and username are required'}
        
        # Check cache first
        cache_key = f"ssh:{username}@{hostname}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Test basic SSH connectivity
            ssh_test = self._test_ssh_connection(hostname, username)
            if not ssh_test['success']:
                result = {'valid': False, 'error': ssh_test['error']}
                self._cache_result(cache_key, result)
                return result
            
            # Test rsync availability and get version
            rsync_test = self._test_rsync_availability(hostname, username)
            
            # Test container runtimes and get versions
            podman_test = self._test_container_runtime(hostname, username, 'podman')
            docker_test = self._test_container_runtime(hostname, username, 'docker')
            
            # Determine preferred container runtime
            container_runtime = None
            if podman_test['success']:
                container_runtime = 'podman'
            elif docker_test['success']:
                container_runtime = 'docker'
            
            result = {
                'valid': True,
                'ssh_status': 'OK',
                'rsync_status': rsync_test.get('version', 'Available') if rsync_test['success'] else rsync_test.get('error', 'Not found'),
                'podman_status': podman_test.get('version', 'Available') if podman_test['success'] else podman_test.get('error', 'Not found'), 
                'docker_status': docker_test.get('version', 'Available') if docker_test['success'] else docker_test.get('error', 'Not found'),
                'container_runtime': container_runtime,
                'tested_at': datetime.now().isoformat()
            }
            
            self._cache_result(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"SSH validation error for {hostname}: {e}")
            result = {'valid': False, 'error': f'SSH validation failed: {str(e)}'}
            self._cache_result(cache_key, result)
            return result

    def _test_ssh_connection(self, hostname: str, username: str) -> Dict[str, Any]:
        """Test basic SSH connectivity"""
        try:
            cmd = self.ssh_factory.build_ssh_command(
                hostname, username, 
                'echo "SSH_OK"',
                connect_timeout=10
            )
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and 'SSH_OK' in result.stdout:
                return {'success': True}
            else:
                return {'success': False, 'error': f'SSH connection failed: {result.stderr.strip()}'}
                
        except Exception as e:
            return {'success': False, 'error': f'SSH test failed: {str(e)}'}

    def _test_rsync_availability(self, hostname: str, username: str) -> Dict[str, Any]:
        """Test rsync availability and get version on remote host"""
        try:
            cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                'rsync --version 2>&1 | head -1',
                connect_timeout=10
            )
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and 'rsync' in result.stdout.lower():
                version_line = result.stdout.strip().split('\n')[0]
                return {'success': True, 'version': version_line}
            else:
                return {'success': False, 'error': 'Not found'}
                
        except Exception as e:
            return {'success': False, 'error': f'Test error: {str(e)}'}

    def _test_container_runtime(self, hostname: str, username: str, runtime: str) -> Dict[str, Any]:
        """Test container runtime (podman/docker) availability and get version"""
        try:
            cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                f'{runtime} --version 2>&1',
                connect_timeout=10
            )
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and runtime in result.stdout.lower():
                version_line = result.stdout.strip().split('\n')[0]
                return {'success': True, 'version': version_line}
            else:
                return {'success': False, 'error': 'Not found'}
                
        except Exception as e:
            return {'success': False, 'error': f'Test error: {str(e)}'}

    def _get_cached_result(self, cache_key: str) -> Dict[str, Any]:
        """Get cached validation result if still valid"""
        if cache_key in self._validation_cache:
            cached_entry = self._validation_cache[cache_key]
            cache_age = datetime.now().timestamp() - cached_entry['timestamp']
            if cache_age < self.cache_duration:
                return cached_entry['result']
            else:
                del self._validation_cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache validation result with timestamp"""
        self._validation_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now().timestamp()
        }
    
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

    def create_validation_session(self, hostname: str, username: str, password: str, ssh_highball: bool, edit_mode: bool) -> str:
        """Create and initialize a validation session, return session ID"""
        import uuid
        import json
        import os
        
        # Business validation rules
        if ssh_highball and not password:
            raise ValueError('Password is required when "Auto-populate keys using Highball" is checked.')
        
        # Generate session ID and create persistent session file
        session_id = str(uuid.uuid4())
        session_dir = '/tmp/ssh_validation_sessions'
        os.makedirs(session_dir, exist_ok=True)
        session_file = f"{session_dir}/{session_id}.json"
        
        # Initialize session data
        session_data = {
            'progress': ['• Starting SSH validation workflow...'],
            'completed': False,
            'success': None,
            'result': None,
            'edit_mode': edit_mode
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        
        # Start background workflow
        self.start_validation_workflow(session_id, hostname, username, password, ssh_highball and password)
        
        return session_id

    def start_validation_workflow(self, session_id: str, hostname: str, username: str, password: str, use_password: bool) -> None:
        """Start background validation workflow in separate thread"""
        import threading
        import json
        
        def run_workflow():
            session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
            try:
                # Run the actual validation work
                result = self.run_validation_workflow(session_id, hostname, username, password, use_password)
                # Update session with completion
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                session_data['completed'] = True
                session_data['result'] = result
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
            except Exception as e:
                # Handle workflow errors
                error_result = {
                    'success': False,
                    'validation_message': f'Validation failed: {str(e)}'
                }
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)
                    session_data['completed'] = True
                    session_data['result'] = error_result
                    with open(session_file, 'w') as f:
                        json.dump(session_data, f)
                except:
                    pass  # Ignore session update errors
        
        threading.Thread(target=run_workflow, daemon=True).start()

    def read_session_progress(self, session_id: str) -> Dict[str, Any]:
        """Read validation session progress and completion status"""
        import json
        import os
        
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        
        if not os.path.exists(session_file):
            return {
                'exists': False,
                'progress': [],
                'completed': False,
                'result': None,
                'edit_mode': False
            }
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            return {
                'exists': True,
                'progress': session_data.get('progress', []),
                'completed': session_data.get('completed', False),
                'result': session_data.get('result'),
                'edit_mode': session_data.get('edit_mode', False)
            }
        except (json.JSONDecodeError, IOError):
            return {
                'exists': False,
                'progress': [],
                'completed': False,
                'result': None,
                'edit_mode': False
            }
    
    def cleanup_session(self, session_id: str) -> None:
        """Clean up validation session file"""
        import os
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        try:
            os.remove(session_file)
        except OSError:
            pass

    def get_highball_public_key(self) -> str:
        """Read Highball public key content"""
        try:
            with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
                return f.read().strip()
        except Exception as e:
            return f"Error reading public key: {str(e)}"