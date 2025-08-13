"""
Restic command builder
Handles restic command construction for backup execution
"""
from dataclasses import dataclass
from typing import List
from services.restic_runner import ResticRunner
from .backup_command_builder import CommandInfo


class ResticCommandBuilder:
    """Builds restic commands for backup execution"""

    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.restic_runner = ResticRunner()

    def build_restic_command(self, job_config, job_name, dry_run):
        """
        Build restic command for execution.
        Returns CommandInfo with exec_argv, log_cmd_str, src_display, dst_display.
        """
        # Add job name to config for ResticRunner
        job_config_with_name = {**job_config, 'name': job_name}
        
        # Generate execution plan
        plan = self.restic_runner.plan_backup_job(job_config_with_name)
        
        if not plan.commands:
            raise ValueError(f"No commands generated for Restic job {job_name}")
        
        # Handle multiple commands (init + backup) by chaining them
        if len(plan.commands) > 1:
            # Multiple commands - chain them with && for sequential execution
            exec_argv = self._build_chained_commands(plan.commands, dry_run)
        else:
            # Single command
            primary_command = plan.commands[0]
            if dry_run:
                # Add --dry-run flag to restic args if not already present
                if '--dry-run' not in (primary_command.args or []):
                    primary_command.args = (primary_command.args or []) + ['--dry-run']
            exec_argv = primary_command.to_ssh_command()
        
        # Build display strings
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        
        src_display = self._build_source_display(job_config.get('source_type'), source_config)
        dst_display = self._build_dest_display(dest_config)
        
        # Build log command string (without sensitive info) - use backup command for display
        backup_command = plan.commands[-1] if plan.commands else plan.commands[0]  # Last command is typically backup
        log_cmd_str = self._build_log_command_string(backup_command)
        
        return CommandInfo(
            exec_argv=exec_argv,
            log_cmd_str=log_cmd_str,
            src_display=src_display,
            dst_display=dst_display
        )
    
    def _build_source_display(self, source_type, source_config):
        """Build source display string"""
        if source_type == 'ssh':
            hostname = source_config.get('hostname', 'unknown')
            username = source_config.get('username', 'unknown')
            path = source_config.get('path', 'unknown')
            return f"{username}@{hostname}:{path}"
        elif source_type == 'local':
            return source_config.get('path', 'unknown')
        else:
            return f"{source_type}:unknown"
    
    def _build_dest_display(self, dest_config):
        """Build destination display string"""
        repo_type = dest_config.get('repo_type', 'unknown')
        repo_uri = dest_config.get('repo_uri', 'unknown')
        return f"restic:{repo_type}:{repo_uri}"
    
    def _build_log_command_string(self, command):
        """Build command string for logging (mask sensitive info)"""
        # Start with basic restic command
        cmd_parts = ['restic', '-r', '<repository>']
        
        # Add args if present
        if command.args:
            cmd_parts.extend(command.args)
        
        # Add source paths if present
        if command.source_paths:
            cmd_parts.extend(command.source_paths)
        
        return ' '.join(cmd_parts)
    
    def _build_chained_commands(self, commands, dry_run):
        """Build chained command execution for multiple restic commands"""
        # For multiple commands, we need to chain them properly
        # Since restic commands need to run on the same remote system, we'll chain the restic commands within SSH
        
        if not commands:
            return []
        
        # Apply dry_run to backup commands
        for cmd in commands:
            if dry_run and cmd.command_type.value == 'backup':
                if '--dry-run' not in (cmd.args or []):
                    cmd.args = (cmd.args or []) + ['--dry-run']
        
        # Use the SSH configuration from the first command
        first_command = commands[0]
        if first_command.transport.value != 'ssh':
            # For non-SSH, just return the first command
            return first_command.to_ssh_command()
        
        # Build environment exports (common to all commands)
        env_exports = []
        if first_command.environment_vars:
            for key, value in first_command.environment_vars.items():
                env_exports.append(f"export {key}='{value}'")
        
        # Build individual restic commands
        restic_commands = []
        for cmd in commands:
            restic_cmd = ["restic", "-r", cmd.repository_url]
            if cmd.command_type.value == 'init':
                restic_cmd.append('init')
            elif cmd.command_type.value == 'backup':
                restic_cmd.append('backup')
                if cmd.args:
                    restic_cmd.extend(cmd.args)
                if cmd.source_paths:
                    restic_cmd.extend(cmd.source_paths)
            
            restic_commands.append(' '.join(restic_cmd))
        
        # Chain restic commands with &&
        chained_restic = ' && '.join(restic_commands)
        
        # Combine environment setup and chained restic commands
        remote_command = '; '.join(env_exports + [chained_restic])
        
        # Build SSH command
        ssh_cmd = [
            'ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            f"{first_command.ssh_config['username']}@{first_command.ssh_config['hostname']}",
            remote_command
        ]
        
        return ssh_cmd