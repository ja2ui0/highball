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
    def validate_rsyncd_destination(hostname, share, source_config=None):
        """Validate rsyncd destination from source perspective"""
        if not hostname or not share:
            return {
                'success': False,
                'message': 'Hostname and share name are required'
            }
        
        # If we have source config, test from source system
        if source_config and source_config.get('hostname'):
            return JobValidator._validate_rsyncd_from_source(hostname, share, source_config)
        else:
            # Fallback to container-based testing (less reliable)
            return JobValidator._validate_rsyncd_from_container(hostname, share)
    
    @staticmethod
    def discover_rsyncd_shares(hostname, source_config=None):
        """Discover available shares on rsyncd server"""
        if not hostname:
            return {
                'success': False,
                'message': 'Hostname is required'
            }
        
        # If we have source config, test from source system
        if source_config and source_config.get('hostname'):
            return JobValidator._discover_shares_from_source(hostname, source_config)
        else:
            # Fallback to container-based testing
            return JobValidator._discover_shares_from_container(hostname)
    
    @staticmethod
    def _validate_rsyncd_from_source(dest_hostname, share, source_config):
        """Test rsyncd access from the source system via SSH"""
        source_hostname = source_config.get('hostname')
        source_username = source_config.get('username')
        
        if not source_hostname or not source_username:
            return {
                'success': False,
                'message': 'Source SSH configuration required for proper rsyncd testing'
            }
        
        try:
            # Run rsync command from source system to test destination
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{source_username}@{source_hostname}',
                f'rsync --list-only rsync://{dest_hostname}/'
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                # Parse available shares
                available_shares = JobValidator._parse_rsyncd_shares(result.stdout)
                
                if share in available_shares:
                    return {
                        'success': True,
                        'message': f'rsyncd share "{share}" accessible from source {source_hostname}',
                        'available_shares': available_shares,
                        'tested_from': f'{source_username}@{source_hostname}'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Share "{share}" not found on {dest_hostname}',
                        'available_shares': available_shares,
                        'tested_from': f'{source_username}@{source_hostname}'
                    }
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {dest_hostname}:873 (tested from {source_hostname})'
                
                return {
                    'success': False,
                    'message': error_msg,
                    'tested_from': f'{source_username}@{source_hostname}'
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': f'Connection timeout testing {dest_hostname} from {source_hostname}',
                'tested_from': f'{source_username}@{source_hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'tested_from': f'{source_username}@{source_hostname}'
            }
    
    @staticmethod
    def _validate_rsyncd_from_container(hostname, share):
        """Fallback: Test rsyncd from container (original method)"""
        try:
            cmd = ['rsync', '--list-only', f'rsync://{hostname}/']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                available_shares = JobValidator._parse_rsyncd_shares(result.stdout)
                
                if share in available_shares:
                    return {
                        'success': True,
                        'message': f'rsyncd share "{share}" accessible from container',
                        'available_shares': available_shares,
                        'tested_from': 'container'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Share "{share}" not found on {hostname}',
                        'available_shares': available_shares,
                        'tested_from': 'container'
                    }
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {hostname}:873'
                
                return {
                    'success': False,
                    'message': error_msg,
                    'tested_from': 'container'
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': 'Connection timeout - rsync daemon not responding',
                'tested_from': 'container'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'tested_from': 'container'
            }
    
    @staticmethod
    def _discover_shares_from_source(dest_hostname, source_config):
        """Discover rsyncd shares from source system via SSH"""
        source_hostname = source_config.get('hostname')
        source_username = source_config.get('username')
        
        if not source_hostname or not source_username:
            return {
                'success': False,
                'message': 'Source SSH configuration required for proper rsyncd discovery'
            }
        
        try:
            # Run rsync command from source system to list shares
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{source_username}@{source_hostname}',
                f'rsync --list-only rsync://{dest_hostname}/'
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                # Parse available shares
                available_shares = JobValidator._parse_rsyncd_shares(result.stdout)
                
                return {
                    'success': True,
                    'message': f'Found {len(available_shares)} shares on {dest_hostname}',
                    'available_shares': available_shares,
                    'tested_from': f'{source_username}@{source_hostname}'
                }
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {dest_hostname}:873 (tested from {source_hostname})'
                
                return {
                    'success': False,
                    'message': error_msg,
                    'tested_from': f'{source_username}@{source_hostname}',
                    'available_shares': []
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': f'Connection timeout to {dest_hostname} from {source_hostname}',
                'tested_from': f'{source_username}@{source_hostname}',
                'available_shares': []
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Discovery error: {str(e)}',
                'tested_from': f'{source_username}@{source_hostname}',
                'available_shares': []
            }
    
    @staticmethod
    def _discover_shares_from_container(hostname):
        """Fallback: Discover shares from container"""
        try:
            cmd = ['rsync', '--list-only', f'rsync://{hostname}/']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                available_shares = JobValidator._parse_rsyncd_shares(result.stdout)
                
                return {
                    'success': True,
                    'message': f'Found {len(available_shares)} shares on {hostname}',
                    'available_shares': available_shares,
                    'tested_from': 'container'
                }
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                if 'connection refused' in error_msg.lower():
                    error_msg = f'rsync daemon not running on {hostname}:873'
                
                return {
                    'success': False,
                    'message': error_msg,
                    'tested_from': 'container',
                    'available_shares': []
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': 'Connection timeout - rsync daemon not responding',
                'tested_from': 'container',
                'available_shares': []
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Discovery error: {str(e)}',
                'tested_from': 'container',
                'available_shares': []
            }
    
    @staticmethod
    def _parse_rsyncd_shares(rsync_output):
        """Parse rsync daemon output to extract share names"""
        shares = []
        for line in rsync_output.strip().split('\n'):
            if line.strip() and not line.startswith('@'):
                parts = line.split()
                if parts:
                    share_name = parts[0]
                    shares.append(share_name)
        return shares
    
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
