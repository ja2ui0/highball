"""
Restic form data parsing
Handles parsing Restic-specific form data into job configuration structures
"""


class ResticFormParser:
    """Parses Restic destination form data"""
    
    @staticmethod
    def parse_restic_destination(form_data):
        """Parse Restic destination configuration from form data"""
        repo_type = form_data.get('restic_repo_type', [''])[0].strip()
        repo_location = form_data.get('restic_repo_location', [''])[0].strip()
        password = form_data.get('restic_password', [''])[0].strip()
        
        if not all([repo_type, repo_location, password]):
            return {
                'valid': False, 
                'error': 'Restic requires repository type, location, and password'
            }
        
        dest_config = {
            'dest_string': f"{repo_type}:{repo_location}",
            'repo_type': repo_type,
            'repo_location': repo_location,
            'password': password
        }
        
        # Add repository type specific fields
        if repo_type == 'sftp':
            sftp_result = ResticFormParser._parse_sftp_fields(form_data)
            if not sftp_result['valid']:
                return sftp_result
            dest_config.update(sftp_result['config'])
            
        elif repo_type == 's3':
            s3_result = ResticFormParser._parse_s3_fields(form_data)
            if not s3_result['valid']:
                return s3_result
            dest_config.update(s3_result['config'])
        
        # Add retention policy if provided
        retention_result = ResticFormParser._parse_retention_policy(form_data)
        if retention_result:
            dest_config['retention_policy'] = retention_result
        
        # Auto-init flag
        auto_init = form_data.get('restic_auto_init', [''])[0] == 'on'
        dest_config['auto_init'] = auto_init
        
        # Tags
        tags = ResticFormParser._parse_tags(form_data)
        if tags:
            dest_config['tags'] = tags
        
        # Exclude patterns
        excludes = ResticFormParser._parse_exclude_patterns(form_data)
        if excludes:
            dest_config['exclude_patterns'] = excludes
        
        return {
            'valid': True,
            'config': dest_config
        }
    
    @staticmethod
    def _parse_sftp_fields(form_data):
        """Parse SFTP repository specific fields"""
        repo_hostname = form_data.get('restic_repo_hostname', [''])[0].strip()
        repo_username = form_data.get('restic_repo_username', [''])[0].strip()
        repo_path = form_data.get('restic_repo_path', [''])[0].strip()
        
        if not all([repo_hostname, repo_username, repo_path]):
            return {
                'valid': False,
                'error': 'SFTP repository requires hostname, username, and path'
            }
        
        return {
            'valid': True,
            'config': {
                'repo_hostname': repo_hostname,
                'repo_username': repo_username,
                'repo_path': repo_path
            }
        }
    
    @staticmethod
    def _parse_s3_fields(form_data):
        """Parse S3 repository specific fields"""
        s3_bucket = form_data.get('restic_s3_bucket', [''])[0].strip()
        s3_prefix = form_data.get('restic_s3_prefix', [''])[0].strip()
        aws_access_key = form_data.get('restic_aws_access_key', [''])[0].strip()
        aws_secret_key = form_data.get('restic_aws_secret_key', [''])[0].strip()
        
        if not s3_bucket:
            return {
                'valid': False,
                'error': 'S3 repository requires bucket name'
            }
        
        config = {
            's3_bucket': s3_bucket,
            's3_prefix': s3_prefix
        }
        
        # Add AWS credentials if provided
        if aws_access_key:
            config['aws_access_key'] = aws_access_key
        if aws_secret_key:
            config['aws_secret_key'] = aws_secret_key
        
        return {
            'valid': True,
            'config': config
        }
    
    @staticmethod
    def _parse_retention_policy(form_data):
        """Parse retention policy from form data"""
        keep_daily = form_data.get('restic_keep_daily', [''])[0].strip()
        keep_weekly = form_data.get('restic_keep_weekly', [''])[0].strip()
        keep_monthly = form_data.get('restic_keep_monthly', [''])[0].strip()
        keep_yearly = form_data.get('restic_keep_yearly', [''])[0].strip()
        
        retention_policy = {}
        
        try:
            if keep_daily:
                retention_policy['keep_daily'] = int(keep_daily)
            if keep_weekly:
                retention_policy['keep_weekly'] = int(keep_weekly)
            if keep_monthly:
                retention_policy['keep_monthly'] = int(keep_monthly)
            if keep_yearly:
                retention_policy['keep_yearly'] = int(keep_yearly)
        except ValueError:
            # Return None for invalid numbers - will be caught by validation
            return None
        
        return retention_policy if retention_policy else None
    
    @staticmethod
    def _parse_tags(form_data):
        """Parse backup tags from form data"""
        tags_string = form_data.get('restic_tags', [''])[0].strip()
        if not tags_string:
            return []
        
        # Split by comma and clean up
        tags = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
        return tags
    
    @staticmethod
    def _parse_exclude_patterns(form_data):
        """Parse exclude patterns from form data"""
        excludes_string = form_data.get('restic_excludes', [''])[0].strip()
        if not excludes_string:
            return []
        
        # Split by newlines and clean up
        patterns = [pattern.strip() for pattern in excludes_string.split('\n') if pattern.strip()]
        return patterns