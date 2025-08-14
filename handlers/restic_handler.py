"""
Restic backup handler
Handles Restic backup job management and execution planning
"""
from handlers.restic_validator import ResticValidator
from services.restic_runner import ResticRunner
from services.template_service import TemplateService
from services.job_logger import JobLogger


class ResticHandler:
    """Handles Restic backup operations with command planning"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.restic_runner = ResticRunner()
        self.job_logger = JobLogger()
    
    def plan_backup(self, handler, job_name):
        """Plan Restic backup execution (returns 202 with plan, does not execute)"""
        try:
            # Get job configuration
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            # Validate it's a Restic job
            if job_config.get('dest_type') != 'restic':
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} is not a Restic backup job'
                }, status_code=400)
                return
            
            # Add job name to config for planning
            job_config_with_name = {**job_config, 'name': job_name}
            
            # Generate execution plan
            plan = self.restic_runner.plan_backup_job(job_config_with_name)
            
            # Log planning event
            self.job_logger.log_job_execution(
                job_name, 
                f"Restic backup plan generated: {len(plan.commands)} commands, estimated {plan.estimated_duration_minutes}min", 
                "INFO"
            )
            
            # Return 202 with structured plan (no execution)
            TemplateService.send_json_response(handler, {
                'status': 'planned',
                'message': f'Backup plan generated for {job_name}',
                'plan': plan.to_dict(),
                'execution_status': 'not_executed',
                'note': 'This is a planning-only response. Actual execution not implemented.'
            }, status_code=202)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Planning failed: {str(e)}'
            }, status_code=500)
    
    def validate_restic_job(self, handler, job_name):
        """Validate existing Restic job configuration"""
        try:
            # Get job configuration
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            # Validate job configuration
            result = ResticValidator.validate_restic_destination(job_config)
            
            # Log validation event
            if result.get('success'):
                self.job_logger.log_job_execution(job_name, f"Restic configuration validated: {result.get('message')}", "INFO")
            else:
                self.job_logger.log_job_execution(job_name, f"Restic validation failed: {result.get('message')}", "ERROR")
            
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Validation failed: {str(e)}'
            }, status_code=500)

    def validate_restic_form(self, handler, form_data):
        """Validate Restic configuration from form data (for job creation)"""
        try:
            from handlers.restic_form_parser import ResticFormParser
            
            # Debug: Log what we received
            print(f"DEBUG: Received form data keys: {list(form_data.keys())}")
            print(f"DEBUG: restic_repo_type: {form_data.get('restic_repo_type')}")
            print(f"DEBUG: restic_password exists: {'restic_password' in form_data}")
            
            # Parse Restic destination from form data
            restic_result = ResticFormParser.parse_restic_destination(form_data)
            
            if not restic_result.get('valid'):
                TemplateService.send_json_response(handler, {
                    'success': False,
                    'message': restic_result.get('error', 'Invalid Restic configuration')
                })
                return
            
            dest_config = restic_result['config']
            
            # Create mock job config for validation
            mock_job_config = {
                'dest_type': 'restic',
                'dest_config': dest_config,
                'source_config': self._parse_source_from_form(form_data)
            }
            
            # Validate with mock job config
            result = ResticValidator.validate_restic_destination(mock_job_config)
            
            # Add form-specific context
            result['details'] = result.get('details', {})
            result['details']['repo_uri'] = dest_config.get('repo_uri', 'Unknown')
            result['details']['repo_type'] = dest_config.get('repo_type', 'Unknown')
            
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'success': False,
                'error': f'Form validation failed: {str(e)}'
            })

    def _parse_source_from_form(self, form_data):
        """Parse source configuration from form data for validation context"""
        source_type = form_data.get('source_type', [''])[0]
        
        if source_type == 'ssh':
            return {
                'hostname': form_data.get('source_ssh_hostname', [''])[0],
                'username': form_data.get('source_ssh_username', [''])[0],
                'path': form_data.get('source_ssh_path', [''])[0]
            }
        elif source_type == 'local':
            return {
                'path': form_data.get('source_local_path', [''])[0]
            }
        else:
            return {}
    
    def check_restic_binary(self, handler, job_name):
        """Check if restic binary is available on source system"""
        try:
            # Get job configuration
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            # Check binary availability
            source_config = job_config.get('source_config', {})
            result = ResticValidator.check_restic_binary(source_config)
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Binary check failed: {str(e)}'
            }, status_code=500)
    
    def get_repository_info(self, handler, job_name):
        """Get repository information for Restic job"""
        try:
            # Get job configuration
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            # Validate it's a Restic job
            if job_config.get('dest_type') != 'restic':
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} is not a Restic backup job'
                }, status_code=400)
                return
            
            # Build repository info
            dest_config = job_config.get('dest_config', {})
            repo_url = self.restic_runner._build_repository_url(dest_config)
            
            TemplateService.send_json_response(handler, {
                'job_name': job_name,
                'repository_type': dest_config.get('repo_type', 'unknown'),
                'repository_url': repo_url,
                'auto_init': dest_config.get('auto_init', False),
                'retention_policy': dest_config.get('retention_policy'),
                'tags': dest_config.get('tags', []),
                'exclude_patterns': dest_config.get('exclude_patterns', [])
            })
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Repository info failed: {str(e)}'
            }, status_code=500)
    
    def list_snapshots(self, handler, job_name):
        """List all snapshots for a Restic repository"""
        try:
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            if job_config.get('dest_type') != 'restic':
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} is not a Restic backup job'
                }, status_code=400)
                return
            
            # Use existing ResticValidator patterns to get snapshots
            result = ResticValidator.list_repository_snapshots(job_config)
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Snapshot listing failed: {str(e)}'
            }, status_code=500)
    
    def get_snapshot_stats(self, handler, job_name, snapshot_id):
        """Get detailed statistics for a specific snapshot"""
        try:
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            if job_config.get('dest_type') != 'restic':
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} is not a Restic backup job'
                }, status_code=400)
                return
            
            if not snapshot_id:
                TemplateService.send_json_response(handler, {
                    'error': 'Snapshot ID is required'
                }, status_code=400)
                return
            
            # Get detailed snapshot statistics
            result = ResticValidator.get_snapshot_statistics(job_config, snapshot_id)
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Snapshot statistics failed: {str(e)}'
            }, status_code=500)
    
    def browse_directory(self, handler, job_name, snapshot_id, path):
        """Browse directory contents in a specific snapshot"""
        try:
            job_config = self.backup_config.get_backup_job(job_name)
            if not job_config:
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} not found'
                }, status_code=404)
                return
            
            if job_config.get('dest_type') != 'restic':
                TemplateService.send_json_response(handler, {
                    'error': f'Job {job_name} is not a Restic backup job'
                }, status_code=400)
                return
            
            # Use existing ResticValidator patterns to browse directory
            result = ResticValidator.browse_snapshot_directory(job_config, snapshot_id, path)
            TemplateService.send_json_response(handler, result)
            
        except Exception as e:
            TemplateService.send_json_response(handler, {
                'error': f'Directory browsing failed: {str(e)}'
            }, status_code=500)