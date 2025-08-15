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
        rsync_options = form_data.get('dest_rsync_options', [''])[0].strip()
        
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
        
        # Add rsync options if provided
        if rsync_options:
            dest_config['rsync_options'] = rsync_options
        
        return {
            'valid': True,
            'config': dest_config
        }
    
    @staticmethod
    def parse_ssh_source(form_data):
        """Parse SSH source configuration from form data"""
        hostname = form_data.get('source_ssh_hostname', [''])[0].strip()
        username = form_data.get('source_ssh_username', [''])[0].strip()
        
        if not all([hostname, username]):
            return {
                'valid': False,
                'error': 'SSH source requires hostname and username'
            }
        
        source_config = {
            'hostname': hostname,
            'username': username
        }
        
        # Add container runtime if detected during SSH validation
        container_runtime = form_data.get('container_runtime', [''])[0].strip()
        if container_runtime:
            source_config['container_runtime'] = container_runtime
        
        return {
            'valid': True,
            'config': source_config
        }