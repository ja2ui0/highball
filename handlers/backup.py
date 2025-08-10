"""
Backup execution handler
Handles running backup jobs (dry-run and real) with async execution
"""
import subprocess
from datetime import datetime
import threading
import shlex  # for safe logging/remote command quoting
from services.template_service import TemplateService


class BackupHandler:
    """Handles backup job execution"""

    def __init__(self, backup_config):
        self.backup_config = backup_config

    # ---------------------------
    # Public entry point (async)
    # ---------------------------
    def run_backup_job(self, handler, job_name, dry_run=True, source="manual"):
        """
        Kick off a backup job in the background and immediately redirect.
        """
        if job_name not in self.backup_config.config.get("backup_jobs", {}):
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
            self.backup_config.log_backup_run(job_name, "started", started_msg)
        except Exception:
            pass

        # Immediately redirect back to dashboard so the UI never blocks
        TemplateService.send_redirect(handler, "/")

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
            self.backup_config.log_backup_run(job_name, status, message)
        except Exception as e:
            self.backup_config.log_backup_run(job_name, "error", str(e))

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
                # no timeout: call without the timeout kwarg
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

        # Write to log file (same files you already used)
        log_file = "/tmp/backup-dry-run.log" if dry_run else f"/tmp/backup-{job_name}.log"
        try:
            with open(log_file, "a") as f:
                f.write(log_content)
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
        rsync_bin = global_settings.get("rsync_path", "/usr/bin/rsync")
        ssh_bin = global_settings.get("ssh_path", "/usr/bin/ssh")

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
        """Build source path from job configuration"""
        # New structure
        if "source_type" in job_config:
            source_config = job_config.get("source_config", {})
            return source_config.get("source_string", "")
        # Legacy
        return job_config.get("source", "")

    def _build_destination_path(self, job_config, job_name, global_settings):
        """Build destination path from job configuration"""
        # New structure
        if "dest_type" in job_config:
            dest_type = job_config["dest_type"]
            dest_config = job_config.get("dest_config", {})

            if dest_type == "local":
                return dest_config.get("path", f"/backups/{job_name}")
            elif dest_type == "ssh":
                return dest_config.get("dest_string", f"backup@localhost:/backups/{job_name}")
            elif dest_type == "rsyncd":
                return dest_config.get("dest_string", f"rsync://localhost/{job_name}")

        # Legacy: rsync daemon to configured host
        dest_host = global_settings.get("dest_host", "192.168.1.252")
        return f"{dest_host}::{job_name}"

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

