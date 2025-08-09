"""
SSH validation service for remote backup sources
Validates SSH connectivity and permissions before job creation
"""

import subprocess
import re
from datetime import datetime

class SSHValidator:
    """Validates SSH connections and remote paths for backup jobs"""
    
    @staticmethod
    def parse_ssh_source(source):
        """Parse SSH source into components"""
        # Match pattern: user@hostname:/path
        match = re.match(r'^([^@]+)@([^:]+):(.+)$', source)
        if not match:
            return None
        
        return {
            'user': match.group(1),
            'hostname': match.group(2), 
            'path': match.group(3)
        }
    
    @staticmethod
    def validate_ssh_connection(user, hostname, timeout=10):
        """Test SSH connection to remote host"""
        try:
            # Test basic SSH connectivity
            cmd = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 
                   f'{user}@{hostname}', 'echo "SSH_OK"']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0 and 'SSH_OK' in result.stdout:
                return {'success': True, 'message': 'SSH connection successful'}
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                return {'success': False, 'message': f'SSH connection failed: {error_msg}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'SSH connection timed out'}
        except Exception as e:
            return {'success': False, 'message': f'SSH test error: {str(e)}'}
    
    @staticmethod
    def validate_remote_path(user, hostname, path, timeout=10):
        """Test if remote path exists and is accessible for rsync operations"""
        try:
            # Test both read access AND directory listing capability
            # rsync needs to be able to list contents, not just read the path
            cmd = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                   f'{user}@{hostname}', 
                   f'test -r "{path}" && ls -1 "{path}" >/dev/null 2>&1 && echo "PATH_OK"']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0 and 'PATH_OK' in result.stdout:
                return {'success': True, 'message': f'Remote path {path} is accessible and listable'}
            else:
                # More specific error messages
                if 'Permission denied' in result.stderr:
                    return {'success': False, 'message': f'Permission denied accessing {path}'}
                elif 'No such file or directory' in result.stderr:
                    return {'success': False, 'message': f'Remote path {path} does not exist'}
                else:
                    return {'success': False, 'message': f'Remote path {path} not accessible for backup operations'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'Remote path test timed out'}
        except Exception as e:
            return {'success': False, 'message': f'Path test error: {str(e)}'}
    
    @staticmethod
    def validate_rsync_capability(user, hostname, timeout=10):
        """Test if rsync is available on remote host"""
        try:
            cmd = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                   f'{user}@{hostname}', 'which rsync']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                rsync_path = result.stdout.strip()
                return {'success': True, 'message': f'rsync available at {rsync_path}'}
            else:
                return {'success': False, 'message': 'rsync not found on remote host'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'rsync test timed out'}
        except Exception as e:
            return {'success': False, 'message': f'rsync test error: {str(e)}'}
    
    @classmethod
    def validate_ssh_source(cls, source):
        """Complete validation of SSH source"""
        # Parse source
        parsed = cls.parse_ssh_source(source)
        if not parsed:
            return {
                'success': False,
                'message': 'Invalid SSH source format. Use: user@hostname:/path'
            }
        
        user = parsed['user']
        hostname = parsed['hostname']
        path = parsed['path']
        
        # Test SSH connection
        ssh_result = cls.validate_ssh_connection(user, hostname)
        if not ssh_result['success']:
            return {
                'success': False,
                'message': f'SSH Connection Failed: {ssh_result["message"]}',
                'details': {
                    'step': 'ssh_connection',
                    'user': user,
                    'hostname': hostname
                }
            }
        
        # Test rsync availability
        rsync_result = cls.validate_rsync_capability(user, hostname)
        if not rsync_result['success']:
            return {
                'success': False,
                'message': f'rsync Unavailable: {rsync_result["message"]}',
                'details': {
                    'step': 'rsync_check',
                    'user': user,
                    'hostname': hostname
                }
            }
        
        # Test path accessibility
        path_result = cls.validate_remote_path(user, hostname, path)
        if not path_result['success']:
            return {
                'success': False,
                'message': f'Path Access Failed: {path_result["message"]}',
                'details': {
                    'step': 'path_validation',
                    'user': user,
                    'hostname': hostname,
                    'path': path
                }
            }
        
        # All tests passed
        return {
            'success': True,
            'message': f'SSH source validated successfully: {user}@{hostname}:{path}',
            'details': {
                'user': user,
                'hostname': hostname,
                'path': path,
                'ssh_status': ssh_result['message'],
                'rsync_status': rsync_result['message'],
                'path_status': path_result['message']
            }
        }
