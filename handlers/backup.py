"""
Backup execution handler
Handles running backup jobs (dry-run and real)
"""
import subprocess
from datetime import datetime
from services.template_service import TemplateService
class BackupHandler:
    """Handles backup job execution"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def run_backup_job(self, handler, job_name, dry_run=True, source="manual"):
        """Execute backup job with specified mode"""
        if job_name not in self.backup_config.config['backup_jobs']:
            TemplateService.send_error_response(handler, f"Job '{job_name}' not found")
            return
        
        job_config = self.backup_config.config['backup_jobs'][job_name]
        global_settings = self.backup_config.config.get('global_settings', {})
        
        # Execute backup
        try:
            result = self._execute_rsync(job_name, job_config, global_settings, dry_run, source)
            
            # Log result
            if dry_run:
                status = 'completed-dry-run' if result['success'] else 'error-dry-run'
                message = f'Dry run completed with return code {result["return_code"]} (triggered by {source})'
            else:
                status = 'completed' if result['success'] else 'error'
                message = f'Backup completed with return code {result["return_code"]}'
            
            self.backup_config.log_backup_run(job_name, status, message)
            
        except Exception as e:
            self.backup_config.log_backup_run(job_name, 'error', str(e))
        
        # Redirect back to dashboard
        TemplateService.send_redirect(handler, '/')
    
    def _execute_rsync(self, job_name, job_config, global_settings, dry_run, source):
        """Execute rsync command and log output"""
        timestamp = datetime.now().isoformat()
        mode_text = "DRY RUN" if dry_run else "REAL BACKUP"
        
        # Build rsync command
        rsync_cmd = self._build_rsync_command(job_config, global_settings, job_name, dry_run)
        
        # Prepare log content
        log_content = self._build_log_header(job_name, timestamp, mode_text, source, rsync_cmd, job_config)
        
        # Execute command
        try:
            result = subprocess.run(
                rsync_cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            
            # Add output to log
            log_content += f"\nSTDOUT:\n{result.stdout}\n"
            log_content += f"\nSTDERR:\n{result.stderr}\n"
            log_content += f"\nRETURN CODE: {result.returncode}\n"
            
            success = result.returncode == 0
            
        except subprocess.TimeoutExpired:
            log_content += f"\nERROR: {mode_text} timed out after 5 minutes\n"
            success = False
            result = type('Result', (), {'returncode': -1})()
            
        except Exception as e:
            log_content += f"\nERROR: {str(e)}\n"
            success = False
            result = type('Result', (), {'returncode': -1})()
        
        # Write to log file
        log_file = "/tmp/backup-dry-run.log" if dry_run else f"/tmp/backup-{job_name}.log"
        try:
            with open(log_file, 'a') as f:
                f.write(log_content)
        except Exception:
            pass  # Don't fail backup if logging fails
        
        return {
            'success': success,
            'return_code': result.returncode,
            'log_content': log_content
        }
    
    def _build_rsync_command(self, job_config, global_settings, job_name, dry_run):
        """Build rsync command with all options using new job structure"""
        rsync_cmd = [global_settings.get('rsync_path', '/usr/bin/rsync'), '-a']
        
        if dry_run:
            rsync_cmd.extend(['--dry-run', '--verbose'])
        
        rsync_cmd.extend([
            '--info=stats1',
            '--delete',
            '--delete-excluded'
        ])
        
        # Add include patterns
        for include in job_config.get('includes', []):
            rsync_cmd.extend(['--include', include])
        
        # Add exclude patterns
        for exclude in job_config.get('excludes', []):
            rsync_cmd.extend(['--exclude', exclude])
        
        # Determine source and destination from new structure
        source = self._build_source_path(job_config)
        dest = self._build_destination_path(job_config, job_name, global_settings)
        
        rsync_cmd.extend([source, dest])
        
        return rsync_cmd
    
    def _build_source_path(self, job_config):
        """Build source path from job configuration"""
        # Check for new structure first
        if 'source_type' in job_config:
            source_config = job_config.get('source_config', {})
            return source_config.get('source_string', '')
        
        # Fall back to legacy structure
        return job_config.get('source', '')
    
    def _build_destination_path(self, job_config, job_name, global_settings):
        """Build destination path from job configuration"""
        # Check for new structure first
        if 'dest_type' in job_config:
            dest_type = job_config['dest_type']
            dest_config = job_config.get('dest_config', {})
            
            if dest_type == 'local':
                return dest_config.get('path', f'/backups/{job_name}')
            elif dest_type == 'ssh':
                return dest_config.get('dest_string', f"backup@localhost:/backups/{job_name}")
            elif dest_type == 'rsyncd':
                return dest_config.get('dest_string', f"rsync://localhost/{job_name}")
        
        # Fall back to legacy structure (rsync daemon to configured host)
        dest_host = global_settings.get('dest_host', '192.168.1.252')
        return f"{dest_host}::{job_name}"
    
    def _build_log_header(self, job_name, timestamp, mode_text, source, rsync_cmd, job_config):
        """Build log header with job details"""
        return f"""
========================================
Backup Job: {job_name} ({mode_text})
Time: {timestamp}
Triggered by: {source}
========================================
COMMAND EXECUTED:
{' '.join(rsync_cmd)}
SOURCE: {job_config['source']}
DESTINATION: {job_config['source']} -> {job_name}
INCLUDES: {job_config.get('includes', [])}
EXCLUDES: {job_config.get('excludes', [])}
========================================
{mode_text} OUTPUT:
"""
