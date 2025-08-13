"""
Restic form data parsing
Handles parsing Restic-specific form data into job configuration structures
"""


class ResticFormParser:
    """Parses Restic destination form data"""
    
    @staticmethod
    def parse_restic_destination(form_data):
        """Parse Restic destination configuration from structured form data"""
        repo_type = form_data.get('restic_repo_type', [''])[0].strip()
        password = form_data.get('restic_password', [''])[0].strip()
        
        if not all([repo_type, password]):
            return {
                'valid': False, 
                'error': 'Restic requires repository type and password'
            }
        
        # Build URI and config based on repository type
        if repo_type == 'local':
            # Local repository - just a path
            path = form_data.get('restic_local_path', [''])[0].strip()
            if not path:
                return {'valid': False, 'error': 'Local repository requires path'}
            
            repo_uri = path
            dest_config = {
                'dest_string': repo_uri,
                'repo_type': repo_type,
                'repo_uri': repo_uri,
                'password': password
            }
            
        elif repo_type == 'rest':
            uri_result = ResticFormParser._build_rest_uri(form_data)
            if not uri_result['valid']:
                return uri_result
                
            dest_config = uri_result['config']
            dest_config.update({
                'repo_type': repo_type,
                'password': password
            })
            
        elif repo_type == 's3':
            uri_result = ResticFormParser._build_s3_uri(form_data)
            if not uri_result['valid']:
                return uri_result
                
            dest_config = uri_result['config']
            dest_config.update({
                'repo_type': repo_type,
                'password': password
            })
            
        elif repo_type == 'rclone':
            uri_result = ResticFormParser._build_rclone_uri(form_data)
            if not uri_result['valid']:
                return uri_result
                
            dest_config = uri_result['config']
            dest_config.update({
                'repo_type': repo_type,
                'password': password
            })
            
        elif repo_type == 'sftp':
            uri_result = ResticFormParser._build_sftp_uri(form_data)
            if not uri_result['valid']:
                return uri_result
                
            dest_config = uri_result['config']
            dest_config.update({
                'repo_type': repo_type,
                'password': password
            })
            
        else:
            return {
                'valid': False,
                'error': f'Unknown repository type: {repo_type}'
            }
        
        return {
            'valid': True,
            'config': dest_config
        }
    
    @staticmethod
    def _build_rest_uri(form_data):
        """Build REST repository URI from structured form data"""
        hostname = form_data.get('restic_rest_hostname', [''])[0].strip()
        port = form_data.get('restic_rest_port', ['8000'])[0].strip()
        path = form_data.get('restic_rest_path', [''])[0].strip()
        # Handle checkbox: present in form_data means checked, absent means unchecked
        use_https = 'restic_rest_use_https' in form_data and form_data.get('restic_rest_use_https', [''])[0] not in ['', 'false', '0']
        username = form_data.get('restic_rest_username', [''])[0].strip()
        password = form_data.get('restic_rest_password', [''])[0].strip()
        
        if not hostname:
            return {'valid': False, 'error': 'REST repository requires hostname'}
        
        # Build URI components
        scheme = 'https' if use_https else 'http'
        port_str = f":{port}" if port and port != '80' and port != '443' else ''
        path_str = f"/{path}" if path and not path.startswith('/') else path or ''
        
        # Build base URI
        if username and password:
            repo_uri = f"rest:{scheme}://{username}:{password}@{hostname}{port_str}{path_str}"
        else:
            repo_uri = f"rest:{scheme}://{hostname}{port_str}{path_str}"
        
        config = {
            'dest_string': repo_uri,
            'repo_uri': repo_uri,
            'rest_hostname': hostname,
            'rest_port': port,
            'rest_path': path,
            'rest_use_https': use_https
        }
        
        # Store credentials separately for future secrets handling
        if username:
            config['rest_username'] = username
        if password:
            config['rest_password'] = password
            
        return {'valid': True, 'config': config}
    
    @staticmethod 
    def _build_s3_uri(form_data):
        """Build S3 repository URI from structured form data"""
        endpoint = form_data.get('restic_s3_endpoint', ['s3.amazonaws.com'])[0].strip()
        bucket = form_data.get('restic_s3_bucket', [''])[0].strip()
        prefix = form_data.get('restic_s3_prefix', [''])[0].strip()
        aws_access_key = form_data.get('restic_aws_access_key', [''])[0].strip()
        aws_secret_key = form_data.get('restic_aws_secret_key', [''])[0].strip()
        
        if not bucket:
            return {'valid': False, 'error': 'S3 repository requires bucket name'}
        
        if not all([aws_access_key, aws_secret_key]):
            return {'valid': False, 'error': 'S3 repository requires AWS Access Key ID and Secret Access Key'}
        
        # Build S3 URI
        if prefix:
            repo_uri = f"s3:{endpoint}/{bucket}/{prefix}"
        else:
            repo_uri = f"s3:{endpoint}/{bucket}"
            
        config = {
            'dest_string': repo_uri,
            'repo_uri': repo_uri,
            's3_endpoint': endpoint,
            's3_bucket': bucket,
            's3_prefix': prefix,
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key
        }
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def _build_rclone_uri(form_data):
        """Build rclone repository URI from structured form data"""
        remote = form_data.get('restic_rclone_remote', [''])[0].strip()
        path = form_data.get('restic_rclone_path', [''])[0].strip()
        
        if not remote:
            return {'valid': False, 'error': 'rclone repository requires remote name'}
        
        # Build rclone URI
        if path:
            repo_uri = f"rclone:{remote}:{path}"
        else:
            repo_uri = f"rclone:{remote}:"
            
        config = {
            'dest_string': repo_uri,
            'repo_uri': repo_uri,
            'rclone_remote': remote,
            'rclone_path': path
        }
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def _build_sftp_uri(form_data):
        """Build SFTP repository URI from structured form data"""
        hostname = form_data.get('restic_sftp_hostname', [''])[0].strip()
        username = form_data.get('restic_sftp_username', [''])[0].strip() 
        path = form_data.get('restic_sftp_path', [''])[0].strip()
        
        if not all([hostname, username, path]):
            return {'valid': False, 'error': 'SFTP repository requires hostname, username, and path'}
        
        # Build SFTP URI
        repo_uri = f"sftp:{username}@{hostname}:{path}"
        
        config = {
            'dest_string': repo_uri,
            'repo_uri': repo_uri,
            'sftp_hostname': hostname,
            'sftp_username': username,
            'sftp_path': path
        }
        
        return {'valid': True, 'config': config}
