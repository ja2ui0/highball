"""
TRANSIENT FILE - TO BE DELETED AFTER JOB FORM REBUILD

Legacy form data structures from models/forms.py that will be discarded
after the job form is rebuilt to use dropdown selection of pre-defined
origins and destinations instead of inline definition.

This file exists temporarily to keep define.py working during the transition.
DELETE THIS FILE once the new job form using dropdown selection is complete.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from models.forms import safe_get_value


# =============================================================================
# TRANSIENT FORM DATA STRUCTURES - TO BE DISCARDED
# =============================================================================

class SourceConfig(BaseModel):
    """TRANSIENT: Form concern - source configuration data structure"""
    source_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    
    # Multi-path support
    source_paths: List[Dict[str, Any]] = Field(default_factory=list)


class DestConfig(BaseModel):
    """TRANSIENT: Form concern - standard destination configuration data structure"""
    dest_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    rsyncd_hostname: str = ""
    rsyncd_share: str = ""
    rsync_options: str = ""


class ResticConfig(BaseModel):
    """TRANSIENT: Form concern - Restic repository configuration data structure"""
    repo_type: str = ""
    password: str = ""
    
    # Repository type specific fields
    local_path: str = ""
    
    # REST fields
    rest_hostname: str = ""
    rest_port: str = "8000"
    rest_path: str = ""
    rest_use_root: bool = False
    rest_use_https: bool = True
    rest_username: str = ""
    rest_password: str = ""
    
    # S3 fields
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint: str = ""
    
    # SFTP fields
    sftp_hostname: str = ""
    sftp_path: str = ""
    
    # Rclone fields
    rclone_config: str = ""


class JobFormData(BaseModel):
    """TRANSIENT: Form concern - complete job form data structure"""
    job_name: str = ""
    source_config: SourceConfig = Field(default_factory=SourceConfig)
    dest_config: DestConfig = Field(default_factory=DestConfig)
    restic_config: ResticConfig = Field(default_factory=ResticConfig)
    schedule: str = ""
    enabled: bool = True
    respect_conflicts: bool = True
    restic_maintenance: str = "auto"
    notifications: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# TEMPORARY PARSERS - Used during job form revamp transition  
# =============================================================================

class SourceParser:
    """Parse source configurations (SSH, local) - temporary location during revamp"""
    
    @staticmethod
    def parse_ssh_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH source configuration"""
        hostname = safe_get_value(form_data, 'hostname')
        username = safe_get_value(form_data, 'username')
        
        if not hostname:
            return {'valid': False, 'error': 'SSH hostname is required'}
        if not username:
            return {'valid': False, 'error': 'SSH username is required'}
        
        config = {
            'hostname': hostname.strip(),
            'username': username.strip()
        }
        
        # Include container runtime if detected during validation
        container_runtime = safe_get_value(form_data, 'container_runtime')
        if container_runtime:
            config['container_runtime'] = container_runtime
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_local_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local source configuration"""
        # Local sources need minimal configuration
        return {'valid': True, 'config': {}}


class JobFormParser:
    """Unified job form parser - temporary location during revamp"""
    
    @staticmethod
    def parse_job_form(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse complete job form data"""
        # Basic job info
        job_name = safe_get_value(form_data, 'job_name').strip()
        if not job_name:
            return {'valid': False, 'error': 'Job name is required'}
        
        # Source parsing
        source_result = JobFormParser.parse_source_configuration(form_data)
        if not source_result['valid']:
            return source_result
        source_config = source_result['config']
        
        # Destination parsing
        dest_result = JobFormParser.parse_destination_configuration(form_data)
        if not dest_result['valid']:
            return dest_result
        dest_config = dest_result['config']
        
        # Handle schedule
        schedule = safe_get_value(form_data, 'schedule', 'manual')
        if schedule == 'custom':
            cron_pattern = safe_get_value(form_data, 'cron_pattern').strip()
            if cron_pattern:
                schedule = cron_pattern
            else:
                return {'valid': False, 'error': 'Cron pattern is required when Custom Cron Pattern is selected'}
        
        enabled = 'enabled' in form_data
        respect_conflicts = 'respect_conflicts' in form_data
        
        # Parse notification configuration
        from jobs.handlers.pages import NotificationParser
        notification_result = NotificationParser.parse_notification_config(form_data)
        if not notification_result['valid']:
            return notification_result
        notifications = notification_result['notifications']
        
        # Parse maintenance configuration (only for Restic destinations)
        maintenance_config = None
        if dest_config.get('repo_type'):  # Restic destination
            from dests.handlers.pages import MaintenanceParser
            maintenance_result = MaintenanceParser.parse_maintenance_config(form_data)
            if not maintenance_result['valid']:
                return maintenance_result
            maintenance_config = maintenance_result.get('maintenance_config')
        
        job_data = {
            'valid': True,
            'job_name': job_name,
            'source_type': source_config['source_type'],
            'source_config': source_config,
            'dest_type': dest_config['dest_type'],
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
    def parse_source_configuration(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse complete source configuration including paths"""
        source_type = safe_get_value(form_data, 'source_type')
        if not source_type:
            return {'valid': False, 'error': 'Source type is required'}
        
        # Schema-driven source parsing
        from origins.schema import SOURCE_TYPE_SCHEMAS
        
        if source_type not in SOURCE_TYPE_SCHEMAS:
            return {'valid': False, 'error': f'Unknown source type: {source_type}'}
        
        # Parse using type-specific parser (following naming convention)
        parser_method_name = f'parse_{source_type}_source'
        if hasattr(SourceParser, parser_method_name):
            parser_method = getattr(SourceParser, parser_method_name)
            source_result = parser_method(form_data)
        else:
            return {'valid': False, 'error': f'No parser available for source type: {source_type}'}
        
        if not source_result['valid']:
            return source_result
        source_config = source_result['config']
        
        # Parse source paths (common to all source types)
        from jobs.handlers.pages import SourcePathsParser
        source_paths_data = SourcePathsParser.parse_multi_path_options(form_data)
        if not source_paths_data['valid']:
            return source_paths_data
        
        # Combine config with paths
        source_config['source_type'] = source_type
        source_config['source_paths'] = source_paths_data['source_paths']
        
        return {'valid': True, 'config': source_config}
    
    @staticmethod
    def parse_destination_configuration(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse destination configuration"""
        dest_type = safe_get_value(form_data, 'dest_type')
        if not dest_type:
            return {'valid': False, 'error': 'Destination type is required'}
        
        # Schema-driven destination parsing
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
        if dest_type not in DESTINATION_TYPE_SCHEMAS:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
        
        # Parse using type-specific parser (following naming convention)
        from dests.handlers.pages import DestinationParser
        parser_method_name = f'parse_{dest_type}_destination'
        if hasattr(DestinationParser, parser_method_name):
            parser_method = getattr(DestinationParser, parser_method_name)
            dest_result = parser_method(form_data)
        else:
            return {'valid': False, 'error': f'No parser available for destination type: {dest_type}'}
        
        if not dest_result['valid']:
            return dest_result
        
        dest_config = dest_result['config']
        dest_config['dest_type'] = dest_type
        
        return {'valid': True, 'config': dest_config}


# =============================================================================
# TEMPORARY ADMIN PREVIEW METHODS - Used during job form revamp transition
# =============================================================================

from fastapi import Request
from fastapi.responses import HTMLResponse
from shared.handlers.templating import TemplateService

class AdminJobPreviewMethods:
    """Temporary admin methods for job preview functionality during revamp"""
    
    def __init__(self):
        self.template_service = TemplateService()
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Extract single value from form data"""
        values = form_data.get(field_name, [])
        if isinstance(values, list):
            return values[0] if values else default
        return values if values else default
    
    async def preview_config_htmx(self, request) -> HTMLResponse:
        """Generate and display job config preview - HTMX handler"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]

        # Business logic (preserve original implementation)
        try:
            if not form_data:
                html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content="Error: No form data received")
                return HTMLResponse(content=html_response)
            
            # Parse the form data using the existing parser
            parser = JobFormParser()
            result = parser.parse_job_form(form_data)
            
            if not result.get('valid', False):
                error_msg = result.get('error', 'Unknown parsing error')
                # Add some debug info to the error
                restic_repo_type = safe_get_value(form_data, 'restic_repo_type')
                dest_type = safe_get_value(form_data, 'dest_type')
                
                debug_error = f"Form Validation Error: {error_msg}\n\n"
                debug_error += f"Debug Info:\n"
                debug_error += f"- restic_repo_type extracted: '{restic_repo_type}'\n"
                debug_error += f"- dest_type extracted: '{dest_type}'\n"
                debug_error += f"- Form data keys: {list(form_data.keys())}\n"
                
                html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content=debug_error)
                return HTMLResponse(content=html_response)
            
            # Build the job config as it would appear in config.yaml
            job_data = result.copy()
            if 'valid' in job_data:
                del job_data['valid']  # Remove the validation flag
            
            # Format as YAML for display
            import yaml
            yaml_content = yaml.dump({job_data.get('job_name', 'unnamed_job'): job_data}, 
                                   default_flow_style=False, sort_keys=False)
            
            html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                   preview_content=yaml_content)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                   preview_content=f"Error generating preview: {str(e)}\n\nCheck server logs for details.")

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    async def check_form_changes_htmx(self, request) -> HTMLResponse:
        """Check if form has changes compared to original config - HTMX handler"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]

        # Business logic (preserve original implementation)
        try:
            import json
            job_parser = JobFormParser()
            
            # Get original config from hidden field
            original_config_str = self._get_form_value(form_data, 'original_job_config')
            if not original_config_str:
                # No original config means this is add mode, always enable
                html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Create Job',
                                                       enabled=True)
                return HTMLResponse(content=html_response)
            
            # Parse current form data
            current_result = job_parser.parse_job_form(form_data)
            if not current_result['valid']:
                # Form is invalid, disable button
                html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=False)
                return HTMLResponse(content=html_response)
            
            # Compare configs (normalize for comparison)
            original_config = json.loads(original_config_str)
            current_config = current_result.copy()
            if 'valid' in current_config:
                del current_config['valid']
            
            # Compare as JSON strings for deep equality
            original_json = json.dumps(original_config, sort_keys=True)
            current_json = json.dumps(current_config, sort_keys=True)
            
            has_changes = original_json != current_json
            html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=has_changes)
            
        except Exception as e:
            # On error, default to enabled
            html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=True)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)