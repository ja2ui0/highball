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
        
        repo_uri = dest_config.get('repo_uri') or dest_config.get('dest_string')
        if not repo_uri:
            return {
                'success': False,
                'message': 'Repository URI is required'
            }
        
        # Validate repository type specific requirements
        if repo_type == 'sftp':
            required_fields = ['sftp_hostname', 'sftp_username', 'sftp_path']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'SFTP repository requires: {", ".join(missing)}'
                }
        
        elif repo_type == 's3':
            required_fields = ['s3_bucket', 'aws_access_key', 'aws_secret_key']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'S3 repository requires: {", ".join(missing)}'
                }
        
        elif repo_type == 'rest':
            required_fields = ['rest_hostname']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'REST repository requires: {", ".join(missing)}'
                }
        
        elif repo_type == 'rclone':
            required_fields = ['rclone_remote']
            missing = [field for field in required_fields if not dest_config.get(field)]
            if missing:
                return {
                    'success': False,
                    'message': f'rclone repository requires: {", ".join(missing)}'
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
            
            # For rclone repositories, also check rclone binary (similar to rsync pattern)
            if repo_type == 'rclone':
                rclone_check = ResticValidator.check_rclone_binary(source_config)
                if not rclone_check['success']:
                    return rclone_check
        
        # Build repository URL using ResticRunner
        runner = ResticRunner()
        repo_url = runner._build_repository_url(dest_config)
        
        # Test actual repository connectivity
        repo_test = ResticValidator.validate_restic_repository_access(dest_config, source_config)
        
        if not repo_test['success']:
            return repo_test
        
        # If repository exists with snapshots, perform simple content comparison
        if repo_test.get('repository_status') == 'existing' and repo_test.get('snapshot_count', 0) > 0:
            from services.restic_content_analyzer import ResticContentAnalyzer
            
            content_analysis = ResticContentAnalyzer.compare_source_to_repository(
                dest_config, source_config, parsed_job.get('source_type')
            )
            
            # Merge content analysis with repository test results
            repo_test.update({
                'content_analysis': content_analysis
            })
        
        return repo_test
    
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
    def check_rclone_binary(source_config):
        """Check if rclone binary is available on source system"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        if not hostname or not username:
            return {
                'success': False,
                'message': 'SSH source configuration required for rclone binary check'
            }
        
        try:
            # Check for rclone binary via SSH
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'which rclone && rclone version'
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                return {
                    'success': True,
                    'message': f'rclone binary found on {hostname}',
                    'version': version_info,
                    'tested_from': f'{username}@{hostname}'
                }
            else:
                error_msg = result.stderr.strip() or 'rclone binary not found'
                return {
                    'success': False,
                    'message': f'rclone not available on {hostname}: {error_msg}',
                    'tested_from': f'{username}@{hostname}',
                    'suggestion': 'Install rclone binary on source system and configure remotes'
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': f'Connection timeout checking rclone on {hostname}',
                'tested_from': f'{username}@{hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'rclone binary check error: {str(e)}',
                'tested_from': f'{username}@{hostname}'
            }
    
    @staticmethod
    def validate_restic_repository_access(dest_config, source_config=None):
        """Test actual repository connectivity and existence"""
        from services.restic_runner import ResticRunner
        
        try:
            # Build repository URL and environment
            runner = ResticRunner()
            repo_url = runner._build_repository_url(dest_config)
            env_vars = runner._build_environment(dest_config)
            
            # Determine execution context
            if source_config and source_config.get('hostname'):
                # SSH execution
                return ResticValidator._test_repository_via_ssh(repo_url, env_vars, source_config)
            else:
                # Local execution (container)
                return ResticValidator._test_repository_locally(repo_url, env_vars)
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Repository access test failed: {str(e)}'
            }
    
    @staticmethod
    def _test_repository_via_ssh(repo_url, env_vars, source_config):
        """Test repository access via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        try:
            # Build environment exports
            env_exports = []
            if env_vars:
                for key, value in env_vars.items():
                    env_exports.append(f"export {key}='{value}'")
            
            # Test repository existence with snapshots command (fast, read-only)
            restic_cmd = f"restic -r '{repo_url}' snapshots --json"
            remote_command = '; '.join(env_exports + [restic_cmd])
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                remote_command
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                # Repository exists and is accessible
                import json
                try:
                    snapshots = json.loads(result.stdout)
                    snapshot_count = len(snapshots) if snapshots else 0
                    
                    if snapshot_count > 0:
                        latest_snap = max(snapshots, key=lambda x: x.get('time', ''))
                        return {
                            'success': True,
                            'message': f'EXISTING REPO FOUND! Repository contains {snapshot_count} snapshots',
                            'repository_status': 'existing',
                            'snapshot_count': snapshot_count,
                            'latest_backup': latest_snap.get('time', 'unknown'),
                            'tested_from': f'{username}@{hostname}'
                        }
                    else:
                        return {
                            'success': True,
                            'message': 'Repository exists but contains no snapshots (empty repository)',
                            'repository_status': 'empty',
                            'snapshot_count': 0,
                            'tested_from': f'{username}@{hostname}'
                        }
                        
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'message': 'Repository accessible but could not parse snapshot data',
                        'repository_status': 'accessible',
                        'tested_from': f'{username}@{hostname}'
                    }
            else:
                # Check if it's a credentials issue or repository doesn't exist
                error_output = result.stderr.strip().lower()
                if 'wrong password' in error_output or 'incorrect password' in error_output or 'no key found' in error_output:
                    return {
                        'success': False,
                        'message': 'Invalid repository password - credentials are incorrect',
                        'error_type': 'authentication',
                        'tested_from': f'{username}@{hostname}'
                    }
                elif 'empty password' in error_output or 'password from stdin' in error_output:
                    return {
                        'success': False,
                        'message': 'Repository password is required but not provided',
                        'error_type': 'authentication',
                        'tested_from': f'{username}@{hostname}'
                    }
                elif 'command not found' in error_output or 'restic: not found' in error_output or (': not found' in error_output and 'restic' in error_output):
                    return {
                        'success': False,
                        'message': f'Restic binary not found on {hostname} - please install restic on the source system',
                        'error_type': 'binary_missing',
                        'tested_from': f'{username}@{hostname}',
                        'suggestion': 'Install restic: sudo apt install restic (or download from https://github.com/restic/restic/releases)'
                    }
                elif 'no such file' in error_output or 'not found' in error_output:
                    return {
                        'success': False,
                        'message': 'Repository not found at specified location',
                        'error_type': 'not_found',
                        'tested_from': f'{username}@{hostname}'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Cannot access repository: {result.stderr.strip()}',
                        'error_type': 'access_error',
                        'tested_from': f'{username}@{hostname}'
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': f'Repository access test timed out on {hostname}',
                'tested_from': f'{username}@{hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Repository access test error: {str(e)}',
                'tested_from': f'{username}@{hostname}'
            }
    
    @staticmethod
    def _test_repository_locally(repo_url, env_vars):
        """Test repository access locally (in container)"""
        try:
            # Prepare environment
            env = {}
            if env_vars:
                env.update(env_vars)
            
            # Test repository with snapshots command
            cmd = ['restic', '-r', repo_url, 'snapshots', '--json']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
            
            if result.returncode == 0:
                import json
                try:
                    snapshots = json.loads(result.stdout)
                    snapshot_count = len(snapshots) if snapshots else 0
                    
                    if snapshot_count > 0:
                        latest_snap = max(snapshots, key=lambda x: x.get('time', ''))
                        return {
                            'success': True,
                            'message': f'EXISTING REPO FOUND! Repository contains {snapshot_count} snapshots',
                            'repository_status': 'existing',
                            'snapshot_count': snapshot_count,
                            'latest_backup': latest_snap.get('time', 'unknown'),
                            'tested_from': 'container'
                        }
                    else:
                        return {
                            'success': True,
                            'message': 'Repository exists but contains no snapshots (empty repository)',
                            'repository_status': 'empty',
                            'snapshot_count': 0,
                            'tested_from': 'container'
                        }
                        
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'message': 'Repository accessible but could not parse snapshot data',
                        'repository_status': 'accessible',
                        'tested_from': 'container'
                    }
            else:
                error_output = result.stderr.strip().lower()
                if 'wrong password' in error_output or 'incorrect password' in error_output or 'no key found' in error_output:
                    return {
                        'success': False,
                        'message': 'Invalid repository password - credentials are incorrect',
                        'error_type': 'authentication'
                    }
                elif 'empty password' in error_output or 'password from stdin' in error_output:
                    return {
                        'success': False,
                        'message': 'Repository password is required but not provided',
                        'error_type': 'authentication'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Cannot access repository: {result.stderr.strip()}',
                        'error_type': 'access_error'
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': 'Repository access test timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Repository access test error: {str(e)}'
            }
    
    @staticmethod
    def list_repository_snapshots(job_config):
        """List all snapshots in a Restic repository"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        try:
            from services.restic_runner import ResticRunner
            runner = ResticRunner()
            repo_url = runner._build_repository_url(dest_config)
            env_vars = runner._build_environment(dest_config)
            
            # Use SSH if source is SSH, otherwise local
            if source_config and source_config.get('hostname'):
                return ResticValidator._list_snapshots_via_ssh(repo_url, env_vars, source_config)
            else:
                return ResticValidator._list_snapshots_locally(repo_url, env_vars)
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Snapshot listing failed: {str(e)}'
            }
    
    @staticmethod
    def _list_snapshots_via_ssh(repo_url, env_vars, source_config):
        """List snapshots via SSH execution"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        try:
            env_exports = []
            if env_vars:
                for key, value in env_vars.items():
                    env_exports.append(f"export {key}='{value}'")
            
            restic_cmd = f"restic -r '{repo_url}' snapshots --json"
            remote_command = '; '.join(env_exports + [restic_cmd])
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                remote_command
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                try:
                    snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    formatted_snapshots = []
                    
                    for snap in snapshots:
                        formatted_snapshots.append({
                            'id': snap.get('short_id', snap.get('id', 'unknown'))[:8],
                            'full_id': snap.get('id', 'unknown'),
                            'time': snap.get('time', 'unknown'),
                            'hostname': snap.get('hostname', 'unknown'),
                            'username': snap.get('username', 'unknown'),
                            'paths': snap.get('paths', []),
                            'tags': snap.get('tags', [])
                        })
                    
                    return {
                        'success': True,
                        'snapshots': formatted_snapshots,
                        'count': len(formatted_snapshots)
                    }
                    
                except json.JSONDecodeError as e:
                    return {
                        'success': False,
                        'error': f'Failed to parse snapshot data: {str(e)}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Failed to list snapshots: {result.stderr.strip()}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Snapshot listing timed out on {hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Snapshot listing error: {str(e)}'
            }
    
    @staticmethod
    def _list_snapshots_locally(repo_url, env_vars):
        """List snapshots locally in container"""
        try:
            env = {}
            if env_vars:
                env.update(env_vars)
            
            cmd = ['restic', '-r', repo_url, 'snapshots', '--json']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            
            if result.returncode == 0:
                import json
                try:
                    snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    formatted_snapshots = []
                    
                    for snap in snapshots:
                        formatted_snapshots.append({
                            'id': snap.get('short_id', snap.get('id', 'unknown'))[:8],
                            'full_id': snap.get('id', 'unknown'),
                            'time': snap.get('time', 'unknown'),
                            'hostname': snap.get('hostname', 'unknown'),
                            'username': snap.get('username', 'unknown'),
                            'paths': snap.get('paths', []),
                            'tags': snap.get('tags', [])
                        })
                    
                    return {
                        'success': True,
                        'snapshots': formatted_snapshots,
                        'count': len(formatted_snapshots)
                    }
                    
                except json.JSONDecodeError as e:
                    return {
                        'success': False,
                        'error': f'Failed to parse snapshot data: {str(e)}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Failed to list snapshots: {result.stderr.strip()}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Snapshot listing timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Snapshot listing error: {str(e)}'
            }
    
    @staticmethod
    def browse_snapshot_directory(job_config, snapshot_id, path):
        """Browse directory contents in a specific snapshot"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        try:
            from services.restic_runner import ResticRunner
            runner = ResticRunner()
            repo_url = runner._build_repository_url(dest_config)
            env_vars = runner._build_environment(dest_config)
            
            # Use SSH if source is SSH, otherwise local
            if source_config and source_config.get('hostname'):
                return ResticValidator._browse_directory_via_ssh(repo_url, env_vars, source_config, snapshot_id, path)
            else:
                return ResticValidator._browse_directory_locally(repo_url, env_vars, snapshot_id, path)
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Directory browsing failed: {str(e)}'
            }
    
    @staticmethod 
    def _browse_directory_via_ssh(repo_url, env_vars, source_config, snapshot_id, path):
        """Browse directory via SSH execution"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        try:
            env_exports = []
            if env_vars:
                for key, value in env_vars.items():
                    env_exports.append(f"export {key}='{value}'")
            
            # Use restic ls command to list directory contents
            escaped_path = path.replace("'", "'\"'\"'")  # Escape single quotes
            restic_cmd = f"restic -r '{repo_url}' ls '{snapshot_id}' --json '{escaped_path}'"
            remote_command = '; '.join(env_exports + [restic_cmd])
            
            ssh_cmd = [
                'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                remote_command
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return ResticValidator._parse_directory_listing(result.stdout, path)
            else:
                return {
                    'success': False,
                    'error': f'Failed to browse directory: {result.stderr.strip()}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Directory browsing timed out on {hostname}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Directory browsing error: {str(e)}'
            }
    
    @staticmethod
    def _browse_directory_locally(repo_url, env_vars, snapshot_id, path):
        """Browse directory locally in container"""
        try:
            env = {}
            if env_vars:
                env.update(env_vars)
            
            cmd = ['restic', '-r', repo_url, 'ls', snapshot_id, '--json', path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            
            if result.returncode == 0:
                return ResticValidator._parse_directory_listing(result.stdout, path)
            else:
                return {
                    'success': False,
                    'error': f'Failed to browse directory: {result.stderr.strip()}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Directory browsing timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Directory browsing error: {str(e)}'
            }
    
    @staticmethod
    def _parse_directory_listing(json_output, current_path):
        """Parse restic ls JSON output into directory structure"""
        try:
            import json
            import os
            
            lines = json_output.strip().split('\n')
            items = []
            
            # Add parent directory entry if not at root
            if current_path and current_path != '/':
                parent_path = os.path.dirname(current_path) if current_path != '/' else '/'
                items.append({
                    'name': '..',
                    'type': 'parent',
                    'path': parent_path,
                    'size': None
                })
            
            # Parse each JSON line 
            for line in lines:
                if not line.strip():
                    continue
                    
                try:
                    item = json.loads(line)
                    name = item.get('name', '')
                    item_type = item.get('type', 'file')
                    size = item.get('size')
                    full_path = item.get('path', os.path.join(current_path, name))
                    
                    # Skip the current directory entry, empty names, and self-references
                    if (name == '.' or name == current_path or name == '' or 
                        full_path == current_path or 
                        (current_path != '/' and name == os.path.basename(current_path))):
                        continue
                    
                    items.append({
                        'name': name,
                        'type': 'directory' if item_type == 'dir' else 'file',
                        'path': full_path,
                        'size': size
                    })
                    
                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
            
            return {
                'success': True,
                'contents': items,
                'current_path': current_path,
                'total_items': len(items)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to parse directory listing: {str(e)}'
            }