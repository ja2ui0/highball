"""
Rsyncd form data parsing
Handles parsing rsyncd daemon form data into job configuration structures
"""


class RsyncdFormParser:
    """Parses rsyncd daemon form data"""
    
    @staticmethod
    def parse_rsyncd_destination(form_data):
        """Parse rsyncd destination configuration from form data"""
        hostname = form_data.get('dest_rsyncd_hostname', [''])[0].strip()
        share = form_data.get('dest_rsyncd_share', [''])[0].strip()
        rsync_options = form_data.get('dest_rsync_options', [''])[0].strip()
        
        if not all([hostname, share]):
            return {
                'valid': False,
                'error': 'rsyncd destination requires hostname and share'
            }
        
        dest_string = f"rsync://{hostname}/{share}"
        dest_config = {
            'dest_string': dest_string,
            'hostname': hostname,
            'share': share
        }
        
        # Add rsync options if provided
        if rsync_options:
            dest_config['rsync_options'] = rsync_options
        
        return {
            'valid': True,
            'config': dest_config
        }