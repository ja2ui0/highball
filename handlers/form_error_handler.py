"""
Form error handler for displaying inline error messages
Handles form validation errors gracefully without scary error pages
"""
from services.job_form_data_builder import JobFormDataBuilder


class FormErrorHandler:
    """Handles form errors by displaying them inline on the form"""
    
    def __init__(self, template_service, job_manager):
        self.template_service = template_service
        self.job_manager = job_manager
    
    def show_form_with_error(self, handler, form_data, error_message):
        """Show job form with error message displayed inline"""
        # Rebuild form data from the submitted form to preserve user input
        try:
            # Try to build from form data to preserve user input
            form_obj = self._build_form_data_from_submitted_form(form_data)
            form_obj.error_message = error_message
        except Exception:
            # Fallback to empty form if parsing fails
            form_obj = JobFormDataBuilder.for_new_job()
            form_obj.error_message = error_message
        
        template_vars = form_obj.to_template_vars()
        html_content = self.template_service.render_template('job_form.html', **template_vars)
        self.template_service.send_html_response(handler, html_content)
    
    def _build_form_data_from_submitted_form(self, form_data):
        """Build JobFormData from submitted form to preserve user input"""
        # Get original job name to determine if this is an edit
        original_job_name = self._get_form_value(form_data, 'original_job_name')
        
        if original_job_name:
            # This is an edit - start with existing job data
            job_config = self.job_manager.get_job(original_job_name)
            if job_config:
                form_obj = JobFormDataBuilder.from_job_config(original_job_name, job_config)
            else:
                form_obj = JobFormDataBuilder.for_new_job()
        else:
            # This is a new job
            form_obj = JobFormDataBuilder.for_new_job()
        
        # Override with submitted form values to preserve user input
        self._populate_form_from_submission(form_obj, form_data)
        
        return form_obj
    
    def _populate_form_from_submission(self, form_obj, form_data):
        """Populate form object with submitted values to preserve user input"""
        # Update basic fields
        form_obj.job_name = self._get_form_value(form_data, 'job_name')
        form_obj.source.source_type = self._get_form_value(form_data, 'source_type')
        form_obj.source.local_path = self._get_form_value(form_data, 'source_local_path')
        form_obj.source.ssh_hostname = self._get_form_value(form_data, 'source_ssh_hostname')
        form_obj.source.ssh_username = self._get_form_value(form_data, 'source_ssh_username')
        form_obj.dest.dest_type = self._get_form_value(form_data, 'dest_type')
        form_obj.schedule_type = self._get_form_value(form_data, 'schedule')
        form_obj.enabled = self._get_form_value(form_data, 'enabled') == 'on'
        form_obj.respect_conflicts = self._get_form_value(form_data, 'respect_conflicts') == 'on'
        
        # Update Restic fields if present
        if self._get_form_value(form_data, 'dest_type') == 'restic':
            form_obj.restic.repo_type = self._get_form_value(form_data, 'restic_repo_type')
            form_obj.restic.password = self._get_form_value(form_data, 'restic_password')
            form_obj.restic.local_path = self._get_form_value(form_data, 'restic_local_path')
            form_obj.restic.rest_hostname = self._get_form_value(form_data, 'restic_rest_hostname')
            form_obj.restic.rest_port = self._get_form_value(form_data, 'restic_rest_port')
            form_obj.restic.rest_path = self._get_form_value(form_data, 'restic_rest_path')
            form_obj.restic.rest_use_https = 'restic_rest_use_https' in form_data
            form_obj.restic.rest_username = self._get_form_value(form_data, 'restic_rest_username')
            form_obj.restic.rest_password = self._get_form_value(form_data, 'restic_rest_password')
            
            # Update S3 fields
            form_obj.restic.s3_endpoint = self._get_form_value(form_data, 'restic_s3_endpoint')
            form_obj.restic.s3_bucket = self._get_form_value(form_data, 'restic_s3_bucket')
            form_obj.restic.s3_prefix = self._get_form_value(form_data, 'restic_s3_prefix')
            form_obj.restic.aws_access_key = self._get_form_value(form_data, 'restic_aws_access_key')
            form_obj.restic.aws_secret_key = self._get_form_value(form_data, 'restic_aws_secret_key')
            
            # Update rclone fields
            form_obj.restic.rclone_remote = self._get_form_value(form_data, 'restic_rclone_remote')
            form_obj.restic.rclone_path = self._get_form_value(form_data, 'restic_rclone_path')
            
            # Update SFTP fields
            form_obj.restic.sftp_hostname = self._get_form_value(form_data, 'restic_sftp_hostname')
            form_obj.restic.sftp_username = self._get_form_value(form_data, 'restic_sftp_username')
            form_obj.restic.sftp_path = self._get_form_value(form_data, 'restic_sftp_path')
    
    def _get_form_value(self, form_data, key, default=''):
        """Safely get form value handling both multidict and regular dict"""
        if hasattr(form_data, 'get'):
            values = form_data.get(key, [default])
            return values[0] if values else default
        return default