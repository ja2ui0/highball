"""
Form data service for generating template variables
Consolidates template variable generation using dataclasses
"""
import html
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class JobFormData:
    """Structured data for job form template variables"""
    # Form metadata
    is_edit: bool = False
    job_name: str = ""
    page_title: str = ""
    form_title: str = ""
    submit_button_text: str = ""
    
    # Source configuration
    source_type: str = ""
    source_local_path: str = ""
    source_ssh_hostname: str = ""
    source_ssh_username: str = ""
    source_ssh_path: str = ""
    
    # Destination configuration
    dest_type: str = ""
    dest_local_path: str = ""
    dest_ssh_hostname: str = ""
    dest_ssh_username: str = ""
    dest_ssh_path: str = ""
    dest_rsyncd_hostname: str = ""
    dest_rsyncd_share: str = ""
    
    # Schedule configuration
    schedule_type: str = "manual"
    cron_pattern: str = ""
    
    # Patterns
    includes: str = ""
    excludes: str = ""
    
    # Job settings
    enabled: bool = True
    respect_conflicts: bool = True
    
    def to_template_vars(self) -> Dict[str, str]:
        """Convert to template variables with proper escaping and formatting"""
        # Determine form type specific values
        page_title = "Edit Backup Job" if self.is_edit else "Add Backup Job"
        form_title = f"Edit Backup Job: {html.escape(self.job_name)}" if self.is_edit else "Add New Backup Job"
        submit_text = "Update Backup Job" if self.is_edit else "Create Job"
        
        # Hidden fields for edit mode
        hidden_fields = ""
        delete_form = ""
        if self.is_edit:
            hidden_fields = f'<input type="hidden" name="original_job_name" value="{html.escape(self.job_name)}">'
            delete_form = self._generate_delete_form()
        
        # Share selection configuration for rsyncd
        if self.is_edit and self.dest_type == 'rsyncd' and self.dest_rsyncd_share:
            share_selection_class = ""
            share_label = "Share"
            share_options = f'<option value="{html.escape(self.dest_rsyncd_share)}" selected>{html.escape(self.dest_rsyncd_share)}</option>'
        else:
            share_selection_class = "hidden"
            share_label = "Available Shares"
            share_options = ""
        
        return {
            # Form metadata
            'PAGE_TITLE': page_title,
            'FORM_TITLE': form_title,
            'SUBMIT_BUTTON_TEXT': submit_text,
            'HIDDEN_FIELDS': hidden_fields,
            'DELETE_FORM': delete_form,
            
            # Job fields
            'JOB_NAME': html.escape(self.job_name),
            
            # Source type selection
            'SOURCE_LOCAL_SELECTED': 'selected' if self.source_type == 'local' else '',
            'SOURCE_SSH_SELECTED': 'selected' if self.source_type == 'ssh' else '',
            
            # Source fields (already safe, no need to escape paths)
            'SOURCE_LOCAL_PATH': self.source_local_path,
            'SOURCE_SSH_HOSTNAME': self.source_ssh_hostname,
            'SOURCE_SSH_USERNAME': self.source_ssh_username,
            'SOURCE_SSH_PATH': self.source_ssh_path,
            
            # Dest type selection  
            'DEST_LOCAL_SELECTED': 'selected' if self.dest_type == 'local' else '',
            'DEST_SSH_SELECTED': 'selected' if self.dest_type == 'ssh' else '',
            'DEST_RSYNCD_SELECTED': 'selected' if self.dest_type == 'rsyncd' else '',
            
            # Dest fields
            'DEST_LOCAL_PATH': self.dest_local_path,
            'DEST_SSH_HOSTNAME': self.dest_ssh_hostname,
            'DEST_SSH_USERNAME': self.dest_ssh_username,
            'DEST_SSH_PATH': self.dest_ssh_path,
            'DEST_RSYNCD_HOSTNAME': self.dest_rsyncd_hostname,
            'DEST_RSYNCD_SHARE': self.dest_rsyncd_share,
            
            # Share selection
            'SHARE_SELECTION_CLASS': share_selection_class,
            'SHARE_LABEL': share_label,
            'SHARE_OPTIONS': share_options,
            
            # Patterns
            'INCLUDES': self.includes,
            'EXCLUDES': self.excludes,
            
            # Schedule selection
            'SCHEDULE_MANUAL_SELECTED': 'selected' if self.schedule_type == 'manual' else '',
            'SCHEDULE_HOURLY_SELECTED': 'selected' if self.schedule_type == 'hourly' else '',
            'SCHEDULE_DAILY_SELECTED': 'selected' if self.schedule_type == 'daily' else '',
            'SCHEDULE_WEEKLY_SELECTED': 'selected' if self.schedule_type == 'weekly' else '',
            'SCHEDULE_MONTHLY_SELECTED': 'selected' if self.schedule_type == 'monthly' else '',
            'SCHEDULE_CRON_SELECTED': 'selected' if self.schedule_type == 'cron' else '',
            'CRON_PATTERN': self.cron_pattern,
            
            # Checkboxes
            'ENABLED_CHECKED': 'checked' if self.enabled else '',
            'CONFLICTS_CHECKED': 'checked' if self.respect_conflicts else ''
        }
    
    def _generate_delete_form(self) -> str:
        """Generate delete form HTML for edit mode"""
        return f'''
        <form method="post" action="/delete-job" class="mt-20" onsubmit="return confirm('Are you sure you want to delete this backup job?')">
            <input type="hidden" name="job_name" value="{html.escape(self.job_name)}">
            <input type="submit" value="Delete Job" class="button button-danger">
        </form>'''


class JobFormDataBuilder:
    """Builder for creating JobFormData from job configurations"""
    
    @classmethod
    def from_job_config(cls, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Create JobFormData from existing job configuration"""
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        
        # Parse schedule - detect if it's a cron pattern
        schedule = job_config.get('schedule', 'manual')
        schedule_type = schedule
        cron_pattern = ''
        
        # Check if it's a cron pattern (has spaces and not in known types)
        known_schedule_types = ['manual', 'hourly', 'daily', 'weekly', 'monthly']
        if ' ' in schedule and schedule not in known_schedule_types:
            schedule_type = 'cron'
            cron_pattern = schedule
        
        return JobFormData(
            is_edit=True,
            job_name=job_name,
            
            # Source configuration
            source_type=job_config.get('source_type', ''),
            source_local_path=source_config.get('path', ''),
            source_ssh_hostname=source_config.get('hostname', ''),
            source_ssh_username=source_config.get('username', ''),
            source_ssh_path=source_config.get('path', ''),
            
            # Destination configuration
            dest_type=job_config.get('dest_type', ''),
            dest_local_path=dest_config.get('path', ''),
            dest_ssh_hostname=dest_config.get('hostname', ''),
            dest_ssh_username=dest_config.get('username', ''),
            dest_ssh_path=dest_config.get('path', ''),
            dest_rsyncd_hostname=dest_config.get('hostname', ''),
            dest_rsyncd_share=dest_config.get('share', ''),
            
            # Schedule
            schedule_type=schedule_type,
            cron_pattern=cron_pattern,
            
            # Patterns
            includes='\n'.join(job_config.get('includes', [])),
            excludes='\n'.join(job_config.get('excludes', [])),
            
            # Settings
            enabled=job_config.get('enabled', True),
            respect_conflicts=job_config.get('respect_conflicts', True)
        )
    
    @classmethod
    def for_new_job(cls) -> JobFormData:
        """Create JobFormData for new job creation"""
        return JobFormData(
            is_edit=False,
            # All other fields use their default values
        )