"""
Local form data parsing
Handles parsing local filesystem form data into job configuration structures
"""


class LocalFormParser:
    """Parses local filesystem form data"""
    
    @staticmethod
    def parse_local_destination(form_data):
        """Parse local destination configuration from form data"""
        path = form_data.get('dest_local_path', [''])[0].strip()
        
        if not path:
            return {
                'valid': False,
                'error': 'Local destination path is required'
            }
        
        dest_config = {
            'dest_string': path,
            'path': path
        }
        
        return {
            'valid': True,
            'config': dest_config
        }
    
    @staticmethod
    def parse_local_source(form_data):
        """Parse local source configuration from form data"""
        path = form_data.get('source_local_path', [''])[0].strip()
        
        if not path:
            return {
                'valid': False,
                'error': 'Local source path is required'
            }
        
        source_config = {
            'source_string': path,
            'path': path
        }
        
        return {
            'valid': True,
            'config': source_config
        }