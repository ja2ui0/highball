#!/usr/bin/env python3
"""
Configuration manager for backup system
Handles loading/saving YAML config files
"""
import os
import yaml
import glob
from dotenv import dotenv_values
class BackupConfig:
    """Manages the backup configuration in YAML format"""
    
    def __init__(self, config_file="/config/local/local.yaml"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load config from new hierarchy: global settings + individual job files + secrets"""
        try:
            # Load global settings from /config/local/local.yaml
            global_settings = self._load_global_settings()
            
            # Load active jobs from /config/local/jobs/*.yaml
            backup_jobs = self._load_backup_jobs()
            
            # Load deleted jobs from /config/local/jobs/deleted/*.yaml  
            deleted_jobs = self._load_deleted_jobs()
            
            # Load SSH origins from /config/local/origins/*.yaml
            ssh_origins = self._load_ssh_origins()
            
            return {
                'global_settings': global_settings,
                'backup_jobs': backup_jobs,
                'deleted_jobs': deleted_jobs,
                'ssh_origins': ssh_origins
            }
            
        except Exception as e:
            # Handle any errors by falling back to defaults
            self._backup_malformed_config(f"Config hierarchy loading error: {str(e)}")
            return self._get_default_config()
    
    def _load_global_settings(self):
        """Load global settings from /config/local/local.yaml"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    content = f.read().strip()
                    
                if not content:
                    return self._get_default_config()['global_settings']
                    
                settings = yaml.safe_load(content)
                
                if settings is None or not isinstance(settings, dict):
                    return self._get_default_config()['global_settings']
                
                # Load user-specific secrets from /config/local/secrets/local.env
                secrets_file = "/config/local/secrets/local.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    settings = self._merge_secrets(settings, secrets)
                
                return settings
                
            except Exception as e:
                print(f"Warning: Error loading global settings: {str(e)}")
                return self._get_default_config()['global_settings']
        else:
            return self._get_default_config()['global_settings']
    
    def _load_backup_jobs(self):
        """Load active jobs from /config/local/jobs/*.yaml with job-scoped secrets"""
        jobs = {}
        jobs_dir = "/config/local/jobs"
        
        if not os.path.exists(jobs_dir):
            return jobs
            
        # Find all .yaml files in jobs directory (not in deleted subdirectory)
        job_files = glob.glob(os.path.join(jobs_dir, "*.yaml"))
        
        for job_file in job_files:
            job_name = os.path.splitext(os.path.basename(job_file))[0]
            
            try:
                # Load job config
                with open(job_file, 'r') as f:
                    job_config = yaml.safe_load(f.read())
                
                if job_config is None:
                    print(f"Warning: Empty job config for {job_name}")
                    continue
                
                # Load job-specific secrets if they exist (scoped per job)
                secrets_file = f"/config/local/secrets/jobs/{job_name}.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    job_config = self._merge_secrets(job_config, secrets)
                
                jobs[job_name] = job_config
                
            except Exception as e:
                print(f"Warning: Error loading job {job_name}: {str(e)}")
                continue
        
        return jobs
    
    def _load_deleted_jobs(self):
        """Load deleted jobs from /config/local/jobs/deleted/*.yaml with job-scoped secrets"""
        deleted_jobs = {}
        deleted_dir = "/config/local/jobs/deleted"
        
        if not os.path.exists(deleted_dir):
            return deleted_jobs
            
        # Find all .yaml files in deleted directory
        job_files = glob.glob(os.path.join(deleted_dir, "*.yaml"))
        
        for job_file in job_files:
            job_name = os.path.splitext(os.path.basename(job_file))[0]
            
            try:
                # Load deleted job config
                with open(job_file, 'r') as f:
                    job_config = yaml.safe_load(f.read())
                
                if job_config is None:
                    print(f"Warning: Empty deleted job config for {job_name}")
                    continue
                
                # Load deleted job secrets if they exist (scoped per deleted job)
                secrets_file = f"/config/local/secrets/jobs/deleted/{job_name}.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    job_config = self._merge_secrets(job_config, secrets)
                
                deleted_jobs[job_name] = job_config
                
            except Exception as e:
                print(f"Warning: Error loading deleted job {job_name}: {str(e)}")
                continue
        
        return deleted_jobs
    
    def _load_ssh_origins(self):
        """Load SSH origins from /config/local/origins/*.yaml with origin-scoped secrets"""
        origins = {}
        origins_dir = "/config/local/origins"
        
        if not os.path.exists(origins_dir):
            return origins
            
        # Find all .yaml files in origins directory
        origin_files = glob.glob(os.path.join(origins_dir, "*.yaml"))
        
        for origin_file in origin_files:
            origin_name = os.path.splitext(os.path.basename(origin_file))[0]
            
            try:
                # Load origin config
                with open(origin_file, 'r') as f:
                    origin_config = yaml.safe_load(f.read())
                
                if origin_config is None:
                    print(f"Warning: Empty origin config for {origin_name}")
                    continue
                
                # Load origin-specific secrets if they exist (scoped per origin)
                secrets_file = f"/config/local/secrets/origins/{origin_name}.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    origin_config = self._merge_secrets(origin_config, secrets)
                
                origins[origin_name] = origin_config
                
            except Exception as e:
                print(f"Warning: Error loading origin {origin_name}: {str(e)}")
                continue
        
        return origins
    
    def _merge_secrets(self, config, secrets):
        """Merge secrets into config by replacing ${VAR} placeholders - maintains job isolation"""
        def replace_vars(obj):
            if isinstance(obj, str):
                # Replace ${VAR} patterns with actual values from job-specific secrets
                for key, value in secrets.items():
                    obj = obj.replace(f"${{{key}}}", value)
                return obj
            elif isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(item) for item in obj]
            else:
                return obj
        
        return replace_vars(config)
    
    def _get_secret_fields_from_schemas(self, job_config):
        """Discover ALL secret fields from ALL schemas based on job configuration"""
        from models.schemas import DESTINATION_TYPE_SCHEMAS, RESTIC_REPOSITORY_TYPE_SCHEMAS, SOURCE_TYPE_SCHEMAS
        from models.notifications import PROVIDER_FIELD_SCHEMAS
        
        secret_fields = {}
        
        # Helper function to extract secrets from any schema structure
        def extract_secrets_from_schema_fields(fields):
            if isinstance(fields, dict):
                # DESTINATION_TYPE_SCHEMAS format: {'field_name': {'config_key': 'key', 'secret': True, 'env_var': 'VAR'}}
                for field_name, field_config in fields.items():
                    if field_config.get('secret') and field_config.get('env_var'):
                        secret_fields[field_name] = field_config['env_var']
            elif isinstance(fields, list):
                # RESTIC_REPOSITORY_TYPE_SCHEMAS format: [{'name': 'field', 'secret': True, 'env_var': 'VAR'}]
                for field_def in fields:
                    if field_def.get('secret') and field_def.get('env_var'):
                        secret_fields[field_def['name']] = field_def['env_var']
        
        # Check source type schema
        source_type = job_config.get('source_type')
        if source_type and source_type in SOURCE_TYPE_SCHEMAS:
            source_schema = SOURCE_TYPE_SCHEMAS[source_type]
            if 'fields' in source_schema:
                extract_secrets_from_schema_fields(source_schema['fields'])
        
        # Check destination type schema
        dest_type = job_config.get('dest_type')
        if dest_type and dest_type in DESTINATION_TYPE_SCHEMAS:
            dest_schema = DESTINATION_TYPE_SCHEMAS[dest_type]
            if 'fields' in dest_schema:
                extract_secrets_from_schema_fields(dest_schema['fields'])
        
        # Check restic repository type schema
        dest_config = job_config.get('dest_config', {})
        repo_type = dest_config.get('repo_type')
        if repo_type and repo_type in RESTIC_REPOSITORY_TYPE_SCHEMAS:
            repo_schema = RESTIC_REPOSITORY_TYPE_SCHEMAS[repo_type]
            if 'fields' in repo_schema:
                extract_secrets_from_schema_fields(repo_schema['fields'])
        
        # Check notification provider schemas
        notifications = job_config.get('notifications', [])
        for notification in notifications:
            if isinstance(notification, dict):
                provider = notification.get('provider')
                if provider and provider in PROVIDER_FIELD_SCHEMAS:
                    provider_schema = PROVIDER_FIELD_SCHEMAS[provider]
                    if 'fields' in provider_schema:
                        extract_secrets_from_schema_fields(provider_schema['fields'])
        
        return secret_fields
    
    def _extract_secrets_from_job_config(self, job_config):
        """Extract secrets from job config based on schemas, replace with placeholders"""
        # Get schema-driven secret field mappings
        secret_fields = self._get_secret_fields_from_schemas(job_config)
        
        clean_config = {}
        secrets = {}
        
        def extract_from_dict(source_dict, target_dict):
            for key, value in source_dict.items():
                if key in secret_fields and value:
                    # Replace secret with placeholder in config
                    env_var = secret_fields[key]
                    target_dict[key] = f"${{{env_var}}}"
                    # Store actual value in secrets
                    secrets[env_var] = value
                elif isinstance(value, dict):
                    # Recursively process nested dictionaries
                    target_dict[key] = {}
                    extract_from_dict(value, target_dict[key])
                else:
                    # Copy non-secret values as-is
                    target_dict[key] = value
        
        extract_from_dict(job_config, clean_config)
        return clean_config, secrets
    
    def _write_job_files_atomically(self, job_name, clean_config, secrets):
        """Write job config and secrets files atomically"""
        import tempfile
        import shutil
        
        jobs_dir = "/config/local/jobs"
        secrets_dir = "/config/local/secrets/jobs"
        
        # Prepare file paths
        config_file = os.path.join(jobs_dir, f"{job_name}.yaml")
        secrets_file = os.path.join(secrets_dir, f"{job_name}.env")
        
        # Write config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_config:
            yaml.dump(clean_config, temp_config, default_flow_style=False, indent=2)
            temp_config_path = temp_config.name
        
        try:
            # Atomic move for config
            shutil.move(temp_config_path, config_file)
            
            # Only create .env file if secrets exist
            if secrets:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_secrets:
                    for key, value in secrets.items():
                        temp_secrets.write(f'{key}="{value}"\n')
                    temp_secrets_path = temp_secrets.name
                
                # Atomic move for secrets
                shutil.move(temp_secrets_path, secrets_file)
            else:
                # Remove secrets file if no secrets (job changed from having secrets to not)
                if os.path.exists(secrets_file):
                    os.remove(secrets_file)
                    
        except Exception as e:
            # Cleanup on failure
            for temp_path in [temp_config_path, temp_secrets_path if secrets else None]:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            raise e
    
    def _backup_malformed_config(self, error_reason):
        """Backup malformed config file and log the issue"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.config_file}.malformed.{timestamp}"
        
        try:
            # Copy the malformed file to backup location
            import shutil
            shutil.copy2(self.config_file, backup_path)
            
            # Log the issue (this will be visible in application logs)
            print(f"WARNING: Malformed config detected - {error_reason}")
            print(f"WARNING: Backed up malformed config to: {backup_path}")
            print(f"WARNING: Using default configuration. Check the backup file and repair if needed.")
            
            # Store the warning in memory so the web interface can show it
            self._config_warning = {
                'message': f"Malformed config detected: {error_reason}",
                'backup_path': backup_path,
                'timestamp': timestamp
            }
            
        except Exception as backup_error:
            print(f"ERROR: Could not backup malformed config: {str(backup_error)}")
            # Still use defaults even if backup fails
    
    def get_config_warning(self):
        """Get any config loading warnings for display in web interface"""
        return getattr(self, '_config_warning', None)
    
    def clear_config_warning(self):
        """Clear the config warning (after user acknowledges it)"""
        if hasattr(self, '_config_warning'):
            delattr(self, '_config_warning')
    
    def _get_default_config(self):
        """Return default configuration structure"""
        return {
            "global_settings": {
                "scheduler_timezone": "UTC",
                "theme": "dark",  # default theme (dark, light, gruvbox, etc.)
                "default_schedule_times": {
                    "hourly": "0 * * * *",     # top of every hour
                    "daily": "0 3 * * *",      # 3am daily
                    "weekly": "0 3 * * 0",     # 3am Sundays
                    "monthly": "0 3 1 * *"     # 3am first of month
                },
                "enable_conflict_avoidance": True,  # wait for conflicting jobs before running
                "conflict_check_interval": 300,     # seconds between conflict checks (5 minutes)
                "delay_notification_threshold": 300,  # seconds delay before sending notification (5 minutes)
                "notification": {
                    "telegram": {
                        "enabled": False,          # enable/disable telegram notifications globally
                        "token": "",               # Bot token from @BotFather
                        "chat_id": ""              # Chat ID for notifications
                    },
                    "email": {
                        "enabled": False,          # enable/disable email notifications globally
                        "smtp_server": "",         # e.g. smtp.gmail.com
                        "smtp_port": 587,          # 587 for TLS, 465 for SSL, 25 for plain
                        "use_tls": True,           # use TLS encryption
                        "use_ssl": False,          # use SSL encryption (alternative to TLS)
                        "from_email": "",          # sender email address
                        "to_email": "",            # recipient email address  
                        "username": "",            # SMTP authentication username
                        "password": ""             # SMTP authentication password
                    }
                },
                "maintenance": {
                    "discard_schedule": "0 3 * * *",         # daily at 3am - combines forget+prune operations
                    "check_schedule": "0 2 * * 0",           # weekly Sunday 2am (staggered from backups)
                    "retention_policy": {
                        "keep_last": 7,        # always keep last 7 snapshots regardless of age
                        "keep_hourly": 6,      # keep 6 most recent hourly snapshots (6 hours coverage)
                        "keep_daily": 7,       # keep 7 most recent daily snapshots (1 week coverage)
                        "keep_weekly": 4,      # keep 4 most recent weekly snapshots (1 month coverage)
                        "keep_monthly": 6,     # keep 6 most recent monthly snapshots (6 months coverage)
                        "keep_yearly": 0       # disable yearly retention by default
                    },
                    "check_config": {
                        "read_data_subset": "5%"   # balance integrity vs performance
                    }
                }
            },
            "backup_jobs": {}  # Jobs now loaded from file hierarchy
        }
    
    def save_config(self, config=None):
        """Save config to YAML file"""
        if config:
            self.config = config
        
        # Ensure directory exists
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
    
    def get_backup_jobs(self):
        """Get all backup jobs"""
        return self.config.get('backup_jobs', {})
    
    def get_backup_job(self, job_name):
        """Get specific backup job"""
        return self.config.get('backup_jobs', {}).get(job_name)
    
    def add_backup_job(self, job_name, job_config):
        """Add or update a backup job using new file hierarchy"""
        return self.save_job(job_name, job_config)
    
    def save_job(self, job_name, job_config):
        """Save a backup job: config with ${placeholders}, .env with secrets (only if secrets exist)"""
        try:
            # Ensure directories exist
            jobs_dir = "/config/local/jobs"
            secrets_dir = "/config/local/secrets/jobs"
            os.makedirs(jobs_dir, exist_ok=True)
            os.makedirs(secrets_dir, exist_ok=True)
            
            # Extract secrets from job config based on schema
            clean_config, secrets = self._extract_secrets_from_job_config(job_config)
            
            # Write files atomically (only creates .env if secrets dict has content)
            self._write_job_files_atomically(job_name, clean_config, secrets)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error saving job {job_name}: {str(e)}")
            return False
    
    def delete_backup_job(self, job_name):
        """Delete a backup job (move files to deleted/ subdirectories)"""
        try:
            # Check if job exists
            if job_name not in self.config.get('backup_jobs', {}):
                return False
            
            # Ensure deleted directories exist
            deleted_jobs_dir = "/config/local/jobs/deleted"
            deleted_secrets_dir = "/config/local/secrets/jobs/deleted"
            os.makedirs(deleted_jobs_dir, exist_ok=True)
            os.makedirs(deleted_secrets_dir, exist_ok=True)
            
            # File paths
            config_file = f"/config/local/jobs/{job_name}.yaml"
            secrets_file = f"/config/local/secrets/jobs/{job_name}.env"
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"
            deleted_secrets_file = f"/config/local/secrets/jobs/deleted/{job_name}.env"
            
            # Add deleted_on timestamp to job config
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    job_config = yaml.safe_load(f.read())
                
                from datetime import datetime
                job_config['deleted_on'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Write updated config to deleted location
                with open(deleted_config_file, 'w') as f:
                    yaml.dump(job_config, f, default_flow_style=False, indent=2)
                
                # Remove original config file
                os.remove(config_file)
            
            # Move secrets file if it exists
            if os.path.exists(secrets_file):
                import shutil
                shutil.move(secrets_file, deleted_secrets_file)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error deleting job {job_name}: {str(e)}")
            return False
    
    def restore_deleted_job(self, job_name):
        """Restore a deleted job (move files back from deleted/ subdirectories)"""
        try:
            # Check if deleted job exists
            if job_name not in self.config.get('deleted_jobs', {}):
                return False
            
            # Check if job name conflicts with existing active job
            if job_name in self.config.get('backup_jobs', {}):
                print(f"Error: Job name '{job_name}' already exists in active jobs")
                return False
            
            # File paths
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"
            deleted_secrets_file = f"/config/local/secrets/jobs/deleted/{job_name}.env"
            config_file = f"/config/local/jobs/{job_name}.yaml"
            secrets_file = f"/config/local/secrets/jobs/{job_name}.env"
            
            # Restore config file
            if os.path.exists(deleted_config_file):
                with open(deleted_config_file, 'r') as f:
                    job_config = yaml.safe_load(f.read())
                
                # Remove deleted_on timestamp
                if 'deleted_on' in job_config:
                    del job_config['deleted_on']
                
                # Write restored config to active location
                with open(config_file, 'w') as f:
                    yaml.dump(job_config, f, default_flow_style=False, indent=2)
                
                # Remove from deleted location
                os.remove(deleted_config_file)
            
            # Restore secrets file if it exists
            if os.path.exists(deleted_secrets_file):
                import shutil
                shutil.move(deleted_secrets_file, secrets_file)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error restoring job {job_name}: {str(e)}")
            return False
    
    def get_global_settings(self):
        """Get global settings"""
        return self.config.get('global_settings', {})
    
    def update_global_settings(self, settings):
        """Update global settings"""
        if 'global_settings' not in self.config:
            self.config['global_settings'] = {}
        self.config['global_settings'].update(settings)
        self.save_config()
    
    def purge_job(self, job_name):
        """Permanently delete a job from deleted/ directories (irreversible)"""
        try:
            # Check if deleted job exists
            if job_name not in self.config.get('deleted_jobs', {}):
                return False
            
            # File paths for deleted job
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"
            deleted_secrets_file = f"/config/local/secrets/jobs/deleted/{job_name}.env"
            
            # Remove config file
            if os.path.exists(deleted_config_file):
                os.remove(deleted_config_file)
            
            # Remove secrets file
            if os.path.exists(deleted_secrets_file):
                os.remove(deleted_secrets_file)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error purging job {job_name}: {str(e)}")
            return False
    
    # =============================================================================
    # SSH ORIGIN MANAGEMENT METHODS
    # =============================================================================
    
    def get_ssh_origins(self):
        """Get all SSH origins"""
        return self.config.get('ssh_origins', {})
    
    def get_ssh_origin(self, origin_name):
        """Get specific SSH origin"""
        return self.config.get('ssh_origins', {}).get(origin_name)
    
    def save_origin(self, origin_name, origin_config):
        """Save an SSH origin: config with ${placeholders}, .env with secrets (only if secrets exist)"""
        try:
            # Ensure directories exist
            origins_dir = "/config/local/origins"
            secrets_dir = "/config/local/secrets/origins"
            os.makedirs(origins_dir, exist_ok=True)
            os.makedirs(secrets_dir, exist_ok=True)
            
            # Extract secrets from origin config for user-managed keys
            clean_config, secrets = self._extract_secrets_from_origin_config(origin_config)
            
            # Write files atomically (only creates .env if secrets dict has content)
            self._write_origin_files_atomically(origin_name, clean_config, secrets)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error saving origin {origin_name}: {str(e)}")
            return False
    
    def delete_origin(self, origin_name):
        """Delete an SSH origin permanently"""
        try:
            # Check if origin exists
            if origin_name not in self.config.get('ssh_origins', {}):
                return False
            
            # File paths
            config_file = f"/config/local/origins/{origin_name}.yaml"
            secrets_file = f"/config/local/secrets/origins/{origin_name}.env"
            
            # Remove config file
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Remove secrets file if it exists
            if os.path.exists(secrets_file):
                os.remove(secrets_file)
            
            # Reload config to reflect changes
            self.config = self.load_config()
            
            return True
            
        except Exception as e:
            print(f"Error deleting origin {origin_name}: {str(e)}")
            return False
    
    def _extract_secrets_from_origin_config(self, origin_config):
        """Extract secrets from origin config for user-managed keys only"""
        clean_config = origin_config.copy()
        secrets = {}
        
        # Only extract secrets if using user-managed keys (ssh_highball = false)
        if not origin_config.get('ssh_highball', True):
            # Extract SSH_PUBKEY if provided
            ssh_pubkey = origin_config.get('ssh_pubkey', '')
            if ssh_pubkey and ssh_pubkey != '${SSH_PUBKEY}':
                secrets['SSH_PUBKEY'] = ssh_pubkey
                clean_config['ssh_pubkey'] = '${SSH_PUBKEY}'
            
            # Extract SSH_PASSPHRASE if provided
            ssh_passphrase = origin_config.get('ssh_passphrase', '')
            if ssh_passphrase and ssh_passphrase != '${SSH_PASSPHRASE}':
                secrets['SSH_PASSPHRASE'] = ssh_passphrase
                clean_config['ssh_passphrase'] = '${SSH_PASSPHRASE}'
        
        # Remove fields that shouldn't be stored in YAML
        if 'origin_name' in clean_config:
            del clean_config['origin_name']  # Derived from filename, not stored
        if 'ssh_password' in clean_config:
            del clean_config['ssh_password']  # Transient field, not stored
        
        return clean_config, secrets
    
    def _write_origin_files_atomically(self, origin_name, clean_config, secrets):
        """Write origin config and secrets files atomically"""
        import tempfile
        import shutil
        
        # Write config file
        config_file = f"/config/local/origins/{origin_name}.yaml"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as temp_config:
            yaml.dump(clean_config, temp_config, default_flow_style=False, indent=2)
            temp_config_path = temp_config.name
        
        # Atomically move config file into place
        shutil.move(temp_config_path, config_file)
        
        # Write secrets file only if there are secrets to write
        secrets_file = f"/config/local/secrets/origins/{origin_name}.env"
        if secrets:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as temp_secrets:
                for key, value in secrets.items():
                    temp_secrets.write(f'{key}="{value}"\n')
                temp_secrets_path = temp_secrets.name
            
            # Atomically move secrets file into place
            shutil.move(temp_secrets_path, secrets_file)
        else:
            # Remove secrets file if no secrets (e.g., switching from user keys to Highball keys)
            if os.path.exists(secrets_file):
                os.remove(secrets_file)
