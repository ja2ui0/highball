"""
HTMX Maintenance Management Service
Handles maintenance form operations and state management for HTMX endpoints
"""
import logging
import html

logger = logging.getLogger(__name__)


class HTMXMaintenanceManager:
    """Manages maintenance form operations for HTMX endpoints"""
    
    def __init__(self):
        pass
    
    def render_maintenance_display(self, mode, existing_data=None):
        """
        Render maintenance display section based on mode (auto/user/off)
        Also updates the hidden field value and returns complete display
        """
        data = existing_data or {}
        
        # Extract maintenance configuration
        retention_policy = data.get('retention_policy', {})
        keep_last = html.escape(str(retention_policy.get('keep_last', '7')))
        keep_daily = html.escape(str(retention_policy.get('keep_daily', '7')))
        keep_weekly = html.escape(str(retention_policy.get('keep_weekly', '4')))
        keep_monthly = html.escape(str(retention_policy.get('keep_monthly', '6')))
        keep_hourly = html.escape(str(retention_policy.get('keep_hourly', '6')))
        keep_yearly = html.escape(str(retention_policy.get('keep_yearly', '0')))
        
        discard_schedule = html.escape(data.get('maintenance_discard_schedule', '0 3 * * *'))
        check_schedule = html.escape(data.get('maintenance_check_schedule', '0 2 * * 0'))
        
        # Render based on mode
        if mode == 'auto':
            display_html = self._render_auto_mode()
        elif mode == 'user':
            display_html = self._render_user_mode(discard_schedule, check_schedule, 
                                                keep_last, keep_daily, keep_weekly, keep_monthly, keep_hourly, keep_yearly)
        elif mode == 'off':
            display_html = self._render_off_mode()
        else:
            display_html = '<div id="maintenance_display"></div>'
        
        # Update hidden field with new mode via out-of-band swap
        hidden_field_update = f'<input type="hidden" id="restic_maintenance" name="restic_maintenance" value="{mode}" hx-swap-oob="true">'
        
        return display_html + hidden_field_update
    
    def _render_auto_mode(self):
        """Render automatic maintenance mode"""
        return '''
        <div id="maintenance_display">
            <div id="auto_help_text" class="help-text">
                Automatic maintenance uses safe defaults: daily cleanup at 3am, weekly integrity checks Sunday 2am, 
                keeps last 7 snapshots plus 7 daily, 4 weekly, 6 monthly.
            </div>
            <div id="user_mode_section" class="hidden"></div>
        </div>
        '''
    
    def _render_user_mode(self, discard_schedule, check_schedule, keep_last, keep_daily, keep_weekly, keep_monthly, keep_hourly, keep_yearly):
        """Render user-configured maintenance mode with dual toggle"""
        return f'''
        <div id="maintenance_display">
            <div id="auto_help_text" class="hidden"></div>
            <div id="user_mode_section">
                <!-- Second Toggle: Config vs Off -->
                <div class="toggle-section mt-10">
                    <span class="toggle-label">Config</span>
                    <button type="button" class="toggle-switch left" 
                            hx-post="/htmx/maintenance-toggle"
                            hx-target="#maintenance_display"
                            hx-vals="js:{{mode: document.querySelector('#restic_maintenance').value === 'user' ? 'off' : 'user'}}"
                            hx-include="[name^='maintenance_'], [name^='keep_']">
                        <div class="toggle-button"></div>
                    </button>
                    <span class="toggle-label">Off</span>
                </div>
                
                <div id="config_help_text" class="help-text mt-10">
                    Configure your own maintenance schedules and retention policies.
                </div>
                <div id="off_help_text" class="hidden"></div>
                <div id="manual_config_options">
                    <div class="form-group">
                        <label for="maintenance_discard_schedule">Discard Schedule (Cron):</label>
                        <input type="text" name="maintenance_discard_schedule" value="{discard_schedule}" 
                               placeholder="0 3 * * *" title="When to run forget+prune operations">
                        <div class="help-text">When to run cleanup (forget + prune operations)</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="maintenance_check_schedule">Check Schedule (Cron):</label>
                        <input type="text" name="maintenance_check_schedule" value="{check_schedule}" 
                               placeholder="0 2 * * 0" title="When to run repository integrity checks">
                        <div class="help-text">When to run integrity checks</div>
                    </div>
                    
                    <h4>Retention Policy</h4>
                    <div class="form-group">
                        <label for="keep_last">Keep Last:</label>
                        <input type="number" name="keep_last" value="{keep_last}" min="1" 
                               title="Always keep this many recent snapshots">
                        <div class="help-text">Always keep this many recent snapshots</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="keep_daily">Keep Daily:</label>
                        <input type="number" name="keep_daily" value="{keep_daily}" min="0" 
                               title="Keep this many daily snapshots">
                    </div>
                    
                    <div class="form-group">
                        <label for="keep_weekly">Keep Weekly:</label>
                        <input type="number" name="keep_weekly" value="{keep_weekly}" min="0" 
                               title="Keep this many weekly snapshots">
                    </div>
                    
                    <div class="form-group">
                        <label for="keep_monthly">Keep Monthly:</label>
                        <input type="number" name="keep_monthly" value="{keep_monthly}" min="0" 
                               title="Keep this many monthly snapshots">
                    </div>
                    
                    <div class="form-group">
                        <label for="keep_hourly">Keep Hourly:</label>
                        <input type="number" name="keep_hourly" value="{keep_hourly}" min="0" 
                               title="Keep this many hourly snapshots">
                    </div>
                    
                    <div class="form-group">
                        <label for="keep_yearly">Keep Yearly:</label>
                        <input type="number" name="keep_yearly" value="{keep_yearly}" min="0" 
                               title="Keep this many yearly snapshots">
                    </div>
                </div>
            </div>
        </div>
        '''
    
    def _render_off_mode(self):
        """Render maintenance disabled mode"""
        return '''
        <div id="maintenance_display">
            <div id="auto_help_text" class="hidden"></div>
            <div id="user_mode_section">
                <!-- Second Toggle: Config vs Off -->
                <div class="toggle-section mt-10">
                    <span class="toggle-label">Config</span>
                    <button type="button" class="toggle-switch right" 
                            hx-post="/htmx/maintenance-toggle"
                            hx-target="#maintenance_display"
                            hx-vals="js:{mode: document.querySelector('#restic_maintenance').value === 'off' ? 'user' : 'off'}"
                            hx-include="[name^='maintenance_'], [name^='keep_']">
                        <div class="toggle-button"></div>
                    </button>
                    <span class="toggle-label">Off</span>
                </div>
                
                <div id="config_help_text" class="hidden"></div>
                <div id="off_help_text" class="help-text mt-10">
                    Maintenance disabled. Repository will grow indefinitely without cleanup.
                    Manual maintenance via `restic forget` and `restic prune` required.
                </div>
                <div id="manual_config_options" class="hidden"></div>
            </div>
        </div>
        '''
    
    def render_maintenance_section_visibility(self, dest_type, existing_data=None):
        """Render entire maintenance section based on destination type"""
        if dest_type != 'restic':
            return '<div id="maintenance_section" class="hidden"></div>'
        
        # For Restic, show the maintenance section
        data = existing_data or {}
        current_mode = data.get('restic_maintenance', 'auto')
        
        return f'''
        <div id="maintenance_section" class="form-section">
            <div class="section-content">
                <h2 class="section-header">Repository Maintenance</h2>
                <div class="form-group">
                    <label>Maintenance Mode:</label>
                    <div class="toggle-switch">
                        <div class="toggle-container {'left' if current_mode == 'auto' else 'right'}" 
                             id="maintenanceFirstToggle" 
                             hx-post="/htmx/maintenance-toggle"
                             hx-vals="js:{{mode: document.getElementById('maintenanceFirstToggle').classList.contains('left') ? 'user' : 'auto'}}"
                             hx-target="#maintenance_display"
                             hx-swap="outerHTML"
                             hx-include="[name^='maintenance_'], [name^='keep_']"
                             onclick="this.classList.toggle('left'); this.classList.toggle('right');">
                            <div class="toggle-slider"></div>
                            <span class="toggle-option left">Auto</span>
                            <span class="toggle-option right">User</span>
                        </div>
                    </div>
                </div>
                
                <div class="form-group" id="user_toggle_section" style="{'display: none' if current_mode == 'auto' else ''}">
                    <label>User Mode:</label>
                    <div class="toggle-switch">
                        <div class="toggle-container {'left' if current_mode == 'user' else 'right'}" 
                             id="maintenanceSecondToggle"
                             hx-post="/htmx/maintenance-toggle"
                             hx-vals="js:{{mode: document.getElementById('maintenanceSecondToggle').classList.contains('left') ? 'off' : 'user'}}"
                             hx-target="#maintenance_display"
                             hx-swap="outerHTML"
                             hx-include="[name^='maintenance_'], [name^='keep_']"
                             onclick="this.classList.toggle('left'); this.classList.toggle('right');">
                            <div class="toggle-slider"></div>
                            <span class="toggle-option left">Config</span>
                            <span class="toggle-option right">Off</span>
                        </div>
                    </div>
                </div>
                
                <input type="hidden" id="restic_maintenance" name="restic_maintenance" value="{current_mode}">
                
                {self.render_maintenance_display(current_mode, existing_data)}
            </div>
        </div>
        '''