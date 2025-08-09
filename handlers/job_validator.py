"""
Job validation logic
Handles validating backup job configurations and connections
"""
import subprocess
import re
from datetime import datetime
from services.ssh_validator import SSHValidator

class JobValidator:
    """Validates backup job configurations and connections"""
    
    @staticmethod
    def validate_job_config(parsed_job):
        """Validate complete job configuration"""
        errors = []
        
        # Validate source
        if parsed_job['source_type'] == 'ssh':
            source_validation = SSHValidator.validate_ssh_source(
                parsed_job['source_config']['source_string']
            )
            if not source_validation['success']:
                errors.append(f"Source SSH validation failed: {source_validation['message']}")
        
        # Validate destination
        if parsed_job['dest_type'] == 'ssh':
            dest_validation = SSHValidator.validate_ssh_source(
                parsed_job['dest_config']['dest_string']
            )
            if not dest_validation['success']:
                errors.append(f"Destination SSH validation failed: {dest_validation['message']}")
        
        elif parsed_job['dest_type'] == 'rsyncd':
            hostname = parsed_job['dest_config']['hostname']
            share = parsed_job['dest_config']['share']
            rsyncd_validation = JobValidator.validate_rsyncd_destination(hostname, share)
            if not rsyncd_validation['success']:
                errors.append(f"rsyncd validation failed: {rsyncd_validation['message']}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    def validate_ssh_source(source):
        """Validate SSH source string"""
        if not JobValidator.is_ssh_source(source):
            return {
                'success': False,
                'message': 'Not an SSH source format'
            }
        
        return SSHValidator.validate_ssh_source(source)
    
    @staticmethod
    def validate_rsyncd_destination(hostname, share):
        """Validate rsyncd destination"""
        if not hostname or not share:
            return {
                'success': False,
                'message': 'Hostname and share name are required'
            }
        
        try:
            # Test if rsync daemon is accessible and share exists
            cmd = ['rsync', '--list-only', f'rsync://{hostname}/{share}/']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'rsync daemon on {hostname} is accessible and share "{share}" exists'
                }
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'unknown module' in error_msg.lower():
                    error_msg = f'Share "{share}" not found on {hostname}'
                elif 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {hostname}:873'
                
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': 'Connection timeout - rsync daemon not responding'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}'
            }
    
    @staticmethod
    def is_ssh_source(source):
        """Check if source is SSH format (user@host:/path)"""
        return bool(re.match(r'^[^@]+@[^:]+:.+', source))
    
    @staticmethod
    def add_validation_timestamps(job_config, source_type, dest_type):
        """Add validation timestamps to job config"""
        if source_type == 'ssh':
            job_config['source_ssh_validated_at'] = datetime.now().isoformat()
        if dest_type == 'ssh':
            job_config['dest_ssh_validated_at'] = datetime.now().isoformat()
        
        return job_config
