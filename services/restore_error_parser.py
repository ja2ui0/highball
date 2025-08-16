"""
Restore error parser service for parsing and aggregating Restic error messages
Handles complex JSON error parsing and provides clean user-friendly error messages
"""
import json
from typing import Dict, List


class RestoreErrorParser:
    """Service for parsing and cleaning restore error messages"""
    
    def parse_error_message(self, error_message: str) -> str:
        """Parse error message and extract meaningful information for users"""
        try:
            # Check if message contains JSON lines
            if '{' in error_message and '"message_type"' in error_message:
                return self._parse_json_error_message(error_message)
            else:
                # Return original message if no JSON parsing needed
                return error_message
                
        except Exception:
            # If parsing fails, return original message
            return error_message
    
    def _parse_json_error_message(self, error_message: str) -> str:
        """Parse JSON-formatted error messages from Restic"""
        lines = error_message.split('\n')
        parsed_errors = []
        initial_error = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('{') and '"message_type"' in line:
                parsed_error = self._parse_json_line(line)
                if parsed_error:
                    parsed_errors.append(parsed_error)
            elif line and not line.startswith('{'):
                # Capture non-JSON error messages
                if not initial_error:
                    initial_error = line
        
        # Build clean error message
        if parsed_errors:
            return self._aggregate_parsed_errors(parsed_errors)
        elif initial_error:
            return initial_error
        else:
            return error_message
    
    def _parse_json_line(self, line: str) -> str:
        """Parse a single JSON line and extract error information"""
        try:
            error_json = json.loads(line)
            message_type = error_json.get('message_type', '')
            
            if message_type == 'error':
                return self._extract_error_message(error_json)
            elif message_type == 'exit_error':
                return self._extract_exit_error_message(error_json)
            
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _extract_error_message(self, error_json: Dict) -> str:
        """Extract error message from JSON error object"""
        error_info = error_json.get('error', {})
        error_msg = error_info.get('message', '')
        item = error_json.get('item', '')
        
        if error_msg and item:
            return f"{item}: {error_msg}"
        elif error_msg:
            return error_msg
        
        return None
    
    def _extract_exit_error_message(self, error_json: Dict) -> str:
        """Extract exit error message from JSON"""
        exit_msg = error_json.get('message', '')
        if exit_msg:
            return f"Fatal: {exit_msg}"
        
        return None
    
    def _aggregate_parsed_errors(self, parsed_errors: List[str]) -> str:
        """Aggregate and summarize multiple parsed errors"""
        # Group similar errors
        error_counts = {}
        unique_errors = []
        
        for error in parsed_errors:
            # Extract the base error type
            base_error = self._categorize_error(error)
            
            if base_error in error_counts:
                error_counts[base_error] += 1
            else:
                error_counts[base_error] = 1
                unique_errors.append(base_error)
        
        # Build summary message
        if len(unique_errors) == 1:
            return unique_errors[0]
        else:
            # Show the most common error and count
            main_error = max(error_counts.keys(), key=lambda k: error_counts[k])
            total_errors = sum(error_counts.values())
            return f"{main_error} ({total_errors} errors total)"
    
    def _categorize_error(self, error: str) -> str:
        """Categorize error into user-friendly groups"""
        error_lower = error.lower()
        
        # Permission errors
        if 'permission denied' in error_lower:
            if 'mkdir' in error_lower:
                return 'Cannot create directory due to permissions'
            else:
                return 'Permission denied accessing backup destination'
        
        # File not found errors
        elif 'no such file or directory' in error_lower:
            return 'Backup destination path does not exist'
        
        # Ownership/permission setting errors
        elif any(cmd in error_lower for cmd in ['chmod', 'lchown', 'chown']):
            return 'Cannot set file permissions/ownership'
        
        # Network/connectivity errors
        elif any(net_err in error_lower for net_err in ['connection', 'network', 'timeout', 'unreachable']):
            return 'Network connectivity issue'
        
        # Repository errors
        elif any(repo_err in error_lower for repo_err in ['repository', 'snapshot', 'index']):
            return 'Repository or snapshot issue'
        
        # Disk space errors
        elif any(space_err in error_lower for space_err in ['no space', 'disk full', 'quota']):
            return 'Insufficient disk space'
        
        # Authentication errors
        elif any(auth_err in error_lower for auth_err in ['authentication', 'password', 'unauthorized']):
            return 'Authentication failed'
        
        # Default: return original error
        else:
            return error
    
    def get_error_category(self, error_message: str) -> str:
        """Get the primary category of an error for classification"""
        parsed_message = self.parse_error_message(error_message)
        
        # Map categories to types
        if 'permission' in parsed_message.lower():
            return 'permission'
        elif 'network' in parsed_message.lower() or 'connectivity' in parsed_message.lower():
            return 'network'
        elif 'repository' in parsed_message.lower() or 'snapshot' in parsed_message.lower():
            return 'repository'
        elif 'space' in parsed_message.lower() or 'disk' in parsed_message.lower():
            return 'storage'
        elif 'authentication' in parsed_message.lower() or 'password' in parsed_message.lower():
            return 'auth'
        else:
            return 'general'
    
    def suggest_resolution(self, error_message: str) -> str:
        """Suggest resolution steps based on error category"""
        category = self.get_error_category(error_message)
        
        suggestions = {
            'permission': 'Check file permissions and ensure the restore target is writable',
            'network': 'Verify network connectivity and repository accessibility',
            'repository': 'Check repository integrity and snapshot availability',
            'storage': 'Free up disk space at the restore destination',
            'auth': 'Verify repository password and credentials',
            'general': 'Check logs for detailed error information'
        }
        
        return suggestions.get(category, suggestions['general'])