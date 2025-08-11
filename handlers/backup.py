"""
Backup execution handler
Handles running backup jobs (dry-run and real) with async execution
"""
import subprocess
import time
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
    
    def run_backup_job_with_conflict_check(self, handler, job_name, dry_run=True, source="schedule"):
        """
        Run backup job with runtime conflict detection and avoidance.
        Will wait for conflicting jobs to finish before running.
        """
        from services.job_conflict_manager import RuntimeConflictManager
        import time
        
        if job_name not in self.backup_config.config.get("backup_jobs", {}):
            if handler is not None:
                TemplateService.send_error_response(handler, f"Job '{job_name}' not found")
            return

        job_config = self.backup_config.config["backup_jobs"][job_name]
        conflict_manager = RuntimeConflictManager(self.backup_config)
        
        # Track conflict delay for logging and notifications
        wait_start_time = None
        total_wait_time = 0
        
        # Wait for any conflicting jobs to finish
        while conflict_manager.has_conflicting_jobs_running(job_name, job_config):
            if wait_start_time is None:
                wait_start_time = time.time()
                running_jobs = conflict_manager.get_running_jobs()
                conflicting_resources = self._get_conflicting_resources(job_config, running_jobs, conflict_manager)
                print(f"INFO: Job '{job_name}' delayed due to resource conflicts with: {', '.join(running_jobs)}")
                print(f"INFO: Conflicting resources: {conflicting_resources}")
                
                # Log initial conflict detection
                conflict_msg = f"Job delayed waiting for conflicting jobs: {', '.join(running_jobs)}"
                self.job_logger.log_job_status(job_name, "waiting-conflict", conflict_msg)
            
            check_interval = conflict_manager.get_conflict_check_interval()
            print(f"INFO: Job '{job_name}' waiting {check_interval} seconds for conflicting jobs to finish")
            time.sleep(check_interval)
        
        # Calculate total wait time and log if there was a delay
        if wait_start_time is not None:
            total_wait_time = time.time() - wait_start_time
            delay_msg = f"Job waited {total_wait_time:.1f} seconds due to resource conflicts before starting"
            print(f"INFO: {delay_msg}")
            self.job_logger.log_job_status(job_name, "conflict-resolved", delay_msg)
            
            # Send notification if delay was significant (configurable threshold)
            if total_wait_time > self._get_delay_notification_threshold():
                self._send_delay_notification(job_name, total_wait_time, source)
        
        # Register this job as running
        conflict_manager.register_running_job(job_name)
        
        try:
            # Run the actual backup job
            self.run_backup_job(handler, job_name, dry_run, source)
        finally:
            # Always unregister the job, even if it fails
            conflict_manager.unregister_running_job(job_name)

    # ---------------------------
    # Background worker
    # ---------------------------
    def _run_job_background(self, job_name, job_config, global_settings, dry_run, trigger_source):
        """
        Runs in a daemon thread: builds command, executes, logs results.
        """
        start_time = time.time()
        
        try:
            result = self._execute_rsync(job_name, job_config, global_settings, dry_run, trigger_source)
            duration = time.time() - start_time
            
            if dry_run:
                status = "completed-dry-run" if result["success"] else "error-dry-run"
                message = f'Dry run completed with return code {result["return_code"]} (triggered by {trigger_source})'
            else:
                status = "completed" if result["success"] else "error"
                message = f'Backup completed with return code {result["return_code"]}'
            
            self.job_logger.log_job_status(job_name, status, message)
            self.job_logger.log_job_execution(job_name, result["log_content"])
            
            # Send notifications
            try:
                from services.notification_service import NotificationService
                notifier = NotificationService(self.backup_config)
                
                if result["success"]:
                    notifier.send_job_success_notification(job_name, duration, dry_run)
                else:
                    error_msg = f'Return code {result["return_code"]}'
                    notifier.send_job_failure_notification(job_name, error_msg, dry_run)
            except Exception as notify_error:
                print(f"WARNING: Failed to send job completion notification: {str(notify_error)}")
                
        except Exception as e:
            duration = time.time() - start_time
            self.job_logger.log_job_status(job_name, "error", str(e))
            self.job_logger.log_job_execution(job_name, f"ERROR: {str(e)}", "ERROR")
            
            # Send failure notification
            try:
                from services.notification_service import NotificationService
                notifier = NotificationService(self.backup_config)
                notifier.send_job_failure_notification(job_name, str(e), dry_run)
            except Exception as notify_error:
                print(f"WARNING: Failed to send job failure notification: {str(notify_error)}")

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
    
    def _get_conflicting_resources(self, job_config, running_jobs, conflict_manager):
        """Get description of conflicting resources"""
        job_sources, job_destinations = conflict_manager.get_job_resources(job_config)
        
        conflicts = []
        for running_job in running_jobs:
            if running_job in self.backup_config.config.get("backup_jobs", {}):
                running_config = self.backup_config.config["backup_jobs"][running_job]
                running_sources, running_destinations = conflict_manager.get_job_resources(running_config)
                
                shared_sources = job_sources.intersection(running_sources)
                shared_destinations = job_destinations.intersection(running_destinations)
                
                if shared_sources:
                    conflicts.append(f"shared sources: {', '.join(shared_sources)}")
                if shared_destinations:
                    conflicts.append(f"shared destinations: {', '.join(shared_destinations)}")
        
        return "; ".join(conflicts) if conflicts else "unknown resource conflict"
    
    def _get_delay_notification_threshold(self):
        """Get minimum delay time before sending notification (in seconds)"""
        global_settings = self.backup_config.config.get("global_settings", {})
        return global_settings.get("delay_notification_threshold", 300)  # Default 5 minutes
    
    def _send_delay_notification(self, job_name, delay_seconds, source):
        """Send notification about job delay"""
        try:
            from services.notification_service import NotificationService
            from services.job_conflict_manager import RuntimeConflictManager
            
            notifier = NotificationService(self.backup_config)
            conflict_manager = RuntimeConflictManager(self.backup_config)
            
            delay_minutes = delay_seconds / 60
            running_jobs = conflict_manager.get_running_jobs()
            
            notifier.send_job_delay_notification(job_name, delay_minutes, running_jobs, source)
            print(f"INFO: Sent delay notification for job '{job_name}' (delayed {delay_minutes:.1f} minutes)")
        except Exception as e:
            print(f"WARNING: Failed to send delay notification for job '{job_name}': {str(e)}")

