"""
Generic binary availability checker for backup tools.
Supports restic, borg, kopia, rclone, and other backup binaries.
"""

from typing import Dict, List, Optional, Any
from services.backup_client import BackupClient


class BinaryCheckerService:
    """Service for checking backup binary availability and versions"""
    
    SUPPORTED_BINARIES = {
        'restic': {
            'version_command': 'restic version',
            'description': 'Restic backup tool'
        },
        'borg': {
            'version_command': 'borg --version',
            'description': 'Borg backup tool'
        },
        'kopia': {
            'version_command': 'kopia --version',
            'description': 'Kopia backup tool'
        },
        'rclone': {
            'version_command': 'rclone version --check=false',
            'description': 'Rclone cloud storage tool'
        }
    }
    
    @staticmethod
    def check_binary_availability(binary_name: str, source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check if a specific binary is available on source system or locally"""
        if binary_name not in BinaryCheckerService.SUPPORTED_BINARIES:
            return {
                'success': False,
                'message': f'Unsupported binary: {binary_name}',
                'supported_binaries': list(BinaryCheckerService.SUPPORTED_BINARIES.keys())
            }
        
        binary_info = BinaryCheckerService.SUPPORTED_BINARIES[binary_name]
        
        # Use SSH if source is configured, otherwise check locally
        if source_config and source_config.get('hostname') and source_config.get('username'):
            return BinaryCheckerService._check_binary_via_ssh(binary_name, binary_info, source_config)
        else:
            return BinaryCheckerService._check_binary_locally(binary_name, binary_info)
    
    @staticmethod
    def _check_binary_via_ssh(binary_name: str, binary_info: Dict[str, str], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check binary availability via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"which {binary_name} && {binary_info['version_command']}"
        
        result = BackupClient.execute_via_ssh(hostname, username, command, timeout=15)
        
        if result['success']:
            version_info = result['stdout'].strip()
            return {
                'success': True,
                'message': f'{binary_info["description"]} found on {hostname}',
                'binary': binary_name,
                'version': version_info,
                'location': f'{username}@{hostname}',
                'installation_method': 'remote'
            }
        else:
            error_msg = result['stderr'].strip() or f'{binary_name} binary not found'
            return {
                'success': False,
                'message': f'{binary_info["description"]} not available on {hostname}: {error_msg}',
                'binary': binary_name,
                'location': f'{username}@{hostname}',
                'installation_guide': BinaryCheckerService._get_installation_guide(binary_name)
            }
    
    @staticmethod
    def _check_binary_locally(binary_name: str, binary_info: Dict[str, str]) -> Dict[str, Any]:
        """Check binary availability locally"""
        command = ['sh', '-c', f'which {binary_name} && {binary_info["version_command"]}']
        
        result = BackupClient.execute_locally(command, timeout=15)
        
        if result['success']:
            version_info = result['stdout'].strip()
            return {
                'success': True,
                'message': f'{binary_info["description"]} found locally',
                'binary': binary_name,
                'version': version_info,
                'location': 'container',
                'installation_method': 'local'
            }
        else:
            error_msg = result['stderr'].strip() or f'{binary_name} binary not found'
            return {
                'success': False,
                'message': f'{binary_info["description"]} not available locally: {error_msg}',
                'binary': binary_name,
                'location': 'container',
                'installation_guide': BinaryCheckerService._get_installation_guide(binary_name)
            }
    
    @staticmethod
    def _get_installation_guide(binary_name: str) -> Dict[str, str]:
        """Get installation instructions for a binary"""
        guides = {
            'restic': {
                'apt': 'apt install restic',
                'yum': 'yum install restic',
                'brew': 'brew install restic',
                'manual': 'Download from https://github.com/restic/restic/releases'
            },
            'borg': {
                'apt': 'apt install borgbackup',
                'yum': 'yum install borgbackup',
                'brew': 'brew install borgbackup',
                'manual': 'pip install borgbackup'
            },
            'kopia': {
                'apt': 'Download .deb from https://github.com/kopia/kopia/releases',
                'yum': 'Download .rpm from https://github.com/kopia/kopia/releases',
                'brew': 'brew install kopia',
                'manual': 'Download from https://github.com/kopia/kopia/releases'
            },
            'rclone': {
                'apt': 'apt install rclone',
                'yum': 'yum install rclone',
                'brew': 'brew install rclone',
                'manual': 'curl https://rclone.org/install.sh | sudo bash'
            }
        }
        
        return guides.get(binary_name, {
            'manual': f'Please install {binary_name} manually'
        })
    
    @staticmethod
    def check_multiple_binaries(binary_names: List[str], source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check availability of multiple binaries"""
        results = {}
        all_available = True
        
        for binary_name in binary_names:
            results[binary_name] = BinaryCheckerService.check_binary_availability(binary_name, source_config)
            if not results[binary_name]['success']:
                all_available = False
        
        return {
            'success': all_available,
            'results': results,
            'summary': f'{sum(1 for r in results.values() if r["success"])}/{len(binary_names)} binaries available'
        }