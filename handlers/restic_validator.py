"""
Restic validation logic
Handles validating Restic backup configurations and binary availability
"""
import subprocess
from services.restic_runner import ResticRunner


class ResticValidator:
    """Validates Restic backup configurations and binary availability"""
    
    @staticmethod
    def validate_restic_destination(parsed_job):
        """Validate Restic destination configuration"""
        dest_config = parsed_job.get('dest_config', {})
        source_config = parsed_job.get('source_config', {})
        
        # Check required fields
        repo_type = dest_config.get('repo_type')
        if not repo_type:
            return {
                'success': False,
                'message': 'Repository type is required'
            }
        
        repo_location = dest_config.get('repo_location')
        if not repo_location:
            return {
                'success': False,
                'message': 'Repository location is required'
            }
        
        # Validate repository type specific requirements
        if repo_type == 'sftp':
            required_fields = ['repo_hostname', 'repo_username', 'repo_path']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'SFTP repository requires: {", ".join(missing)}'
                }
        
        elif repo_type == 's3':
            required_fields = ['s3_bucket']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'S3 repository requires: {", ".join(missing)}'
                }
        
        # Check for password
        if not dest_config.get('password'):
            return {
                'success': False,
                'message': 'Repository password is required'
            }
        
        # For SSH sources, validate binary availability
        if parsed_job.get('source_type') == 'ssh':
            binary_check = ResticValidator.check_restic_binary(source_config)
            if not binary_check['success']:
                return binary_check
        
        # Build repository URL using ResticRunner
        runner = ResticRunner()
        repo_url = runner._build_repository_url(dest_config)
        
        return {
            'success': True,
            'message': f'Restic {repo_type} repository configuration valid',
            'repository_url': repo_url
        }
    
    @staticmethod
    def check_restic_binary(source_config):
        """Check if restic binary is available on source system"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        if not hostname or not username:
            return {
                'success': False,
                'message': 'SSH source configuration required for restic binary check'
            }
        
        try:
            # Check for restic binary via SSH
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'which restic && restic version'
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                return {
                    'success': True,
                    'message': f'Restic binary found on {hostname}',
                    'version': version_info,
                    'tested_from': f'{username}@{hostname}'
                }
            else:
                error_msg = result.stderr.strip() or 'Restic binary not found'
                return {
                    'success': False,
                    'message': f'Restic not available on {hostname}: {error_msg}',
                    'tested_from': f'{username}@{hostname}',
                    'suggestion': 'Install restic binary on source system or use package manager'
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': f'Connection timeout checking restic on {hostname}',
                'tested_from': f'{username}@{hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Binary check error: {str(e)}',
                'tested_from': f'{username}@{hostname}'
            }
    
    @staticmethod
    def validate_restic_repository_access(dest_config, source_config=None):
        """Test repository access (for future implementation)"""
        # This would test actual repository connectivity
        # For now, return success as placeholder
        return {
            'success': True,
            'message': 'Repository access validation not yet implemented',
            'note': 'Future: Test repository init/access without modifying it'
        }