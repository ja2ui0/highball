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
        # Local source configuration no longer needs individual path
        # Paths are handled in the multi-path parser
        source_config = {
            'source_type': 'local'
        }
        
        return {
            'valid': True,
            'config': source_config
        }