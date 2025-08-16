"""
Source path validator service
Validates source paths with RX/RWX permission checking for backup/restore capabilities
"""

from typing import Dict, List, Any
from services.command_execution_service import CommandExecutionService
import os


class SourcePathValidator:
    """Validates source paths with permission analysis"""
    
    @staticmethod
    def validate_source_paths(source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all source paths with permission checking"""
        source_type = source_config.get('source_type')
        source_paths = source_config.get('source_paths', [])
        
        if not source_paths:
            return {'success': False, 'message': 'No source paths configured'}
        
        # Validate each path
        results = []
        all_valid = True
        has_warnings = False
        
        for i, path_config in enumerate(source_paths):
            path = path_config.get('path', '').strip()
            if not path:
                continue
                
            if source_type == 'ssh':
                result = SourcePathValidator._check_ssh_path(
                    source_config.get('hostname'),
                    source_config.get('username'), 
                    path
                )
            elif source_type == 'local':
                result = SourcePathValidator._check_local_path(path)
            else:
                result = {'valid': False, 'message': f'Unsupported source type: {source_type}'}
            
            result['path'] = path
            result['index'] = i + 1
            results.append(result)
            
            if not result.get('valid'):
                all_valid = False
            if result.get('warning'):
                has_warnings = True
        
        # Build response
        message = f'All {len(results)} path(s) validated' if all_valid else f'{sum(1 for r in results if not r.get("valid"))} path(s) failed validation'
        if has_warnings:
            message += ' (with warnings)'
        
        return {
            'success': all_valid,
            'message': message,
            'source_type': source_type,
            'has_warnings': has_warnings,
            'paths_detail': results,
            'tested_from': f"{source_config.get('username')}@{source_config.get('hostname')}" if source_type == 'ssh' else 'Local container'
        }
    
    @staticmethod
    def _check_ssh_path(hostname: str, username: str, path: str) -> Dict[str, Any]:
        """Check SSH path permissions with RX/RWX analysis"""
        if not hostname or not username:
            return {'valid': False, 'message': 'SSH hostname and username required'}
        
        try:
            executor = CommandExecutionService()
            
            # Test RX permissions (required for backup) + write test in one command
            test_cmd = f'[ -d "{path}" ] && [ -r "{path}" ] && [ -x "{path}" ] && echo "RX_OK" && ([ -w "{path}" ] && echo "W_OK" || echo "W_FAIL") || echo "RX_FAIL"'
            result = executor.execute_via_ssh(hostname, username, test_cmd)
            
            if not result.success:
                return {'valid': False, 'message': f'SSH connection failed: {result.stderr}'}
            
            output = result.stdout.strip()
            
            if 'RX_OK' not in output:
                return {'valid': False, 'message': f'Path not accessible (missing read/execute permissions)'}
            
            has_write = 'W_OK' in output
            response = {
                'valid': True,
                'message': f'Path accessible ({"RXW" if has_write else "RX"} permissions)',
                'can_backup': True,
                'can_restore_to_source': has_write
            }
            
            if not has_write:
                response['warning'] = 'No write permissions - restore-to-source will fail'
            
            return response
            
        except Exception as e:
            return {'valid': False, 'message': f'Permission check failed: {str(e)}'}
    
    @staticmethod
    def _check_local_path(path: str) -> Dict[str, Any]:
        """Check local path permissions with RX/RWX analysis"""
        try:
            if not os.path.exists(path):
                return {'valid': False, 'message': 'Path does not exist'}
            
            if not os.path.isdir(path):
                return {'valid': False, 'message': 'Path is not a directory'}
            
            # Check RX permissions
            if not (os.access(path, os.R_OK) and os.access(path, os.X_OK)):
                return {'valid': False, 'message': 'Missing read/execute permissions'}
            
            has_write = os.access(path, os.W_OK)
            response = {
                'valid': True,
                'message': f'Path accessible ({"RXW" if has_write else "RX"} permissions)',
                'can_backup': True,
                'can_restore_to_source': has_write
            }
            
            if not has_write:
                response['warning'] = 'No write permissions - restore-to-source will fail'
            
            return response
            
        except Exception as e:
            return {'valid': False, 'message': f'Permission check failed: {str(e)}'}