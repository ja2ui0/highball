"""
Restic content analysis service
Handles source and repository content comparison for validation
"""
import subprocess
import json
import os
import random
from typing import Dict, List, Set


class ResticContentAnalyzer:
    """Analyzes content similarity between source and restic repository"""
    
    @staticmethod
    def compare_source_to_repository(dest_config, source_config, source_type, timeout=5):
        """
        Compare source content to repository content using simple file/directory name matching.
        Returns match assessment with warning levels.
        """
        try:
            # Get sample files from repository's latest snapshot
            repo_files = ResticContentAnalyzer._get_repository_sample_files(
                dest_config, source_config, source_type, timeout
            )
            
            if not repo_files:
                return {
                    'match_status': 'unable_to_analyze',
                    'message': 'Could not retrieve repository file list for comparison',
                    'warning_level': 'info'
                }
            
            # Get sample files from source
            source_files = ResticContentAnalyzer._get_source_sample_files(
                source_config, source_type, timeout
            )
            
            if not source_files:
                return {
                    'match_status': 'unable_to_analyze',
                    'message': 'Could not retrieve source file list for comparison',
                    'warning_level': 'info'
                }
            
            # Compare file/directory names
            matches = ResticContentAnalyzer._compare_file_lists(repo_files, source_files)
            
            return ResticContentAnalyzer._assess_match_quality(matches, len(repo_files))
            
        except Exception as e:
            return {
                'match_status': 'analysis_error',
                'message': f'Content analysis failed: {str(e)}',
                'warning_level': 'info'
            }
    
    @staticmethod
    def _get_repository_sample_files(dest_config, source_config, source_type, timeout):
        """Get sample file/directory names from latest repository snapshot"""
        from services.restic_runner import ResticRunner
        
        try:
            # Build repository URL and environment
            runner = ResticRunner()
            repo_url = runner._build_repository_url(dest_config)
            env_vars = runner._build_environment(dest_config)
            
            # Get latest snapshot ID first
            snapshot_id = ResticContentAnalyzer._get_latest_snapshot_id(
                repo_url, env_vars, source_config, source_type, timeout
            )
            
            if not snapshot_id:
                return []
            
            # List files from latest snapshot
            if source_type == 'ssh' and source_config.get('hostname'):
                return ResticContentAnalyzer._get_repo_files_via_ssh(
                    repo_url, env_vars, source_config, snapshot_id, timeout
                )
            else:
                return ResticContentAnalyzer._get_repo_files_locally(
                    repo_url, env_vars, snapshot_id, timeout
                )
                
        except Exception:
            return []
    
    @staticmethod
    def _get_latest_snapshot_id(repo_url, env_vars, source_config, source_type, timeout):
        """Get the ID of the most recent snapshot"""
        try:
            if source_type == 'ssh' and source_config.get('hostname'):
                # SSH execution
                env_exports = []
                if env_vars:
                    for key, value in env_vars.items():
                        env_exports.append(f"export {key}='{value}'")
                
                restic_cmd = f"restic -r '{repo_url}' snapshots --json --latest 1"
                remote_command = '; '.join(env_exports + [restic_cmd])
                
                ssh_cmd = [
                    'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                    '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                    f"{source_config['username']}@{source_config['hostname']}",
                    remote_command
                ]
                
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            else:
                # Local execution
                env = env_vars if env_vars else {}
                cmd = ['restic', '-r', repo_url, 'snapshots', '--json', '--latest', '1']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
            
            if result.returncode == 0:
                snapshots = json.loads(result.stdout)
                if snapshots and len(snapshots) > 0:
                    return snapshots[0].get('id', '')
                    
        except Exception:
            pass
            
        return None
    
    @staticmethod
    def _get_repo_files_via_ssh(repo_url, env_vars, source_config, snapshot_id, timeout):
        """Get file list from repository via SSH"""
        try:
            env_exports = []
            if env_vars:
                for key, value in env_vars.items():
                    env_exports.append(f"export {key}='{value}'")
            
            # List files from snapshot, limit to reasonable number
            restic_cmd = f"restic -r '{repo_url}' ls {snapshot_id} | head -20"
            remote_command = '; '.join(env_exports + [restic_cmd])
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f"{source_config['username']}@{source_config['hostname']}",
                remote_command
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                # Extract just the base names, sample randomly
                basenames = [os.path.basename(f.strip()) for f in files if f.strip()]
                return random.sample(basenames, min(10, len(basenames))) if basenames else []
                
        except Exception:
            pass
            
        return []
    
    @staticmethod
    def _get_repo_files_locally(repo_url, env_vars, snapshot_id, timeout):
        """Get file list from repository locally"""
        try:
            env = env_vars if env_vars else {}
            cmd = ['restic', '-r', repo_url, 'ls', snapshot_id]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
            
            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                # Extract just the base names, sample randomly  
                basenames = [os.path.basename(f.strip()) for f in files if f.strip()]
                return random.sample(basenames, min(10, len(basenames))) if basenames else []
                
        except Exception:
            pass
            
        return []
    
    @staticmethod
    def _get_source_sample_files(source_config, source_type, timeout):
        """Get sample file/directory names from source"""
        try:
            source_path = source_config.get('path', '/home')
            
            if source_type == 'ssh':
                return ResticContentAnalyzer._get_source_files_via_ssh(
                    source_config, source_path, timeout
                )
            elif source_type == 'local':
                return ResticContentAnalyzer._get_source_files_locally(source_path, timeout)
            else:
                return []
                
        except Exception:
            return []
    
    @staticmethod
    def _get_source_files_via_ssh(source_config, source_path, timeout):
        """Get source file list via SSH"""
        try:
            # List files and directories, limit output
            list_cmd = f"find '{source_path}' -maxdepth 2 -type f -o -type d | head -20"
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f"{source_config['username']}@{source_config['hostname']}",
                list_cmd
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                # Extract base names, sample randomly
                basenames = [os.path.basename(f.strip()) for f in files if f.strip()]
                return random.sample(basenames, min(10, len(basenames))) if basenames else []
                
        except Exception:
            pass
            
        return []
    
    @staticmethod
    def _get_source_files_locally(source_path, timeout):
        """Get source file list locally"""
        try:
            cmd = ['find', source_path, '-maxdepth', '2', '-type', 'f', '-o', '-type', 'd']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                files = result.stdout.strip().split('\n')
                # Extract base names, sample randomly
                basenames = [os.path.basename(f.strip()) for f in files if f.strip()]
                return random.sample(basenames, min(10, len(basenames))) if basenames else []
                
        except Exception:
            pass
            
        return []
    
    @staticmethod
    def _compare_file_lists(repo_files: List[str], source_files: List[str]) -> int:
        """Compare file lists and return number of matches"""
        repo_set = set(f.lower() for f in repo_files if f)
        source_set = set(f.lower() for f in source_files if f)
        
        matches = len(repo_set.intersection(source_set))
        return matches
    
    @staticmethod
    def _assess_match_quality(matches: int, sample_size: int) -> Dict:
        """Assess match quality and generate appropriate warnings"""
        if sample_size == 0:
            return {
                'match_status': 'unable_to_analyze',
                'message': 'No files available for comparison',
                'warning_level': 'info'
            }
        
        match_ratio = matches / sample_size
        
        if matches == 0:
            return {
                'match_status': 'no_match',
                'message': f'No matching file/directory names found (0/{sample_size}). This source may be completely different from the repository contents.',
                'warning_level': 'error',
                'matches': matches,
                'sample_size': sample_size
            }
        elif matches <= 2:
            return {
                'match_status': 'poor_match',
                'message': f'Few matching file/directory names found ({matches}/{sample_size}). Consider verifying this is the correct repository for this source.',
                'warning_level': 'warning',
                'matches': matches,
                'sample_size': sample_size
            }
        elif matches <= 4:
            return {
                'match_status': 'partial_match',
                'message': f'Some matching file/directory names found ({matches}/{sample_size}). Repository may contain related but different content.',
                'warning_level': 'caution',
                'matches': matches,
                'sample_size': sample_size
            }
        else:
            return {
                'match_status': 'good_match',
                'message': f'Many matching file/directory names found ({matches}/{sample_size}). Source and repository appear to contain related content.',
                'warning_level': 'success',
                'matches': matches,
                'sample_size': sample_size
            }