"""
Backup command builder
Handles rsync command construction and path building
"""
import subprocess
import shlex
from dataclasses import dataclass
from typing import List


@dataclass
class CommandInfo:
    """Information about built backup command"""
    exec_argv: List[str]
    log_cmd_str: str
    src_display: str
    dst_display: str


class BackupCommandBuilder:
    """Builds rsync commands and paths for backup execution"""

    def __init__(self, backup_config):
        self.backup_config = backup_config

    def build_rsync_command(self, job_config, job_name, dry_run):
        """
        Build the command to execute and display information.
        Returns CommandInfo with exec_argv, log_cmd_str, src_display, dst_display.
        """
        global_settings = self.backup_config.config.get("global_settings", {})
        
        rsync_bin = self._discover_binary_path("rsync", "/usr/bin/rsync")
        ssh_bin = self._discover_binary_path("ssh", "/usr/bin/ssh")

        # Build rsync command with custom or default options
        dest_config = job_config.get('dest_config', {})
        custom_options = dest_config.get('rsync_options', '')
        
        if custom_options:
            # Use custom options - split by spaces and filter empty strings
            rsync_options = [opt for opt in custom_options.split() if opt]
            rsync_cmd = [rsync_bin] + rsync_options
        else:
            # Use default options
            rsync_cmd = [rsync_bin, "-a", "--info=stats1", "--delete", "--delete-excluded"]
        
        # Add dry run options if needed
        if dry_run:
            rsync_cmd.extend(["--dry-run", "--verbose"])

        # Add include/exclude patterns
        for include in job_config.get("includes", []) or []:
            rsync_cmd.extend(["--include", include])
        for exclude in job_config.get("excludes", []) or []:
            rsync_cmd.extend(["--exclude", exclude])

        # Build source and destination paths
        source_str = self._build_source_path(job_config)
        dest_str = self._build_destination_path(job_config, job_name, global_settings)

        # Default local execution argv
        local_rsync_argv = rsync_cmd + [source_str, dest_str]

        # Determine execution context
        execution_info = self._determine_execution_context(job_config, source_str, dest_str)
        
        if execution_info.requires_ssh:
            exec_argv = self._build_ssh_command(
                ssh_bin, execution_info.ssh_target, local_rsync_argv, execution_info.remote_src_path
            )
        else:
            exec_argv = local_rsync_argv

        log_cmd_str = " ".join(shlex.quote(x) for x in exec_argv)
        
        return CommandInfo(
            exec_argv=exec_argv,
            log_cmd_str=log_cmd_str,
            src_display=source_str,
            dst_display=dest_str
        )

    def _build_source_path(self, job_config):
        """
        Build the source path for rsync based on config fields.
        Accepts:
          - source_config.user / source_config.host / source_config.path
          - source_config.username / source_config.hostname / source_config.path
          - or flat source_string
        """
        sc = job_config.get("source_config", {})
        # Allow either `user` or `username`
        user = sc.get("user") or sc.get("username")
        # Allow either `host` or `hostname`
        host = sc.get("host") or sc.get("hostname")
        path = sc.get("path")

        if sc.get("source_string"):
            return sc["source_string"]

        if user and host and path:
            return f"{user}@{host}:{path}"
        elif host and path:
            return f"{host}:{path}"
        elif path:
            return path
        else:
            raise ValueError("Invalid source_config: missing required fields for source path")

    def _build_destination_path(self, job_config, job_name, global_settings):
        """
        Build destination path from job configuration.

        Accepts either legacy or new-style keys:
          - dest_config.dest_string                      (wins if present)
          - dest_type: local | ssh | rsyncd
          - dest_config:
              # local
              path
              # ssh
              user | username, host | hostname, path
              # rsyncd
              host | hostname, share
              # optional knobs
              protocol: 'rsync' | 'daemon'   (daemon => 'host::share')
              double_colon: bool             (forces 'host::share' if True)
        Falls back to global_settings.dest_host using 'host::job_name' for legacy.
        """
        dest_type = job_config.get("dest_type")
        dest_config = job_config.get("dest_config", {}) or {}

        # Absolute override if provided
        if dest_config.get("dest_string"):
            return dest_config["dest_string"]

        # Normalize common fields
        user = dest_config.get("user") or dest_config.get("username")
        host = dest_config.get("host") or dest_config.get("hostname")
        path = dest_config.get("path")
        share = dest_config.get("share") or job_name

        # Modern types
        if dest_type == "local":
            return path or f"/backups/{job_name}"

        if dest_type == "ssh":
            # default path if none given
            dest_path = path or f"/backups/{job_name}"
            if host:
                return f"{user + '@' if user else ''}{host}:{dest_path}"
            # no host means treat as local path
            return dest_path

        if dest_type == "rsyncd":
            # allow either rsync://host/share or host::share (daemon syntax)
            use_double_colon = bool(dest_config.get("double_colon"))
            protocol = (dest_config.get("protocol") or "rsync").lower()

            if host:
                if use_double_colon or protocol == "daemon":
                    return f"{host}::{share}"
                return f"rsync://{host}/{share}"

            # no host provided - destination must be explicitly configured
            raise ValueError(f"rsyncd destination requires explicit hostname for job '{job_name}'")

        # dest_type unspecified - destination must be explicitly configured
        raise ValueError(f"Destination type must be specified for job '{job_name}'")

    def _determine_execution_context(self, job_config, source_str, dest_str):
        """Determine if SSH execution is needed and extract SSH parameters"""
        context = ExecutionContext()
        
        # Structured detection (no regex): rely on validated form fields
        src_type = job_config.get("source_type")
        src_cfg = job_config.get("source_config", {}) or {}
        dst_type = job_config.get("dest_type")
        
        # rsyncd destination is indicated by dest_type or by dest_str shape
        dst_is_rsyncd = (dst_type == "rsyncd") or (
            isinstance(dest_str, str) and (dest_str.startswith("rsync://") or "::" in dest_str)
        )

        # SSH source components from validated config
        src_user = src_cfg.get("user") or src_cfg.get("username")
        src_host = src_cfg.get("host") or src_cfg.get("hostname")
        src_path = src_cfg.get("path")

        # Case: SSH source -> rsync daemon destination
        if (src_type == "ssh") and dst_is_rsyncd:
            if src_user and src_host and src_path:
                context.requires_ssh = True
                context.ssh_target = f"{src_user}@{src_host}"
                context.remote_src_path = src_path
            else:
                # fallback to formatted string if provided by our own builder
                if ":" in source_str:
                    userhost, remote_src_path = source_str.split(":", 1)
                    context.requires_ssh = True
                    context.ssh_target = userhost
                    context.remote_src_path = remote_src_path

        return context

    def _build_ssh_command(self, ssh_bin, ssh_target, local_rsync_argv, remote_src_path):
        """Build SSH command for remote execution"""
        # replace SRC with the remote path for the remote rsync
        remote_rsync_list = local_rsync_argv.copy()  # [..., SRC, DST]
        remote_rsync_list[-2] = remote_src_path
        remote_cmd_str = shlex.join(remote_rsync_list)

        return [ssh_bin, ssh_target, "--", remote_cmd_str]

    def _discover_binary_path(self, binary_name, fallback_path):
        """Discover binary path using 'which' command with fallback"""
        try:
            result = subprocess.run(['which', binary_name], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return fallback_path


@dataclass
class ExecutionContext:
    """Context information for command execution"""
    requires_ssh: bool = False
    ssh_target: str = ""
    remote_src_path: str = ""