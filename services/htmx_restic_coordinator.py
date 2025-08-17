"""
HTMX Restic Coordinator Service
Coordinates Restic repository operations and URI generation for HTMX endpoints
"""

import logging
from services.htmx_restic_renderer import HTMXResticRenderer
from services.htmx_validation_renderer import HTMXValidationRenderer
from services.restic_validator import ResticValidator

logger = logging.getLogger(__name__)

class HTMXResticCoordinator:
    """Coordinates Restic repository operations for HTMX"""
    
    def __init__(self):
        self.renderer = HTMXResticRenderer()
        self.validation_renderer = HTMXValidationRenderer()
    
    def handle_repo_type_change(self, repo_type, form_data=None):
        """Handle repository type change and return fields + URI preview"""
        logger.info(f"HTMX Restic repo type change: {repo_type}")
        
        # Render the repository-specific fields
        fields_html = self.renderer.render_restic_repo_fields(repo_type, form_data)
        
        # Generate URI preview
        uri_preview = self.renderer.generate_uri_preview(repo_type, form_data or {})
        
        # Combine fields with URI preview container
        return f'''
        {fields_html}
        <div id="uri_preview_container" class="uri-preview-section">
            <div class="form-group">
                <label>Repository URI Preview:</label>
                <div class="uri-preview-display">
                    <code>{uri_preview}</code>
                </div>
                <div class="help-text">
                    This URI will be used by Restic to access your repository.
                </div>
            </div>
        </div>
        '''
    
    def handle_uri_preview_update(self, form_data):
        """Handle URI preview update when form fields change"""
        repo_type = form_data.get('restic_repo_type', [''])[0]
        
        if not repo_type:
            return '<div class="uri-preview-display"><em>Select repository type to see preview</em></div>'
        
        uri_preview = self.renderer.generate_uri_preview(repo_type, form_data)
        
        return f'''
        <div class="uri-preview-display">
            <code>{uri_preview}</code>
        </div>
        <div class="help-text">
            This URI will be used by Restic to access your repository.
        </div>
        '''
    
    def handle_restic_validation(self, form_data):
        """Handle Restic repository validation with full repository status detection"""
        try:
            repo_type = form_data.get('restic_repo_type', [''])[0]
            password = form_data.get('restic_password', [''])[0]
            
            if not repo_type:
                return self.validation_renderer.render_error("Please select a repository type")
            
            if not password:
                return self.validation_renderer.render_error("Repository password is required")
            
            # Basic validation checks
            validation_errors = self._validate_repository_config(repo_type, form_data)
            if validation_errors:
                return self.validation_renderer.render_error(validation_errors[0])
            
            # Build destination config for validation
            dest_config = self._build_dest_config(repo_type, form_data)
            
            # Get source config if available for container runtime detection
            source_config = self._build_source_config(form_data)
            
            # Perform actual repository validation
            result = ResticValidator.validate_restic_repository_access(dest_config, source_config)
            
            if result.get('success'):
                return self._render_validation_success(result)
            else:
                return self._render_validation_error(result)
            
        except Exception as e:
            logger.error(f"Restic validation error: {e}")
            return self.validation_renderer.render_error(f"Validation failed: {str(e)}")
    
    def _validate_repository_config(self, repo_type, form_data):
        """Validate repository configuration and return list of errors"""
        errors = []
        
        if repo_type == 'local':
            path = form_data.get('restic_local_path', [''])[0]
            if not path:
                errors.append("Local repository path is required")
        
        elif repo_type == 'rest':
            hostname = form_data.get('restic_rest_hostname', [''])[0]
            if not hostname:
                errors.append("REST server hostname is required")
        
        elif repo_type == 's3':
            bucket = form_data.get('restic_s3_bucket', [''])[0]
            if not bucket:
                errors.append("S3 bucket name is required")
        
        elif repo_type == 'rclone':
            remote = form_data.get('restic_rclone_remote', [''])[0]
            path = form_data.get('restic_rclone_path', [''])[0]
            if not remote:
                errors.append("Rclone remote name is required")
            if not path:
                errors.append("Rclone repository path is required")
        
        elif repo_type == 'sftp':
            hostname = form_data.get('restic_sftp_hostname', [''])[0]
            username = form_data.get('restic_sftp_username', [''])[0]
            path = form_data.get('restic_sftp_path', [''])[0]
            if not hostname:
                errors.append("SFTP hostname is required")
            if not username:
                errors.append("SFTP username is required")
            if not path:
                errors.append("SFTP repository path is required")
        
        return errors
    
    def _build_dest_config(self, repo_type, form_data):
        """Build destination config from form data"""
        dest_config = {
            'dest_type': 'restic',
            'repo_type': repo_type,
            'password': form_data.get('restic_password', [''])[0]
        }
        
        if repo_type == 'local':
            dest_config['local_path'] = form_data.get('restic_local_path', [''])[0]
        elif repo_type == 'rest':
            dest_config.update({
                'rest_hostname': form_data.get('restic_rest_hostname', [''])[0],
                'rest_port': form_data.get('restic_rest_port', ['8000'])[0],
                'rest_path': form_data.get('restic_rest_path', [''])[0],
                'rest_use_https': 'restic_rest_use_https' in form_data,
                'rest_username': form_data.get('restic_rest_username', [''])[0],
                'rest_password': form_data.get('restic_rest_password', [''])[0]
            })
        elif repo_type == 's3':
            dest_config.update({
                's3_endpoint': form_data.get('restic_s3_endpoint', ['s3.amazonaws.com'])[0],
                's3_bucket': form_data.get('restic_s3_bucket', [''])[0],
                's3_prefix': form_data.get('restic_s3_prefix', [''])[0],
                's3_access_key': form_data.get('restic_s3_access_key', [''])[0],
                's3_secret_key': form_data.get('restic_s3_secret_key', [''])[0]
            })
        elif repo_type == 'rclone':
            dest_config.update({
                'rclone_remote': form_data.get('restic_rclone_remote', [''])[0],
                'rclone_path': form_data.get('restic_rclone_path', [''])[0]
            })
        elif repo_type == 'sftp':
            dest_config.update({
                'sftp_hostname': form_data.get('restic_sftp_hostname', [''])[0],
                'sftp_username': form_data.get('restic_sftp_username', [''])[0],
                'sftp_path': form_data.get('restic_sftp_path', [''])[0]
            })
        
        return dest_config
    
    def _build_source_config(self, form_data):
        """Build source config from form data for container runtime detection"""
        source_type = form_data.get('source_type', [''])[0]
        if source_type == 'ssh':
            return {
                'source_type': 'ssh',
                'hostname': form_data.get('source_ssh_hostname', [''])[0],
                'username': form_data.get('source_ssh_username', [''])[0]
            }
        return {}
    
    def _render_validation_success(self, result):
        """Render successful validation with repository status and init button logic"""
        repository_status = result.get('repository_status', 'unknown')
        snapshot_count = result.get('snapshot_count')
        latest_backup = result.get('latest_backup')
        tested_from = result.get('tested_from', '')
        repo_uri = result.get('details', {}).get('repo_uri', '')
        
        # Build status message
        if repository_status == 'empty':
            status_msg = "Repository location is empty - ready for initialization"
            show_init = True
        elif snapshot_count is not None:
            status_msg = f"Repository validated with {snapshot_count} snapshot(s)"
            show_init = False
        else:
            status_msg = "Repository configuration validated"
            show_init = False
        
        # Build detailed info
        details = []
        if repository_status:
            details.append(f"Repository status: {repository_status}")
        if snapshot_count is not None:
            details.append(f"Snapshots: {snapshot_count}")
        if latest_backup:
            details.append(f"Latest backup: {latest_backup}")
        if tested_from:
            details.append(f"Tested from: {tested_from}")
        if repo_uri:
            details.append(f"Repository URI: {repo_uri}")
        
        details_html = '<br>'.join(details) if details else ''
        
        # Build init button HTML
        init_button_html = ''
        if show_init:
            init_button_html = '''
            <div class="form-group" style="margin-top: 1rem;">
                <button type="button" 
                        class="button button-primary" 
                        onclick="initializeResticRepository()"
                        id="init_restic_button">
                    Initialize Repository
                </button>
                <div class="help-text">
                    This will create a new Restic repository at the specified location.
                </div>
            </div>
            '''
        
        # Combine success message with details and init button
        return f'''
        <div class="validation-success">
            <span class="validation-status">[OK] {status_msg}</span>
            {f'<div class="validation-details">{details_html}</div>' if details_html else ''}
        </div>
        {init_button_html}
        '''
    
    def _render_validation_error(self, result):
        """Render validation error"""
        message = result.get('message', 'Repository validation failed')
        error_details = result.get('details', {})
        
        details_html = ''
        if error_details:
            details_list = []
            for key, value in error_details.items():
                if value:
                    details_list.append(f"{key}: {value}")
            if details_list:
                details_html = f'<div class="validation-details">{", ".join(details_list)}</div>'
        
        return f'''
        <div class="validation-error">
            <span class="validation-status">[ERROR] {message}</span>
            {details_html}
        </div>
        '''
    
    def handle_repository_initialization(self, form_data):
        """Handle Restic repository initialization"""
        try:
            repo_type = form_data.get('restic_repo_type', [''])[0]
            password = form_data.get('restic_password', [''])[0]
            
            if not repo_type or not password:
                return self.validation_renderer.render_error("Repository type and password are required")
            
            # Build job config for initialization
            dest_config = self._build_dest_config(repo_type, form_data)
            source_config = self._build_source_config(form_data)
            
            job_config = {
                'dest_config': dest_config,
                'source_config': source_config
            }
            
            # Initialize repository
            result = ResticValidator.initialize_restic_repository(job_config)
            
            if result.get('success'):
                return f'''
                <div class="validation-success">
                    <span class="validation-status">[OK] Repository initialized successfully</span>
                    <div class="validation-details">
                        Repository is ready for backups<br>
                        {result.get('tested_from', '')}
                    </div>
                </div>
                '''
            else:
                return self.validation_renderer.render_error(f"Initialization failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Repository initialization error: {e}")
            return self.validation_renderer.render_error(f"Initialization failed: {str(e)}")