#!/usr/bin/env python3
"""
Admin Services - System Initialization

Centralized system initialization and service container for Highball.
Manages SSH keypair setup, scheduler bootstrapping, and handler initialization.
"""
import os
import subprocess
import stat
from typing import Dict, Any, Optional

from handlers.operations import OperationsHandler
from handlers.api import APIHandler
from jobs.services.scheduler import JobSchedulerHandler
from services.template import TemplateService
from jobs.services.schedule import SchedulingService
from services.data_services import JobFormDataBuilder
from config import BackupConfig


class HighballServices:
    """Container for shared application services"""
    
    def __init__(self):
        self.backup_config = None
        self.template_service = None
        self.scheduler_service = None
        self.handlers = None
        self.job_form_builder = None
    
    def initialize(self):
        """Initialize all services once at startup"""
        if self.backup_config is not None:
            return  # Already initialized
            
        # Core services
        config_path = os.environ.get('CONFIG_PATH', '/config/local/local.yaml')
        self.backup_config = BackupConfig(config_path)
        self.template_service = TemplateService(self.backup_config)
        self.scheduler_service = SchedulingService()
        self.job_form_builder = JobFormDataBuilder()

        # Initialize SSH keypair for Highball-managed origins (do not bring down UI if this fails)
        try:
            self._ensure_highball_ssh_keypair()
            print("Highball SSH keypair verified/created")
        except Exception as e:
            print(f"[SSH_KEYS] Warning: SSH key generation failed: {e}")

        # Register schedules (do not bring down UI if this fails)
        try:
            count = self.scheduler_service.bootstrap_schedules(self.backup_config)
            print(f"Scheduled {count} backup job(s) from config.")
        except Exception as e:
            print(f"[SCHEDULER] disabled at startup: {e}")

        # Initialize handlers
        self.handlers = {
            'operations': OperationsHandler(self.backup_config, self.template_service),
            'api': APIHandler(self.backup_config, self.template_service),
            'job_scheduler': JobSchedulerHandler(self.scheduler_service),
        }
    
    def _ensure_highball_ssh_keypair(self):
        """Ensure Highball SSH keypair exists, generate if needed"""
        ssh_dir = "/config/local/secrets/.ssh"
        private_key_path = os.path.join(ssh_dir, "id_highball")
        public_key_path = os.path.join(ssh_dir, "id_highball.pub")
        
        # Check if keypair already exists
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            # Verify permissions on existing key
            try:
                os.chmod(private_key_path, 0o600)
                os.chmod(public_key_path, 0o644)
            except Exception as e:
                print(f"Warning: Could not set SSH key permissions: {e}")
            return
        
        # Create SSH directory if it doesn't exist
        os.makedirs(ssh_dir, exist_ok=True)
        
        # Generate keypair without passphrase for non-interactive use
        print("Generating Highball SSH keypair...")
        cmd = [
            'ssh-keygen', 
            '-t', 'rsa',
            '-b', '2048',
            '-f', private_key_path,
            '-N', '',  # No passphrase
            '-C', 'HIGHBALL@HIGHBALL',
            '-q'  # Quiet mode
        ]
        
        # Run ssh-keygen
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(f"ssh-keygen failed: {result.stderr}")
        
        # Set proper permissions
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        # Create known_hosts file for host key acceptance
        known_hosts_path = os.path.join(ssh_dir, "known_hosts")
        if not os.path.exists(known_hosts_path):
            with open(known_hosts_path, 'w') as f:
                f.write("# SSH known hosts for Highball\n")
            os.chmod(known_hosts_path, 0o644)