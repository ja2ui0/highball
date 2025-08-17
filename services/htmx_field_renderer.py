"""
HTMX Field Renderer Service
Handles rendering of form field HTML fragments for HTMX responses
"""

import logging

logger = logging.getLogger(__name__)

class HTMXFieldRenderer:
    """Renders form field HTML fragments for HTMX responses"""
    
    def render_source_fields(self, source_type, data=None):
        """Render source fields based on type"""
        if source_type == 'local':
            return self._render_source_local()
        elif source_type == 'ssh':
            return self._render_source_ssh(data)
        else:
            return '<div id="source_fields"></div>'
    
    def render_dest_fields(self, dest_type, data=None):
        """Render destination fields based on type"""
        if dest_type == 'local':
            return self._render_dest_local(data)
        elif dest_type == 'ssh':
            return self._render_dest_ssh(data)
        elif dest_type == 'rsyncd':
            return self._render_dest_rsyncd(data)
        elif dest_type == 'restic':
            return self._render_dest_restic(data)
        else:
            return '<div id="dest_fields"></div>'
    
    def _render_source_local(self):
        """Render local source fields"""
        return '''
        <div id="source_fields">
            <p class="help-text">Local filesystem source selected. Configure paths in Source Options below.</p>
        </div>
        '''
    
    def _render_source_ssh(self, data=None):
        """Render SSH source fields with preserved data"""
        hostname = data.get('source_ssh_hostname', '') if data else ''
        username = data.get('source_ssh_username', '') if data else ''
        
        return f'''
        <div id="source_fields">
            <div class="form-group">
                <label for="source_ssh_hostname">Hostname:</label>
                <input type="text" name="source_ssh_hostname" value="{hostname}" placeholder="server">
            </div>
            
            <div class="form-group">
                <label for="source_ssh_username">Username:</label>
                <input type="text" name="source_ssh_username" value="{username}" placeholder="root">
            </div>
            
            <div class="help-text">
                <button type="button" 
                        hx-post="/htmx/validate-source" 
                        hx-target="#source_validation_status"
                        hx-include="[name='source_ssh_hostname'], [name='source_ssh_username']"
                        class="button button-warning">Validate SSH Source</button>
                <span id="source_validation_status"></span>
                <div id="source_validation_details" class="validation-details hidden"></div>
                <br><small>Configure paths in Source Options below.</small>
            </div>
        </div>
        '''
    
    def _render_dest_local(self, data=None):
        """Render local destination fields"""
        path = data.get('dest_local_path', '') if data else ''
        
        return f'''
        <div id="dest_fields">
            <div class="form-group">
                <label for="dest_local_path">Local Destination Path (on source system):</label>
                <input type="text" name="dest_local_path" value="{path}" placeholder="/backups">
                <div class="help-text config-note">
                    <strong>Important:</strong> "Local" means local to the SOURCE system, not this container.<br>
                    If source is SSH remote, destination will be created on that remote system.<br>
                    If source is local to this container, destination must be a mounted volume.
                </div>
            </div>
        </div>
        '''
    
    def _render_dest_ssh(self, data=None):
        """Render SSH destination fields"""
        hostname = data.get('dest_ssh_hostname', '') if data else ''
        username = data.get('dest_ssh_username', '') if data else ''
        path = data.get('dest_ssh_path', '') if data else ''
        rsync_options = data.get('dest_rsync_options', '') if data else ''
        
        return f'''
        <div id="dest_fields">
            <div class="form-group">
                <label for="dest_ssh_hostname">Hostname:</label>
                <input type="text" name="dest_ssh_hostname" value="{hostname}" placeholder="backup-server">
            </div>
            
            <div class="form-group">
                <label for="dest_ssh_username">Username:</label>
                <input type="text" name="dest_ssh_username" value="{username}" placeholder="backup">
            </div>
            
            <div class="form-group">
                <label for="dest_ssh_path">Path:</label>
                <input type="text" name="dest_ssh_path" value="{path}" placeholder="/backups">
            </div>
            
            <div class="form-group">
                <label for="dest_rsync_options">Rsync Options:</label>
                <input type="text" name="dest_rsync_options" value="{rsync_options}" placeholder="-avz --delete">
                <div class="help-text">
                    <strong>Default options:</strong> <code>-avz --delete</code><br>
                    Leave empty to use defaults. Custom options will override defaults completely.
                </div>
            </div>
            
            <div class="help-text">
                <button type="button" 
                        hx-post="/htmx/validate-dest-ssh" 
                        hx-target="#dest_ssh_validation_status"
                        hx-include="[name='dest_ssh_hostname'], [name='dest_ssh_username']"
                        class="button button-warning">Validate SSH Destination</button>
                <span id="dest_ssh_validation_status"></span>
                <div id="dest_ssh_validation_details" class="validation-details hidden"></div>
            </div>
        </div>
        '''
    
    def _render_dest_rsyncd(self, data=None):
        """Render rsyncd destination fields"""
        hostname = data.get('dest_rsyncd_hostname', '') if data else ''
        share = data.get('dest_rsyncd_share', '') if data else ''
        rsync_options = data.get('dest_rsync_options', '') if data else ''
        
        return f'''
        <div id="dest_fields">
            <div class="form-group">
                <label for="dest_rsyncd_hostname">Hostname:</label>
                <input type="text" name="dest_rsyncd_hostname" value="{hostname}" placeholder="backup-server">
            </div>
            
            <div class="form-group">
                <button type="button" 
                        hx-post="/htmx/rsyncd-discovery" 
                        hx-target="#discover_status"
                        hx-include="[name='dest_rsyncd_hostname'], [name='source_ssh_hostname'], [name='source_ssh_username']"
                        class="button button-warning">Discover Shares</button>
                <span id="discover_status"></span>
            </div>
            
            <div id="share_selection" class="{'hidden' if not share else ''}">
                <div class="form-group">
                    <label for="dest_rsyncd_share">Share:</label>
                    <select name="dest_rsyncd_share" id="dest_rsyncd_share">
                        <option value="">Select a share...</option>
                        <option value="{share}" {'selected' if share else ''}>{share}</option>
                    </select>
                </div>
            </div>
            
            <div class="form-group">
                <label for="dest_rsync_options">Rsync Options:</label>
                <input type="text" name="dest_rsync_options" value="{rsync_options}" placeholder="-avz --delete">
                <div class="help-text">
                    <strong>Default options:</strong> <code>-avz --delete</code><br>
                    Leave empty to use defaults. Custom options will override defaults completely.
                </div>
            </div>
        </div>
        '''
    
    def _render_dest_restic(self, data=None):
        """Render Restic destination fields with HTMX integration"""
        password = data.get('restic_password', '') if data else ''
        repo_type = data.get('restic_repo_type', '') if data else ''
        
        return f'''
        <div id="dest_fields">
            <div class="form-group">
                <label for="restic_repo_type">Repository Type:</label>
                <select id="restic_repo_type" name="restic_repo_type" 
                        hx-post="/htmx/restic-repo-fields" 
                        hx-target="#restic_repo_container"
                        hx-include="[name^='restic_']">
                    <option value="">Select repository type...</option>
                    <option value="local" {"selected" if repo_type == "local" else ""}>Local Path</option>
                    <option value="rest" {"selected" if repo_type == "rest" else ""}>REST Server</option>
                    <option value="s3" {"selected" if repo_type == "s3" else ""}>Amazon S3</option>
                    <option value="rclone" {"selected" if repo_type == "rclone" else ""}>rclone Remote</option>
                    <option value="sftp" {"selected" if repo_type == "sftp" else ""}>SFTP</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="restic_password">Repository Password:</label>
                <div class="password-input-container">
                    <input type="password" id="restic_password" name="restic_password" 
                           value="{password}" placeholder="Strong repository password" required>
                    <button type="button" class="password-toggle" onclick="togglePasswordVisibility('restic_password')" 
                            aria-label="Toggle password visibility">
                        <span class="password-toggle-icon" data-target="restic_password">Show</span>
                    </button>
                </div>
                <div class="help-text">This password encrypts your entire backup repository. Store it securely!</div>
            </div>
            
            <div id="restic_repo_container">
                <!-- Repository-specific fields will be loaded here by HTMX -->
            </div>
            
            <div class="help-text">
                <button type="button" 
                        hx-post="/htmx/validate-restic" 
                        hx-target="#restic_validation_status"
                        hx-include="[name^='restic_']"
                        class="button button-warning">Validate Repository Configuration</button>
                <span id="restic_validation_status"></span>
            </div>
        </div>
        '''
    
    def render_cron_field(self, schedule_value, existing_cron_pattern=""):
        """Render cron field based on schedule selection"""
        import html
        if schedule_value == 'cron':
            return f'''
            <div id="cron_field" class="mt-10">
                <label for="cron_pattern">Cron Pattern:</label>
                <input type="text" name="cron_pattern" value="{html.escape(existing_cron_pattern)}" placeholder="0 3 * * *" 
                       title="Format: minute hour day month weekday">
                <div class="help-text">
                    Examples: "0 3 * * *" (daily 3am), "0 */6 * * *" (every 6 hours), "0 3 * * 0" (weekly Sunday 3am), "0 3 1 * *" (monthly 1st 3am)
                </div>
            </div>
            '''
        else:
            return '<div id="cron_field" class="hidden mt-10"></div>'