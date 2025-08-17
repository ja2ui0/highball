"""
Form data service for generating template variables
Refactored for modularity and maintainability
"""
import html
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class SourceConfig:
    """Source configuration fields"""
    source_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    
    # Multi-path support
    source_paths: list = field(default_factory=list)


@dataclass  
class DestConfig:
    """Standard destination configuration fields"""
    dest_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    rsyncd_hostname: str = ""
    rsyncd_share: str = ""
    rsync_options: str = ""


@dataclass
class ResticConfig:
    """Restic repository configuration fields"""
    repo_type: str = ""
    password: str = ""
    
    # Repository type specific fields
    local_path: str = ""
    
    # REST fields
    rest_hostname: str = ""
    rest_port: str = "8000"
    rest_path: str = ""
    rest_use_https: bool = True
    rest_username: str = ""
    rest_password: str = ""
    
    # S3 fields
    s3_endpoint: str = "s3.amazonaws.com"
    s3_bucket: str = ""
    s3_prefix: str = ""
    aws_access_key: str = ""
    aws_secret_key: str = ""
    
    # rclone fields
    rclone_remote: str = ""
    rclone_path: str = ""
    
    # SFTP fields
    sftp_hostname: str = ""
    sftp_username: str = ""
    sftp_path: str = ""


@dataclass
class MaintenanceConfig:
    """Maintenance configuration fields"""
    restic_maintenance: str = "auto"  # "auto", "user", or "off"
    maintenance_discard_schedule: str = ""
    maintenance_check_schedule: str = ""
    # Retention policy fields
    keep_last: Optional[int] = None
    keep_hourly: Optional[int] = None
    keep_daily: Optional[int] = None
    keep_weekly: Optional[int] = None
    keep_monthly: Optional[int] = None
    keep_yearly: Optional[int] = None


