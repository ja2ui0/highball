"""
Maintenance form data parsing
Handles parsing maintenance configuration from job forms
"""

def _safe_get_value(form_data, key, default=''):
    """Safely get single value from form data"""
    values = form_data.get(key, [])
    return values[0] if values and values[0] else default

def _safe_get_int(form_data, key, default=None):
    """Safely get integer value from form data"""
    value = _safe_get_value(form_data, key)
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return default

class MaintenanceFormParser:
    """Parses maintenance configuration from job forms"""
    
    @staticmethod
    def parse_maintenance_config(form_data):
        """Parse maintenance configuration from form data"""
        # Get maintenance mode from toggle: auto, user, or off
        maintenance_mode = _safe_get_value(form_data, 'restic_maintenance', 'auto')
        
        # Always create base config with maintenance mode
        config = {
            'restic_maintenance': maintenance_mode
        }
        
        # If mode is 'auto' or 'off', only include the mode
        if maintenance_mode in ['auto', 'off']:
            return {
                'valid': True,
                'maintenance_config': config
            }
        
        # Parse user maintenance options when mode is 'user'
        
        # Parse schedules (optional)
        discard_schedule = _safe_get_value(form_data, 'maintenance_discard_schedule')
        if discard_schedule:
            config['maintenance_discard_schedule'] = discard_schedule
        
        check_schedule = _safe_get_value(form_data, 'maintenance_check_schedule')
        if check_schedule:
            config['maintenance_check_schedule'] = check_schedule
        
        # Parse retention policy (optional)
        retention_policy = {}
        
        keep_last = _safe_get_int(form_data, 'keep_last')
        if keep_last is not None:
            retention_policy['keep_last'] = keep_last
            
        keep_hourly = _safe_get_int(form_data, 'keep_hourly')
        if keep_hourly is not None:
            retention_policy['keep_hourly'] = keep_hourly
            
        keep_daily = _safe_get_int(form_data, 'keep_daily')
        if keep_daily is not None:
            retention_policy['keep_daily'] = keep_daily
            
        keep_weekly = _safe_get_int(form_data, 'keep_weekly')
        if keep_weekly is not None:
            retention_policy['keep_weekly'] = keep_weekly
            
        keep_monthly = _safe_get_int(form_data, 'keep_monthly')
        if keep_monthly is not None:
            retention_policy['keep_monthly'] = keep_monthly
            
        keep_yearly = _safe_get_int(form_data, 'keep_yearly')
        if keep_yearly is not None:
            retention_policy['keep_yearly'] = keep_yearly
        
        # Only add retention policy if at least one field is set
        if retention_policy:
            config['retention_policy'] = retention_policy
        
        return {
            'valid': True,
            'maintenance_config': config
        }