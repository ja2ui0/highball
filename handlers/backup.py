"""
Backup execution handler
Handles running backup jobs (dry-run and real) with async execution
"""
import subprocess
from datetime import datetime
import threading
import shlex  # for safe logging/remote command quoting
from services.template_service import TemplateService
from services.job_logger import JobLogger


class BackupHandler:
    """Handles backup job execution"""

    def __init__(self, backup_config, scheduler_service=None):
        self.backup_config = backup_config
        self.scheduler_service = scheduler_service  # not used here yet, but injected safely
        self.job_logger = JobLogger()

    # ---------------------------
    # Public entry points
    # ---------------------------
    def run_backup_job(self, handler, job_name, dry_run=True, source="manual"):
        """
        Kick off a backup job in the background and (if handler is provided) redirect immediately.
        When handler is None (scheduler/CLI), no HTTP responses are sent.
        """
        if job_name not in self.backup_config.config.get("backup_jobs", {}):
            if handler is not None:
                TemplateService.send_error_response(handler, f"Job '{job_name}' not found")
            return

        job_config = self.backup_config.config["backup_jobs"][job_name]
        global_settings = self.backup_config.config.get("global_settings", {})

        # Start background worker
        t = threading.Thread(
            target=self._run_job_background,
            args=(job_name, job_config, global_settings, dry_run, source),
            daemon=True,
        )
        t.start()

        # Optional: write a quick "started" entry so the log exists immediately
        started_msg = (
            "Dry run started" if dry_run else "Backup started"
        ) + f" (triggered by {source})"
        try:
            self.job_logger.log_job_status(job_name, "started", started_msg)
        except Exception:
            pass

        # Only redirect when serving an HTTP request
        if handler is not None:
            TemplateService.send_redirect(handler, "/")

    def run_backup_job_headless(self, job_name, dry_run=True, source="scheduler"):
        """
        Convenience wrapper for scheduler/CLI use (no HTTP handler).
        """
        self.run_backup_job(handler=None, job_name=job_name, dry_run=dry_run, source=source)

    # ---------------------------
    # Background worker
    # ---------------------------
    def _run_job_background(self, job_name, job_config, global_settings, dry_run, trigger_source):
        """
        Runs in a daemon thread: builds command, executes, logs results.
        """
        try:
            result = self._execute_rsync(job_name, job_config, global_settings, dry_run, trigger_source)
            if dry_run:
                status = "completed-dry-run" if result["success"] else "error-dry-run"
                message = f'Dry run completed with return code {result["return_code"]} (triggered by {trigger_source})'
            else:
                status = "completed" if result["success"] else "error"
                message = f'Backup completed with return code {result["return_code"]}'
            self.job_logger.log_job_status(job_name, status, message)
            self.job_logger.log_job_execution(job_name, result["log_content"])
        except Exception as e:
            self.job_logger.log_job_status(job_name, "error", str(e))
            self.job_logger.log_job_execution(job_name, f"ERROR: {str(e)}", "ERROR")

    # ---------------------------
    # Rsync execution
    # ---------------------------
    def _execute_rsync(self, job_name, job_config, global_settings, dry_run, trigger_source):
        """Execute rsync command and log output"""
        timestamp = datetime.now().isoformat()
        mode_text = "DRY RUN" if dry_run else "REAL BACKUP"

        exec_argv, log_cmd_str, src_display, dst_display = self._build_rsync_command(
            job_config, global_settings, job_name, dry_run
        )

        # Prepare log content
        log_content = self._build_log_header(
            job_name=job_name,
            timestamp=timestamp,
            mode_text=mode_text,
            trigger_source=trigger_source,
            log_cmd_str=log_cmd_str,
            src_display=src_display,
            dst_display=dst_display,
            job_config=job_config,
        )

        # Determine timeout policy:
        # - default 300s for dry runs (fast)
        # - unlimited for real backups unless overridden
        dry_default = 300
        timeout_cfg = global_settings.get("rsync_timeout_seconds")
        timeout = timeout_cfg if isinstance(timeout_cfg, (int, float)) else (dry_default if dry_run else None)

        try:
            if timeout is None:
                result = subprocess.run(exec_argv, capture_output=True, text=True)
            else:
                result = subprocess.run(exec_argv, capture_output=True, text=True, timeout=timeout)

            log_content += f"\nSTDOUT:\n{result.stdout}\n"
            log_content += f"\nSTDERR:\n{result.stderr}\n"
            log_content += f"\nRETURN CODE: {result.returncode}\n"
            success = result.returncode == 0

        except subprocess.TimeoutExpired:
            log_content += f"\nERROR: {mode_text} timed out after {timeout} seconds\n"
            success = False
            result = type("Result", (), {"returncode": -1})()

        except Exception as e:
            log_content += f"\nERROR: {str(e)}\n"
            success = False
            result = type("Result", (), {"returncode": -1})()

        # Log detailed execution to job logger
        try:
            self.job_logger.log_job_execution(job_name, log_content)
        except Exception:
            pass

        return {
            "success": success,
            "return_code": result.returncode,
            "log_content": log_content,
        }

    def _build_rsync_command(self, job_config, global_settings, job_name, dry_run):
        """
        Build the command to execute and a pretty log string.
        Returns (exec_argv, log_cmd_str, src_display, dst_display).
        """
        rsync_bin = self._discover_binary_path("rsync", "/usr/bin/rsync")
        ssh_bin = self._discover_binary_path("ssh", "/usr/bin/ssh")

        # Base rsync command + flags
        rsync_cmd = [rsync_bin, "-a"]
        if dry_run:
            rsync_cmd.extend(["--dry-run", "--verbose"])

        rsync_cmd.extend(["--info=stats1", "--delete", "--delete-excluded"])

        # Add include/exclude patterns
        for include in job_config.get("includes", []) or []:
            rsync_cmd.extend(["--include", include])
        for exclude in job_config.get("excludes", []) or []:
            rsync_cmd.extend(["--exclude", exclude])

        # Build display strings using your existing helpers
        source_str = self._build_source_path(job_config)
        dest_str = self._build_destination_path(job_config, job_name, global_settings)

        # Default local execution argv
        local_rsync_argv = rsync_cmd + [source_str, dest_str]

        # Structured detection (no regex): rely on validated form fields
        src_type = job_config.get("source_type")
        src_cfg = job_config.get("source_config", {}) or {}
        dst_type = job_config.get("dest_type")
        # rsyncd destination is indicated by dest_type or by dest_str shape
        dst_is_rsyncd = (dst_type == "rsyncd") or (
            isinstance(dest_str, str) and (dest_str.startswith("rsync://") or "::" in dest_str)
        )

        # SSH source components from validated config
        src_user = src_cfg.get("user")
        src_host = src_cfg.get("host")
        src_path = src_cfg.get("path")

        # Case: SSH source -> rsync daemon destination
        if (src_type == "ssh") and dst_is_rsyncd:
            if src_user and src_host and src_path:
                userhost = f"{src_user}@{src_host}"
                remote_src_path = src_path
            else:
                # fallback to formatted string if provided by our own builder
                if ":" in source_str:
                    userhost, remote_src_path = source_str.split(":", 1)
                else:
                    # unexpected; proceed with local exec
                    exec_argv = local_rsync_argv
                    log_cmd_str = " ".join(shlex.quote(x) for x in exec_argv)
                    return exec_argv, log_cmd_str, source_str, dest_str

            # replace SRC with the remote path for the remote rsync
            remote_rsync_list = local_rsync_argv.copy()  # [..., SRC, DST]
            remote_rsync_list[-2] = remote_src_path
            remote_cmd_str = shlex.join(remote_rsync_list)

            exec_argv = [ssh_bin, userhost, "--", remote_cmd_str]
            log_cmd_str = " ".join(shlex.quote(x) for x in exec_argv)
            return exec_argv, log_cmd_str, source_str, dest_str

        # Default: run rsync locally
        exec_argv = local_rsync_argv
        log_cmd_str = " ".join(shlex.quote(x) for x in exec_argv)
        return exec_argv, log_cmd_str, source_str, dest_str

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

    def _build_log_header(
        self,
        job_name: str,
        timestamp: str,
        mode_text: str,
        trigger_source: str,
        log_cmd_str: str,
        src_display: str,
        dst_display: str,
        job_config: dict,
    ):
        """Build log header with job details"""
        return f"""
========================================
Backup Job: {job_name} ({mode_text})
Time: {timestamp}
Triggered by: {trigger_source}
========================================
COMMAND EXECUTED:
{log_cmd_str}
SOURCE: {src_display}
DESTINATION: {dst_display}
INCLUDES: {job_config.get('includes', [])}
EXCLUDES: {job_config.get('excludes', [])}
========================================
{mode_text} OUTPUT:
"""
    
    def _discover_binary_path(self, binary_name, fallback_path):
        """Discover binary path using 'which' command with fallback"""
        try:
            result = subprocess.run(['which', binary_name], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return fallback_path

