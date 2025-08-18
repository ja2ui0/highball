#!/usr/bin/env python3
"""
Backup Manager Web Interface
Clean, modular architecture
"""
import os
import traceback
import cgi
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Consolidated Handlers
from handlers.pages import PagesHandler
from handlers.operations import OperationsHandler
from handlers.api import APIHandler
from handlers.forms import FormsHandler

# Legacy handlers for compatibility
from handlers.scheduler import JobSchedulerHandler

# Services
from services.template import TemplateService
from services.scheduling import SchedulingService
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
            cls._scheduler_service = SchedulingService()

        # Register schedules (do not bring down UI if this fails)
        try:
            count = cls._scheduler_service.bootstrap_schedules(cls._backup_config)
            print(f"Scheduled {count} backup job(s) from config.")
        except Exception as e:
            print(f"[SCHEDULER] disabled at startup: {e}")

        # Build handler map last; if this throws, leave _handlers=None so we retry next request
        try:
            cls._handlers = {
                'pages': PagesHandler(cls._backup_config, cls._template_service),
                'operations': OperationsHandler(cls._backup_config, cls._template_service),
                'api': APIHandler(cls._backup_config, cls._template_service),
                'forms': FormsHandler(cls._backup_config, cls._template_service),
                'job_scheduler': JobSchedulerHandler(cls._scheduler_service),
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

            # Route to consolidated handlers
            if path in ['/', '/dashboard']:
                self._handlers['pages'].show_dashboard(self)
            elif path == '/add-job':
                self._handlers['pages'].show_add_job_form(self)
            elif path == '/edit-job':
                job_name = params.get('name', [''])[0]
                self._handlers['pages'].show_edit_job_form(self, job_name)
            elif path == '/config':
                self._handlers['pages'].show_config_manager(self)
            elif path == '/config/raw':
                self._handlers['pages'].show_raw_editor(self)
            elif path == '/dev':
                log_type = params.get('type', ['app'])[0]
                self._handlers['pages'].show_dev_logs(self, log_type)
            elif path == '/inspect':
                self._handlers['pages'].show_job_inspect(self)
            elif path == '/scan-network':
                network_range = params.get('range', ['192.168.1.0/24'])[0]
                self._handlers['pages'].scan_network_for_rsyncd(self, network_range)
            elif path == '/validate-ssh':
                source = params.get('source', [''])[0]
                self._handlers['pages'].validate_ssh_source(self, source)
            elif path == '/validate-restic':
                job_name = params.get('job', [''])[0]
                self._handlers['api'].validate_restic_job(self, job_name)
            elif path == '/validate-restic-form':
                self._send_405()  # Only POST allowed for form validation
            elif path == '/restic-repo-info':
                job_name = params.get('job', [''])[0]
                self._handlers['api'].get_repository_info(self, job_name)
            elif path == '/restic-snapshots':
                job_name = params.get('job', [''])[0]
                self._handlers['api'].list_snapshots(self, job_name)
            elif path == '/restic-snapshot-stats':
                job_name = params.get('job', [''])[0]
                snapshot_id = params.get('snapshot', [''])[0]
                self._handlers['api'].get_snapshot_stats(self, job_name, snapshot_id)
            elif path == '/restic-browse':
                job_name = params.get('job', [''])[0]
                snapshot_id = params.get('snapshot', [''])[0]
                browse_path = params.get('path', ['/'])[0]
                self._handlers['api'].browse_directory(self, job_name, snapshot_id, browse_path)
            elif path == '/restic-init':
                job_name = params.get('job', [''])[0]
                self._handlers['api'].init_repository(self, job_name)
            elif path == '/filesystem-browse':
                self._handlers['api'].browse_filesystem(self)
            elif path == '/jobs':
                self._handlers['job_scheduler'].list_jobs(self)
            elif path == '/api/highball/jobs':
                self._handlers['api'].get_jobs(self)
            else:
                self._send_404()
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Server error: {str(e)}")

    def do_POST(self):
        """Route POST requests to appropriate handlers"""
        url_parts = urlparse(self.path)
        path = url_parts.path

        # HTMX routes handle their own form parsing (thin orchestrator)
        if path.startswith('/htmx/'):
            action = path[6:]  # Remove '/htmx/' prefix
            html = self._handlers['forms'].handle_htmx_request(self, action)
            self._send_htmx_response(html)
            return

        # Read form data for non-HTMX endpoints - support both multipart and URL-encoded
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Check content type to determine parsing method
            content_type = self.headers.get('Content-Type', '')
            
            if content_type.startswith('multipart/form-data'):
                # Parse multipart form data
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                
                # Convert to dict format expected by handlers
                form_data = {}
                for field in form.list:
                    if field.name in form_data:
                        # Handle multiple values for same field name
                        if not isinstance(form_data[field.name], list):
                            form_data[field.name] = [form_data[field.name]]
                        form_data[field.name].append(field.value)
                    else:
                        form_data[field.name] = [field.value]
            else:
                # Parse URL-encoded form data (legacy support)
                post_data = self.rfile.read(content_length).decode('utf-8')
                form_data = parse_qs(post_data)
                
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Invalid form data: {str(e)}")
            return

        try:
            # Route to consolidated handlers
            if path == '/save-job':
                self._handlers['pages'].save_backup_job(self, form_data)
            elif path == '/delete-job':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['pages'].delete_backup_job(self, job_name)
            elif path == '/run-backup':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['operations'].run_backup_job(self, job_name, dry_run=False)
            elif path == '/dry-run-backup':
                job_name = form_data.get('job_name', [''])[0]
                self._handlers['operations'].run_backup_job(self, job_name, dry_run=True)
            elif path == '/validate-restic-form':
                self._handlers['api'].validate_restic_form(self, form_data)
            elif path == '/validate-source-paths':
                self._handlers['pages'].validate_source_paths(self, form_data)
            elif path == '/initialize-restic-repo':
                self._handlers['api'].initialize_restic_repo(self, form_data)
            
            elif path == '/preview-config-changes':
                self._handlers['pages'].preview_config_changes(self, form_data)
            elif path == '/save-config':
                self._handlers['pages'].save_structured_config(self, form_data)
            elif path == '/save-config/raw':
                self._handlers['pages'].save_raw_config(self, form_data)
            elif path == '/schedule-job':
                self._handlers['operations'].schedule_job(self, form_data)
            elif path == '/restore':
                self._handlers['operations'].process_restore_request(self, form_data)
            elif path == '/check-restore-overwrites':
                self._handlers['operations'].check_restore_overwrites(self, form_data)
            elif path == '/test-telegram-notification':
                self._handlers['api'].test_telegram_notification(self, form_data)
            elif path == '/test-email-notification':
                self._handlers['api'].test_email_notification(self, form_data)
            else:
                self._send_404()
        except Exception as e:
            traceback.print_exc()
            self._send_error_response(f"Server error: {str(e)}")

    def do_OPTIONS(self):
        """Handle CORS preflight requests for API endpoints"""
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        if path.startswith('/api/'):
            self._handlers['api'].handle_options(self)
        else:
            self._send_405()

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

    def _send_htmx_response(self, html_content):
        """Send HTMX HTML fragment response"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

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
