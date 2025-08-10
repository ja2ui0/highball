"""
Job form data parsing
Handles parsing form data into job configuration structures
"""

class JobFormParser:
    """Parses form data into structured job configurations"""
    
    @staticmethod
    def parse_job_form(form_data):
        """Parse complete job form data"""
        # Basic job info
        job_name = form_data.get('job_name', [''])[0].strip()
        if not job_name:
            return {'valid': False, 'error': 'Job name is required'}
        
        # Source parsing
        source_type = form_data.get('source_type', [''])[0]
        if not source_type:
            return {'valid': False, 'error': 'Source type is required'}
        
        if source_type == 'local':
            path = form_data.get('source_local_path', [''])[0].strip()
            if not path:
                return {'valid': False, 'error': 'Local source path is required'}
            source_config = {'source_string': path, 'path': path}
            
        elif source_type == 'ssh':
            hostname = form_data.get('source_ssh_hostname', [''])[0].strip()
            username = form_data.get('source_ssh_username', [''])[0].strip()
            path = form_data.get('source_ssh_path', [''])[0].strip()
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'SSH source requires hostname, username, and path'}
            
            source_string = f"{username}@{hostname}:{path}"
            source_config = {
                'source_string': source_string,
                'hostname': hostname,
                'username': username,
                'path': path
            }
        else:
            return {'valid': False, 'error': f'Unknown source type: {source_type}'}
        
        # Destination parsing
        dest_type = form_data.get('dest_type', [''])[0]
        if not dest_type:
            return {'valid': False, 'error': 'Destination type is required'}
        
        if dest_type == 'local':
            path = form_data.get('dest_local_path', [''])[0].strip()
            if not path:
                return {'valid': False, 'error': 'Local destination path is required'}
            dest_config = {'dest_string': path, 'path': path}
            
        elif dest_type == 'ssh':
            hostname = form_data.get('dest_ssh_hostname', [''])[0].strip()
            username = form_data.get('dest_ssh_username', [''])[0].strip()
            path = form_data.get('dest_ssh_path', [''])[0].strip()
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'SSH destination requires hostname, username, and path'}
            
            dest_string = f"{username}@{hostname}:{path}"
            dest_config = {
                'dest_string': dest_string,
                'hostname': hostname,
                'username': username,
                'path': path
            }
            
        elif dest_type == 'rsyncd':
            hostname = form_data.get('dest_rsyncd_hostname', [''])[0].strip()
            share = form_data.get('dest_rsyncd_share', [''])[0].strip()
            
            if not all([hostname, share]):
                return {'valid': False, 'error': 'rsyncd destination requires hostname and share'}
            
            dest_string = f"rsync://{hostname}/{share}"
            dest_config = {
                'dest_string': dest_string,
                'hostname': hostname,
                'share': share
            }
        else:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
        
        # Parse additional options
        includes = JobFormParser.parse_lines(form_data.get('includes', [''])[0])
        excludes = JobFormParser.parse_lines(form_data.get('excludes', [''])[0])
        schedule = form_data.get('schedule', ['manual'])[0]
        enabled = 'enabled' in form_data
        
        return {
            'valid': True,
            'job_name': job_name,
            'source_type': source_type,
            'source_config': source_config,
            'dest_type': dest_type,
            'dest_config': dest_config,
            'includes': includes,
            'excludes': excludes,
            'schedule': schedule,
            'enabled': enabled
        }
    
    @staticmethod
    def parse_lines(text):
        """Parse textarea input into list of non-empty lines"""
        return [line.strip() for line in text.split('\n') if line.strip()]
