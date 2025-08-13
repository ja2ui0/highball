#!/usr/bin/env python3
"""
Backup Manager Web Interface
Clean, modular architecture
"""
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Handlers
from handlers.dashboard import DashboardHandler
from handlers.config_handler import ConfigHandler
from handlers.logs import LogsHandler
from handlers.network import NetworkHandler
from handlers.backup import BackupHandler
from handlers.job_scheduler import JobSchedulerHandler
from handlers.restic_handler import ResticHandler

# Services
from services.template_service import TemplateService
from services.scheduler_service import SchedulerService
# NOTE: we import bootstrap_schedules lazily inside _initialize_services()
# so a scheduler import error won't take down the whole UI.

from config import BackupConfig


class BackupWebHandler(BaseHTTPRequestHandler):
    """Main request router - delegates to specific handlers"""

    # Class-level services (shared across requests)
    _backup_config = None
    _template_service = None
    _scheduler_service = None
    _handlers = None

    @classmethod
    def _initialize_services(cls):
        """Initialize services once at startup (idempotent & resilient)."""
        needs_init = (
            cls._backup_config is None
            or cls._template_service is None
            or cls._scheduler_service is None
            or cls._handlers is None
        )
        if not needs_init:
            return

        # Core services
        config_path = os.environ.get('CONFIG_PATH', '/config/config.yaml')
        cls._backup_config = cls._backup_config or BackupConfig(config_path)
        cls._template_service = cls._template_service or TemplateService(cls._backup_config)
        if cls._scheduler_service is None:
            cls._scheduler_service = SchedulerService()

        # Register schedules (do not bring down UI if this fails)
        try:
            from services.schedule_loader import bootstrap_schedules
            count = bootstrap_schedules(cls._backup_config, cls._scheduler_service)
            print(f"Scheduled {count} backup job(s) from config.")
        except Exception as e:
            print(f"[SCHEDULER] disabled at startup: {e}")

        # Build handler map last; if this throws, leave _handlers=None so we retry next request
        try:
            cls._handlers = {
                'dashboard': DashboardHandler(
                    cls._backup_config,
                    cls._template_service,
                    cls._scheduler_service
                ),
                'config': ConfigHandler(cls._backup_config, cls._template_service),
                'logs': LogsHandler(cls._template_service, cls._backup_config),
                'network': NetworkHandler(),
                'backup': BackupHandler(cls._backup_config, cls._scheduler_service),
                'job_scheduler': JobSchedulerHandler(cls._scheduler_service),
                'restic': ResticHandler(cls._backup_config),
            }
        except Exception:
            cls._handlers = None
            raise

    def __init__(self, *args, **kwargs):
        # Initialize services if not already done
        self._initialize_services()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Route GET requests to appropriate handlers"""
        url_parts = urlparse(self.path)
        path = url_parts.path
        params = parse_qs(url_parts.query)

        try:
            # Static files
            if path.startswith('/static/'):
                self._serve_static_file(path)
                return
            
            # Favicon
            if path == '/favicon.ico':
                self._serve_favicon()
                return

            # Route to handlers
            if path in ['/', '/dashboard']:
                self._handlers['dashboard'].show_dashboard(self)
            elif path == '/add-job':
                self._handlers['dashboard'].show_add_job_form(self)
            elif path == '/edit-job':
                job_name = params.get('name', [''])[0]
                self._handlers['dashboard'].show_edit_job_form(self, job_name)
            elif path == '/config':
                self._handlers['config'].show_config_manager(self)
            elif path == '/config/raw':
                self._handlers['config'].show_raw_editor(self)
            elif path == '/logs':
                log_type = params.get('type', ['app'])[0]
                self._handlers['logs'].show_logs(self, log_type)
            elif path == '/scan-network':
                network_range = params.get('range', ['192.168.1.0/24'])[0]
                self._handlers['network'].scan_network_for_rsyncd(self, network_range)
            elif path == '/validate-ssh':
                source = params.get('source', [''])[0]
                self._handlers['dashboard'].validate_ssh_source(self, source)
            elif path == '/validate-rsyncd':
                hostname = params.get('hostname', [''])[0]
                share = params.get('share', [''])[0]
                self._handlers['dashboard'].validate_rsyncd_destination(self, hostname, share)
            elif path == '/validate-restic':
                job_name = params.get('job', [''])[0]
                self._handlers['restic'].validate_restic_job(self, job_name)
            elif path == '/validate-restic-form':
                self._send_405()  # Only POST allowed for form validation
            elif path == '/check-restic-binary':
                job_name = params.get('job', [''])[0]
                self._handlers['restic'].check_restic_binary(self, job_name)
            elif path == '/restic-repo-info':
                job_name = params.get('job', [''])[0]
                self._handlers['restic'].get_repository_info(self, job_name)
            elif path == '/jobs':
                self._handlers['job_scheduler'].list_jobs(self)
            elif path == '/history':
                job_name = params.get('job', [''])[0]
                self._handlers['dashboard'].show_job_history(self, job_name)
            elif path == '/reload-config':
                self._handlers['config'].reload_config(self)
            elif path == '/backup-config':
                self._handlers['config'].download_config_backup(self)
            else:
                self._send_404()
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Server error: {str(e)}")

    def do_POST(self):
        """Route POST requests to appropriate handlers"""
        url_parts = urlparse(self.path)
        path = url_parts.path

        # Read form data
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = parse_qs(post_data)
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Invalid form data: {str(e)}")
            return

        try:
            # Route to handlers
            if path == '/save-job':
                self._handlers['dashboard'].save_backup_job(self, form_data)
            elif path == '/delete-job':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['dashboard'].delete_backup_job(self, job_name)
            elif path == '/restore-job':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['dashboard'].restore_backup_job(self, job_name)
            elif path == '/purge-job':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['dashboard'].purge_backup_job(self, job_name)
            elif path == '/run-backup':
                job_name = form_data.get('job_name', [''])[0]
                # Real run
                self._handlers['backup'].run_backup_job(self, job_name, dry_run=False)
            elif path == '/dry-run-backup':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['backup'].run_backup_job(self, job_name, dry_run=True)
            elif path == '/plan-restic-backup':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['restic'].plan_backup(self, job_name)
            elif path == '/validate-restic-form':
                self._handlers['restic'].validate_restic_form(self, form_data)
            elif path == '/save-config':
                self._handlers['config'].save_structured_config(self, form_data)
            elif path == '/save-config/raw':
                self._handlers['config'].save_raw_config(self, form_data)
            elif path == '/dismiss-warning':
                self._handlers['dashboard'].dismiss_config_warning(self)
            elif path == '/schedule-job':
                self._handlers['job_scheduler'].schedule_job(self, form_data)
            else:
                self._send_404()
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Server error: {str(e)}")

    def _serve_static_file(self, path):
        """Serve CSS/JS files"""
        file_path = path[1:]  # Remove leading /

        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()

            # Set content type
            if path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            else:
                content_type = 'text/plain'

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_404()

    def _serve_favicon(self):
        """Serve favicon.ico from root directory"""
        if os.path.exists('favicon.ico'):
            with open('favicon.ico', 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'image/x-icon')
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_404()

    def _send_404(self):
        """Send 404 error"""
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>404 Not Found</h1></body></html>')

    def _send_405(self):
        """Send 405 Method Not Allowed error"""
        self.send_response(405)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>405 Method Not Allowed</h1></body></html>')

    def _send_error_response(self, message):
        """Send error page"""
        import html
        html_content = f"""
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Server Error</h1>
            <p>{html.escape(message)}</p>
            <a href="/">Back to Dashboard</a>
        </body>
        </html>
        """
        self.send_response(500)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())


def main():
    """Start the web server"""
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), BackupWebHandler)
    print(f"Backup Manager starting on 0.0.0.0:{port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == '__main__':
    main()