@dataclass
class JobFormData:
    """Structured data for job form template variables"""
    # Form metadata
    is_edit: bool = False
    job_name: str = ""
    error_message: str = ""
    
    # Configuration sections
    source: SourceConfig = field(default_factory=SourceConfig)
    dest: DestConfig = field(default_factory=DestConfig)
    restic: ResticConfig = field(default_factory=ResticConfig)
    maintenance: MaintenanceConfig = field(default_factory=MaintenanceConfig)
    
    # Schedule configuration
    schedule_type: str = "manual"
    cron_pattern: str = ""
    
    # Patterns
    includes: str = ""
    excludes: str = ""
    
    # Job settings
    enabled: bool = True
    respect_conflicts: bool = True
    
    # Notification settings
    notifications: list = field(default_factory=list)
    
    # Feedback variables
    feedback_type: str = ""  # 'success', 'error', or empty
    feedback_message: str = ""
    feedback_payload: str = ""
    
    def to_template_vars(self) -> Dict[str, str]:
        """Convert to template variables with proper escaping and formatting"""
        template_vars = {}
        
        # Build template variables modularly
        template_vars.update(self._get_form_metadata())
        template_vars.update(self._get_source_variables())
        template_vars.update(self._get_dest_variables()) 
        template_vars.update(self._get_restic_variables())
        template_vars.update(self._get_maintenance_variables())
        template_vars.update(self._get_schedule_variables())
        template_vars.update(self._get_pattern_variables())
        template_vars.update(self._get_checkbox_variables())
        template_vars.update(self._get_notification_variables())
        template_vars.update(self._get_special_variables())
        template_vars.update(self._get_feedback_variables())
        
        return template_vars
    
    def _get_form_metadata(self) -> Dict[str, str]:
        """Get form metadata variables"""
        page_title = "Edit Backup Job" if self.is_edit else "Add Backup Job"
        form_title = f"Edit Backup Job: {html.escape(self.job_name)}" if self.is_edit else "Add New Backup Job"
        submit_text = "Update Backup Job" if self.is_edit else "Create Job"
        
        # Generate form-specific fields
        hidden_fields = ""
        delete_form = ""
        if self.is_edit:
            hidden_fields = f'<input type="hidden" name="original_job_name" value="{html.escape(self.job_name)}">'
            delete_form = self._generate_delete_form()
        
        # Generate error message HTML
        error_html = ""
        if self.error_message:
            error_html = f'''
                <div class="alert alert-error" style="margin-bottom: var(--space-lg);">
                    <strong>Error:</strong> {html.escape(self.error_message)}
                </div>
            '''
        
        return {
            'PAGE_TITLE': page_title,
            'FORM_TITLE': form_title,
            'SUBMIT_BUTTON_TEXT': submit_text,
            'HIDDEN_FIELDS': hidden_fields,
            'DELETE_FORM': delete_form,
            'JOB_NAME': html.escape(self.job_name),
            'ERROR_MESSAGE': error_html,
        }
    
    def _get_source_variables(self) -> Dict[str, str]:
        """Get source configuration variables"""
        vars_dict = {
            'SOURCE_LOCAL_SELECTED': 'selected' if self.source.source_type == 'local' else '',
            'SOURCE_SSH_SELECTED': 'selected' if self.source.source_type == 'ssh' else '',
            'SOURCE_LOCAL_PATH': self.source.local_path,
            'SOURCE_SSH_HOSTNAME': self.source.ssh_hostname,
            'SOURCE_SSH_USERNAME': self.source.ssh_username,
            'SOURCE_SSH_PATH': self.source.ssh_path,
        }
        
        # Add multi-path variables
        vars_dict.update(self._get_multi_path_variables())
        
        return vars_dict
    
    def _get_multi_path_variables(self) -> Dict[str, str]:
        """Get multi-path template variables - generate for ALL paths"""
        import json
        vars_dict = {}
        
        if self.source.source_paths:
            # Generate variables for all existing paths
            for i, path_config in enumerate(self.source.source_paths):
                vars_dict[f'SOURCE_PATH_{i}'] = path_config.get('path', '')
                vars_dict[f'SOURCE_INCLUDES_{i}'] = '\n'.join(path_config.get('includes', []))
                vars_dict[f'SOURCE_EXCLUDES_{i}'] = '\n'.join(path_config.get('excludes', []))
            
            # Set the count of paths for JavaScript initialization
            vars_dict['SOURCE_PATHS_COUNT'] = str(len(self.source.source_paths))
            
            # Generate JSON data for JavaScript initialization
            paths_json = []
            for path_config in self.source.source_paths:
                paths_json.append({
                    'path': path_config.get('path', ''),
                    'includes': path_config.get('includes', []),
                    'excludes': path_config.get('excludes', [])
                })
            
            vars_dict['SOURCE_PATHS_JSON'] = json.dumps(paths_json)
            
        else:
            # Backward compatibility: use old single path if source_paths not available
            if self.source.source_type == 'local':
                vars_dict['SOURCE_PATH_0'] = self.source.local_path
            elif self.source.source_type == 'ssh':
                vars_dict['SOURCE_PATH_0'] = self.source.ssh_path
            else:
                vars_dict['SOURCE_PATH_0'] = ''
            
            vars_dict['SOURCE_INCLUDES_0'] = self.includes
            vars_dict['SOURCE_EXCLUDES_0'] = self.excludes
            vars_dict['SOURCE_PATHS_COUNT'] = '1'
            vars_dict['SOURCE_PATHS_JSON'] = json.dumps([{
                'path': vars_dict['SOURCE_PATH_0'],
                'includes': self.includes.split('\n') if self.includes else [],
                'excludes': self.excludes.split('\n') if self.excludes else []
            }])
        
        return vars_dict
    
    def _get_dest_variables(self) -> Dict[str, str]:
        """Get destination configuration variables"""
        # Share selection logic for rsyncd
        share_vars = self._get_share_selection_variables()
        
        return {
            'DEST_LOCAL_SELECTED': 'selected' if self.dest.dest_type == 'local' else '',
            'DEST_SSH_SELECTED': 'selected' if self.dest.dest_type == 'ssh' else '',
            'DEST_RSYNCD_SELECTED': 'selected' if self.dest.dest_type == 'rsyncd' else '',
            'DEST_RESTIC_SELECTED': 'selected' if self.dest.dest_type == 'restic' else '',
            'DEST_LOCAL_PATH': self.dest.local_path,
            'DEST_SSH_HOSTNAME': self.dest.ssh_hostname,
            'DEST_SSH_USERNAME': self.dest.ssh_username,
            'DEST_SSH_PATH': self.dest.ssh_path,
            'DEST_RSYNCD_HOSTNAME': self.dest.rsyncd_hostname,
            'DEST_RSYNCD_SHARE': self.dest.rsyncd_share,
            'DEST_RSYNC_OPTIONS': self.dest.rsync_options,
            'RESTIC_OPTION': f'<option value="restic" {("selected" if self.dest.dest_type == "restic" else "")}>Restic Repository</option>',
            **share_vars
        }
    
    def _get_restic_variables(self) -> Dict[str, str]:
        """Get Restic configuration variables"""
        return {
            'RESTIC_REPO_TYPE': self.restic.repo_type,
            'RESTIC_PASSWORD': self.restic.password,
            'RESTIC_LOCAL_PATH': self.restic.local_path,
            'RESTIC_REST_HOSTNAME': self.restic.rest_hostname,
            'RESTIC_REST_PORT': self.restic.rest_port,
            'RESTIC_REST_PATH': self.restic.rest_path,
            'RESTIC_REST_USE_HTTPS_CHECKED': 'checked' if self.restic.rest_use_https else '',
            'RESTIC_REST_USERNAME': self.restic.rest_username,
            'RESTIC_REST_PASSWORD': self.restic.rest_password,
            'RESTIC_S3_ENDPOINT': self.restic.s3_endpoint,
            'RESTIC_S3_BUCKET': self.restic.s3_bucket,
            'RESTIC_S3_PREFIX': self.restic.s3_prefix,
            'RESTIC_AWS_ACCESS_KEY': self.restic.aws_access_key,
            'RESTIC_AWS_SECRET_KEY': self.restic.aws_secret_key,
            'RESTIC_RCLONE_REMOTE': self.restic.rclone_remote,
            'RESTIC_RCLONE_PATH': self.restic.rclone_path,
            'RESTIC_SFTP_HOSTNAME': self.restic.sftp_hostname,
            'RESTIC_SFTP_USERNAME': self.restic.sftp_username,
            'RESTIC_SFTP_PATH': self.restic.sftp_path,
        }
    
    def _get_maintenance_variables(self) -> Dict[str, str]:
        """Get maintenance configuration variables"""
        mode = self.maintenance.restic_maintenance
        
        # First toggle: Auto (left) / User (right)
        first_toggle_class = 'left' if mode == 'auto' else 'right'
        
        # Second toggle: Config (left) / Off (right) - only for user mode
        # Default to Config (left) when switching to User mode
        second_toggle_class = 'right' if mode == 'off' else 'left'
        
        return {
            'RESTIC_MAINTENANCE_MODE': mode,
            'MAINTENANCE_FIRST_TOGGLE_CLASS': first_toggle_class,
            'MAINTENANCE_SECOND_TOGGLE_CLASS': second_toggle_class,
            'MAINTENANCE_DISCARD_SCHEDULE': self.maintenance.maintenance_discard_schedule,
            'MAINTENANCE_CHECK_SCHEDULE': self.maintenance.maintenance_check_schedule,
            'KEEP_LAST': str(self.maintenance.keep_last) if self.maintenance.keep_last is not None else '',
            'KEEP_HOURLY': str(self.maintenance.keep_hourly) if self.maintenance.keep_hourly is not None else '',
            'KEEP_DAILY': str(self.maintenance.keep_daily) if self.maintenance.keep_daily is not None else '',
            'KEEP_WEEKLY': str(self.maintenance.keep_weekly) if self.maintenance.keep_weekly is not None else '',
            'KEEP_MONTHLY': str(self.maintenance.keep_monthly) if self.maintenance.keep_monthly is not None else '',
            'KEEP_YEARLY': str(self.maintenance.keep_yearly) if self.maintenance.keep_yearly is not None else '',
        }
    
    def _get_schedule_variables(self) -> Dict[str, str]:
        """Get schedule configuration variables"""
        return {
            'SCHEDULE_MANUAL_SELECTED': 'selected' if self.schedule_type == 'manual' else '',
            'SCHEDULE_HOURLY_SELECTED': 'selected' if self.schedule_type == 'hourly' else '',
            'SCHEDULE_DAILY_SELECTED': 'selected' if self.schedule_type == 'daily' else '',
            'SCHEDULE_WEEKLY_SELECTED': 'selected' if self.schedule_type == 'weekly' else '',
            'SCHEDULE_MONTHLY_SELECTED': 'selected' if self.schedule_type == 'monthly' else '',
            'SCHEDULE_CRON_SELECTED': 'selected' if self.schedule_type == 'cron' else '',
            'CRON_PATTERN': self.cron_pattern,
        }
    
    def _get_pattern_variables(self) -> Dict[str, str]:
        """Get include/exclude pattern variables"""
        return {
            'INCLUDES': self.includes,
            'EXCLUDES': self.excludes,
        }
    
    def _get_checkbox_variables(self) -> Dict[str, str]:
        """Get checkbox state variables"""
        return {
            'ENABLED_CHECKED': 'checked' if self.enabled else '',
            'CONFLICTS_CHECKED': 'checked' if self.respect_conflicts else ''
        }
    
    def _get_share_selection_variables(self) -> Dict[str, str]:
        """Get rsyncd share selection variables"""
        if self.is_edit and self.dest.dest_type == 'rsyncd' and self.dest.rsyncd_share:
            return {
                'SHARE_SELECTION_CLASS': "",
                'SHARE_LABEL': "Share",
                'SHARE_OPTIONS': f'<option value="{html.escape(self.dest.rsyncd_share)}" selected>{html.escape(self.dest.rsyncd_share)}</option>'
            }
        else:
            return {
                'SHARE_SELECTION_CLASS': "hidden",
                'SHARE_LABEL': "Available Shares",
                'SHARE_OPTIONS': ""
            }
    
    def _get_notification_variables(self) -> Dict[str, str]:
        """Get notification configuration variables"""
        import json
        
        # For now, we'll get available providers from a service
        # This will be populated by checking global configuration
        available_providers = self._get_available_notification_providers()
        
        # Generate JSON data for JavaScript
        return {
            'AVAILABLE_PROVIDERS_JSON': json.dumps(available_providers),
            'EXISTING_NOTIFICATIONS_JSON': json.dumps(self.notifications),
            'AVAILABLE_PROVIDERS_OPTIONS': self._generate_provider_options(available_providers),
            'ADD_PROVIDER_CLASS': '' if available_providers else 'hidden'
        }
    
    def _get_available_notification_providers(self) -> list:
        """Get list of globally configured notification providers"""
        # This will need to be passed in via the builder or form context
        # For now, return common providers - will be improved when we wire up the handlers
        return ['telegram', 'email']
    
    def _generate_provider_options(self, providers: list) -> str:
        """Generate HTML options for provider dropdown"""
        options = ""
        for provider in providers:
            display_name = provider.capitalize()
            options += f'<option value="{provider}">{display_name}</option>\n'
        return options
    
    def _get_special_variables(self) -> Dict[str, str]:
        """Get special computed variables"""
        return {
            'DEFAULT_RSYNC_OPTIONS': '-a --info=stats1 --delete --delete-excluded'
        }
    
    def _get_feedback_variables(self) -> Dict[str, str]:
        """Get feedback section variables"""
        if not self.feedback_type:
            return {'FEEDBACK_SECTION': ''}
        
        # Generate feedback section HTML using existing classes
        alert_class = 'alert-success' if self.feedback_type == 'success' else 'alert-error'
        
        feedback_html = f'''
        <div class="validation-section">
            <div class="{alert_class}" style="margin-bottom: var(--space-lg);">
                {html.escape(self.feedback_message)}
            </div>
            <div class="validation-content">
                <h3>Configuration Payload:</h3>
                <div class="log-container">
                    <pre style="margin: 0; font-family: monospace; white-space: pre-wrap;">{html.escape(self.feedback_payload)}</pre>
                </div>
            </div>
        </div>
        '''
        
        return {'FEEDBACK_SECTION': feedback_html}
    
    def _generate_delete_form(self) -> str:
        """Generate delete form HTML for edit mode"""
        return f'''
        <form method="post" action="/delete-job" class="mt-20" onsubmit="return confirm('Are you sure you want to delete this backup job?')">
            <input type="hidden" name="job_name" value="{html.escape(self.job_name)}">
            <input type="submit" value="Delete Job" class="button button-danger">
        </form>'''


