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
        """Validate Restic job configuration"""
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