"""
SSH form data parsing
Handles parsing SSH-specific form data into job configuration structures
"""


class SSHFormParser:
    """Parses SSH destination form data"""
    
    @staticmethod
    def parse_ssh_destination(form_data):
        """Parse SSH destination configuration from form data"""
        hostname = form_data.get('dest_ssh_hostname', [''])[0].strip()
        username = form_data.get('dest_ssh_username', [''])[0].strip()
        path = form_data.get('dest_ssh_path', [''])[0].strip()
        
        if not all([hostname, username, path]):
            return {
                'valid': False,
                'error': 'SSH destination requires hostname, username, and path'
            }
        
        dest_string = f"{username}@{hostname}:{path}"
        dest_config = {
            'dest_string': dest_string,
            'hostname': hostname,
            'username': username,
            'path': path
        }
        
        return {
            'valid': True,
            'config': dest_config
        }
    
    @staticmethod
    def parse_ssh_source(form_data):
        """Parse SSH source configuration from form data"""
        hostname = form_data.get('source_ssh_hostname', [''])[0].strip()
        username = form_data.get('source_ssh_username', [''])[0].strip()
        path = form_data.get('source_ssh_path', [''])[0].strip()
        
        if not all([hostname, username, path]):
            return {
                'valid': False,
                'error': 'SSH source requires hostname, username, and path'
            }
        
        source_string = f"{username}@{hostname}:{path}"
        source_config = {
            'source_string': source_string,
            'hostname': hostname,
            'username': username,
            'path': path
        }
        
        return {
            'valid': True,
            'config': source_config
        }