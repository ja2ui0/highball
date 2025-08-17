"""
HTMX Restic Renderer Service
Handles rendering of Restic repository configuration forms and URI previews
"""

import logging

logger = logging.getLogger(__name__)

class HTMXResticRenderer:
    """Renders Restic repository forms and URI previews for HTMX"""
    
    def render_restic_repo_fields(self, repo_type, data=None):
        """Render Restic repository fields based on type"""
        if repo_type == 'local':
            return self._render_local_repo(data)
        elif repo_type == 'rest':
            return self._render_rest_repo(data)
        elif repo_type == 's3':
            return self._render_s3_repo(data)
        elif repo_type == 'rclone':
            return self._render_rclone_repo(data)
        elif repo_type == 'sftp':
            return self._render_sftp_repo(data)
        else:
            return '<div id="restic_repo_fields"></div>'
    
    def generate_uri_preview(self, repo_type, form_data):
        """Generate URI preview based on repository type and form data"""
        if repo_type == 'rest':
            return self._generate_rest_uri(form_data)
        elif repo_type == 's3':
            return self._generate_s3_uri(form_data)
        elif repo_type == 'rclone':
            return self._generate_rclone_uri(form_data)
        elif repo_type == 'sftp':
            return self._generate_sftp_uri(form_data)
        elif repo_type == 'local':
            return self._generate_local_uri(form_data)
        else:
            return "Select repository type to see URI preview"
    
    def _render_local_repo(self, data=None):
        """Render local repository fields"""
        path = data.get('restic_local_path', '') if data else ''
        
        return f'''
        <div id="restic_repo_fields">
            <div class="form-group">
                <label for="restic_local_path">Local Repository Path:</label>
                <input type="text" name="restic_local_path" value="{path}" 
                       placeholder="/backups/restic-repo"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
                <div class="help-text">
                    Path to local Restic repository directory. Will be created if it doesn't exist.
                </div>
            </div>
        </div>
        '''
    
    def _render_rest_repo(self, data=None):
        """Render REST repository fields"""
        hostname = data.get('restic_rest_hostname', '') if data else ''
        port = data.get('restic_rest_port', '8000') if data else '8000'
        path = data.get('restic_rest_path', '') if data else ''
        use_https = data.get('restic_rest_use_https', True) if data else True
        
        return f'''
        <div id="restic_repo_fields">
            <div class="form-group">
                <label for="restic_rest_hostname">REST Server Hostname:</label>
                <input type="text" name="restic_rest_hostname" value="{hostname}" 
                       placeholder="backup-server.local"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_rest_port">Port:</label>
                <input type="number" name="restic_rest_port" value="{port}" 
                       placeholder="8000"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_rest_path">Repository Path (optional):</label>
                <input type="text" name="restic_rest_path" value="{path}" 
                       placeholder="/repo"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" name="restic_rest_use_https" 
                           {"checked" if use_https else ""}
                           hx-post="/htmx/restic-uri-preview" 
                           hx-target="#uri_preview_container"
                           hx-include="[name='restic_repo_type'], [name^='restic_']"
                           hx-trigger="change">
                    Use HTTPS
                </label>
            </div>
        </div>
        '''
    
    def _render_s3_repo(self, data=None):
        """Render S3 repository fields"""
        bucket = data.get('restic_s3_bucket', '') if data else ''
        region = data.get('restic_s3_region', 'us-east-1') if data else 'us-east-1'
        path = data.get('restic_s3_path', '') if data else ''
        endpoint = data.get('restic_s3_endpoint', '') if data else ''
        
        return f'''
        <div id="restic_repo_fields">
            <div class="form-group">
                <label for="restic_s3_bucket">S3 Bucket:</label>
                <input type="text" name="restic_s3_bucket" value="{bucket}" 
                       placeholder="my-backup-bucket"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_s3_region">AWS Region:</label>
                <input type="text" name="restic_s3_region" value="{region}" 
                       placeholder="us-east-1"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_s3_path">Repository Path (optional):</label>
                <input type="text" name="restic_s3_path" value="{path}" 
                       placeholder="/backup/repo"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_s3_endpoint">Custom Endpoint (optional):</label>
                <input type="text" name="restic_s3_endpoint" value="{endpoint}" 
                       placeholder="https://s3.example.com"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
                <div class="help-text">
                    For S3-compatible services like MinIO. Leave empty for AWS S3.
                </div>
            </div>
        </div>
        '''
    
    def _render_rclone_repo(self, data=None):
        """Render rclone repository fields"""
        remote = data.get('restic_rclone_remote', '') if data else ''
        path = data.get('restic_rclone_path', '') if data else ''
        
        return f'''
        <div id="restic_repo_fields">
            <div class="form-group">
                <label for="restic_rclone_remote">Rclone Remote:</label>
                <input type="text" name="restic_rclone_remote" value="{remote}" 
                       placeholder="myremote"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_rclone_path">Repository Path:</label>
                <input type="text" name="restic_rclone_path" value="{path}" 
                       placeholder="/backup/repo"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
        </div>
        '''
    
    def _render_sftp_repo(self, data=None):
        """Render SFTP repository fields"""
        hostname = data.get('restic_sftp_hostname', '') if data else ''
        username = data.get('restic_sftp_username', '') if data else ''
        path = data.get('restic_sftp_path', '') if data else ''
        
        return f'''
        <div id="restic_repo_fields">
            <div class="form-group">
                <label for="restic_sftp_hostname">SFTP Hostname:</label>
                <input type="text" name="restic_sftp_hostname" value="{hostname}" 
                       placeholder="backup-server.local"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_sftp_username">Username:</label>
                <input type="text" name="restic_sftp_username" value="{username}" 
                       placeholder="backup"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
            
            <div class="form-group">
                <label for="restic_sftp_path">Repository Path:</label>
                <input type="text" name="restic_sftp_path" value="{path}" 
                       placeholder="/backups/restic-repo"
                       hx-post="/htmx/restic-uri-preview" 
                       hx-target="#uri_preview_container"
                       hx-include="[name='restic_repo_type'], [name^='restic_']"
                       hx-trigger="input delay:300ms">
            </div>
        </div>
        '''
    
    def _generate_local_uri(self, form_data):
        """Generate local repository URI"""
        path = form_data.get('restic_local_path', [''])[0] or '/path/to/repo'
        return path
    
    def _generate_rest_uri(self, form_data):
        """Generate REST repository URI"""
        hostname = form_data.get('restic_rest_hostname', [''])[0] or 'hostname'
        port = form_data.get('restic_rest_port', ['8000'])[0] or '8000'
        path = form_data.get('restic_rest_path', [''])[0] or ''
        use_https = 'restic_rest_use_https' in form_data
        
        scheme = 'https' if use_https else 'http'
        port_str = f':{port}' if port and port not in ['80', '443'] else ''
        path_str = f'/{path.lstrip("/")}' if path else ''
        
        return f'rest:{scheme}://{hostname}{port_str}{path_str}'
    
    def _generate_s3_uri(self, form_data):
        """Generate S3 repository URI"""
        bucket = form_data.get('restic_s3_bucket', [''])[0] or 'bucket'
        region = form_data.get('restic_s3_region', ['us-east-1'])[0] or 'us-east-1'
        path = form_data.get('restic_s3_path', [''])[0] or ''
        endpoint = form_data.get('restic_s3_endpoint', [''])[0]
        
        if endpoint:
            # Custom S3-compatible endpoint
            path_str = f'/{path.lstrip("/")}' if path else ''
            return f's3:{endpoint}/{bucket}{path_str}'
        else:
            # Standard AWS S3
            path_str = f'/{path.lstrip("/")}' if path else ''
            return f's3:s3.{region}.amazonaws.com/{bucket}{path_str}'
    
    def _generate_rclone_uri(self, form_data):
        """Generate rclone repository URI"""
        remote = form_data.get('restic_rclone_remote', [''])[0] or 'remote'
        path = form_data.get('restic_rclone_path', [''])[0] or '/path'
        path_str = f':{path.lstrip(":")}' if path else ''
        return f'rclone:{remote}{path_str}'
    
    def _generate_sftp_uri(self, form_data):
        """Generate SFTP repository URI"""
        hostname = form_data.get('restic_sftp_hostname', [''])[0] or 'hostname'
        username = form_data.get('restic_sftp_username', [''])[0] or 'user'
        path = form_data.get('restic_sftp_path', [''])[0] or '/path'
        path_str = f'/{path.lstrip("/")}' if path else ''
        return f'sftp:{username}@{hostname}{path_str}'