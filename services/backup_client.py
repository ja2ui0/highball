"""
Generic backup client for SSH/local execution patterns.
Shared across Restic, Borg, Kopia, and other backup providers.
"""

import subprocess
import json
from typing import Dict, List, Optional, Any


class BackupClient:
    """Generic client for executing backup commands via SSH or locally"""
    
    @staticmethod
    def execute_via_ssh(hostname: str, username: str, command: str, env_vars: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute a command via SSH with environment variables"""
        try:
            env_exports = []
            if env_vars:
                for key, value in env_vars.items():
                    env_exports.append(f"export {key}='{value}'")
            
            remote_command = '; '.join(env_exports + [command])
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                remote_command
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'success': False
            }
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    @staticmethod
    def execute_locally(command: List[str], env_vars: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute a command locally with environment variables"""
        try:
            env = {}
            if env_vars:
                env.update(env_vars)
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'success': False
            }
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    @staticmethod
    def parse_json_output(stdout: str) -> Dict[str, Any]:
        """Parse JSON output with error handling"""
        try:
            return {
                'success': True,
                'data': json.loads(stdout) if stdout.strip() else None
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON: {str(e)}',
                'raw_output': stdout
            }