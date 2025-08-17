"""
Job form data parsing
Handles parsing form data into job configuration structures
"""

class JobFormParser:
    """Parses form data into structured job configurations"""
    
    @staticmethod
    def parse_source_configuration(form_data):
        """Parse complete source configuration including paths from form data"""
        source_type = form_data.get('source_type', [''])[0]
        if not source_type:
            return {'valid': False, 'error': 'Source type is required'}
        
        # Parse basic source config (connection details)
        if source_type == 'local':
            from handlers.local_form_parser import LocalFormParser
            source_result = LocalFormParser.parse_local_source(form_data)
            if not source_result['valid']:
                return source_result
            source_config = source_result['config']
            
        elif source_type == 'ssh':
            from handlers.ssh_form_parser import SSHFormParser
            source_result = SSHFormParser.parse_ssh_source(form_data)
            if not source_result['valid']:
                return source_result
            source_config = source_result['config']
            
        else:
            return {'valid': False, 'error': f'Unknown source type: {source_type}'}
        
        # Parse source paths (common to all source types)
        source_paths_data = JobFormParser.parse_multi_path_options(form_data)
        if not source_paths_data['valid']:
            return source_paths_data
        
        # Combine config with paths
        source_config['source_type'] = source_type
        source_config['source_paths'] = source_paths_data['source_paths']
        
        return {'valid': True, 'config': source_config}
    
    @staticmethod
    def parse_job_form(form_data):
        """Parse complete job form data"""
        # Basic job info
        job_name = form_data.get('job_name', [''])[0].strip()
        if not job_name:
            return {'valid': False, 'error': 'Job name is required'}
        
        # Source parsing (use dedicated method)
        source_result = JobFormParser.parse_source_configuration(form_data)
        if not source_result['valid']:
            return source_result
        source_config = source_result['config']
        
        # Destination parsing (delegated to modular parsers)
        dest_type = form_data.get('dest_type', [''])[0]
        if not dest_type:
            return {'valid': False, 'error': 'Destination type is required'}
        
        if dest_type == 'local':
            from handlers.local_form_parser import LocalFormParser
            dest_result = LocalFormParser.parse_local_destination(form_data)
            if not dest_result['valid']:
                return dest_result
            dest_config = dest_result['config']
            
        elif dest_type == 'ssh':
            from handlers.ssh_form_parser import SSHFormParser
            dest_result = SSHFormParser.parse_ssh_destination(form_data)
            if not dest_result['valid']:
                return dest_result
            dest_config = dest_result['config']
            
        elif dest_type == 'rsyncd':
            from handlers.rsyncd_form_parser import RsyncdFormParser
            rsyncd_result = RsyncdFormParser.parse_rsyncd_destination(form_data)
            if not rsyncd_result['valid']:
                return rsyncd_result
            dest_config = rsyncd_result['config']
            
        elif dest_type == 'restic':
            from handlers.restic_form_parser import ResticFormParser
            restic_result = ResticFormParser.parse_restic_destination(form_data)
            if not restic_result['valid']:
                return restic_result
            dest_config = restic_result['config']
            
        else:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
        
        # Source paths already parsed in parse_source_configuration - no need to parse again
        
        # Handle schedule - if 'cron' is selected, use the cron_pattern field
        schedule = form_data.get('schedule', ['manual'])[0]
        if schedule == 'cron':
            cron_pattern = form_data.get('cron_pattern', [''])[0].strip()
            if cron_pattern:
                schedule = cron_pattern
            else:
                return {'valid': False, 'error': 'Cron pattern is required when Custom Cron Pattern is selected'}
        
        enabled = 'enabled' in form_data
        respect_conflicts = 'respect_conflicts' in form_data
        
        # Parse notification configuration
        from handlers.notification_form_parser import NotificationFormParser
        notification_result = NotificationFormParser.parse_notification_config(form_data)
        if not notification_result['valid']:
            return notification_result
        notifications = notification_result['notifications']
        
        # Parse maintenance configuration (only for Restic destinations)
        maintenance_config = None
        if dest_type == 'restic':
            from handlers.maintenance_form_parser import MaintenanceFormParser
            maintenance_result = MaintenanceFormParser.parse_maintenance_config(form_data)
            if not maintenance_result['valid']:
                return maintenance_result
            maintenance_config = maintenance_result.get('maintenance_config')
        
        job_data = {
            'valid': True,
            'job_name': job_name,
            'source_type': source_config['source_type'],
            'source_config': source_config,
            'dest_type': dest_type,
            'dest_config': dest_config,
            'schedule': schedule,
            'enabled': enabled,
            'respect_conflicts': respect_conflicts,
            'notifications': notifications
        }
        
        # Add maintenance config if present
        if maintenance_config:
            job_data['maintenance_config'] = maintenance_config
            
        return job_data
    
    @staticmethod
    def parse_multi_path_options(form_data):
        """Parse multi-path source options from form data"""
        # Get arrays of paths, includes, and excludes
        # Handle different form data formats
        def safe_get_list(data, key):
            """Safely get list from form data regardless of format"""
            if hasattr(data, 'getlist'):
                return data.getlist(key)
            else:
                # For regular dict, values are already lists from parse_qs
                value = data.get(key, [])
                return value if isinstance(value, list) else [value]
        
        source_paths = safe_get_list(form_data, 'source_paths[]')
        source_includes = safe_get_list(form_data, 'source_includes[]') 
        source_excludes = safe_get_list(form_data, 'source_excludes[]')
        
        
        if not source_paths:
            return {'valid': False, 'error': 'At least one source path is required'}
        
        # Build source paths array with per-path includes/excludes
        parsed_paths = []
        for i, path in enumerate(source_paths):
            path = path.strip()
            if not path:
                continue  # Skip empty paths instead of failing
            
            # Get includes/excludes for this path (or empty if not provided)
            includes_text = source_includes[i] if i < len(source_includes) else ''
            excludes_text = source_excludes[i] if i < len(source_excludes) else ''
            
            path_config = {
                'path': path,
                'includes': JobFormParser.parse_lines(includes_text),
                'excludes': JobFormParser.parse_lines(excludes_text)
            }
            parsed_paths.append(path_config)
        
        # Ensure we have at least one valid path after filtering empty ones
        if not parsed_paths:
            return {'valid': False, 'error': 'At least one source path is required'}
        
        return {
            'valid': True,
            'source_paths': parsed_paths
        }
    
    @staticmethod
    def parse_lines(text):
        """Parse textarea input into list of non-empty lines"""
        return [line.strip() for line in text.split('\n') if line.strip()]
