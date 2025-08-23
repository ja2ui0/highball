#!/usr/bin/env python3
"""
Highball FastAPI Application
Modern FastAPI-based backup manager web interface
"""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Specialized Handlers
from handlers.pages import GETHandlers, POSTHandlers, ValidationHandlers
from handlers.operations import OperationsHandler
from handlers.api import APIHandler
from handlers.forms import FormsHandler
from handlers.scheduler import JobSchedulerHandler

# Services
from services.template import TemplateService
from services.scheduling import SchedulingService
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

        # Register schedules (do not bring down UI if this fails)
        try:
            count = self.scheduler_service.bootstrap_schedules(self.backup_config)
            print(f"Scheduled {count} backup job(s) from config.")
        except Exception as e:
            print(f"[SCHEDULER] disabled at startup: {e}")

        # Initialize handlers
        self.handlers = {
            'get_pages': GETHandlers(self.backup_config, self.template_service, self.job_form_builder),
            'post_pages': POSTHandlers(self.backup_config, self.template_service, self.job_form_builder),
            'validation_pages': ValidationHandlers(self.backup_config, self.template_service, self.job_form_builder),
            'operations': OperationsHandler(self.backup_config, self.template_service),
            'api': APIHandler(self.backup_config, self.template_service),
            'forms': FormsHandler(self.backup_config, self.template_service),
            'job_scheduler': JobSchedulerHandler(self.scheduler_service),
        }


# Global services instance
services = HighballServices()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    services.initialize()
    yield


# Create FastAPI application
app = FastAPI(
    title="Highball Backup Manager",
    description="Web-based backup orchestration with scheduling and monitoring",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# =============================================================================
# BRIDGE FUNCTION ELIMINATED - 100% FASTAPI MODERNIZATION COMPLETE  
# =============================================================================
# All handlers now return FastAPI responses directly - zero legacy remnants


# =============================================================================
# MAIN DASHBOARD AND PAGES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard():
    """Main dashboard page"""
    return services.handlers['get_pages'].show_dashboard()


@app.get("/add-job", response_class=HTMLResponse)
async def show_add_job_form():
    """Add new backup job form"""
    return services.handlers['get_pages'].show_add_job_form()


@app.get("/edit-job", response_class=HTMLResponse)
async def show_edit_job_form(name: str = Query("")):
    """Edit existing backup job form"""
    return services.handlers['get_pages'].show_edit_job_form(name)


@app.get("/config", response_class=HTMLResponse)
async def show_config_manager():
    """Configuration manager page"""
    return services.handlers['get_pages'].show_config_manager()


@app.get("/config/raw", response_class=HTMLResponse)
async def show_raw_editor():
    """Raw YAML configuration editor"""
    return services.handlers['get_pages'].show_raw_editor()


@app.get("/dev", response_class=HTMLResponse)
async def show_dev_logs(type: str = Query("app")):
    """Development logs and debugging"""
    return services.handlers['get_pages'].show_dev_logs(type)


@app.get("/inspect", response_class=HTMLResponse)
async def show_job_inspect(name: str = Query("")):
    """Job inspection page"""
    return services.handlers['get_pages'].show_job_inspect(name)


# =============================================================================
# VALIDATION ENDPOINTS
# =============================================================================

@app.get("/scan-network")
async def scan_network_for_rsyncd(range: str = Query("192.168.1.0/24")):
    """Scan network for rsyncd services"""
    return services.handlers['validation_pages'].scan_network_for_rsyncd(range)


@app.get("/validate-ssh")
async def validate_ssh_source(source: str = Query("")):
    """Validate SSH source configuration"""
    return services.handlers['validation_pages'].validate_ssh_source(source)


@app.get("/validate-restic")
async def validate_restic_job(job: str = Query("")):
    """Validate Restic repository configuration"""
    return services.handlers['api'].validate_restic_job(job)


@app.post("/validate-restic-form")
async def validate_restic_form(request: Request):
    """Validate Restic configuration from form data"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['api'].validate_restic_form(form_data)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/restic-repo-info")
async def get_repository_info(job: str = Query("")):
    """Get Restic repository information"""
    return services.handlers['api'].get_repository_info(job)


@app.get("/restic-snapshots")
async def list_snapshots(job: str = Query("")):
    """List Restic repository snapshots"""
    return services.handlers['api'].list_snapshots(job)


@app.get("/restic-snapshot-stats")
async def get_snapshot_stats(job: str = Query(""), snapshot: str = Query("")):
    """Get statistics for specific snapshot"""
    return services.handlers['api'].get_snapshot_stats(job, snapshot)


@app.get("/restic-browse")
async def browse_directory(job: str = Query(""), snapshot: str = Query(""), path: str = Query("/")):
    """Browse directory in snapshot"""
    return services.handlers['api'].browse_directory(job, snapshot, path)


@app.get("/restic-init")
async def init_repository(job: str = Query("")):
    """Initialize Restic repository"""
    return services.handlers['api'].init_repository(job)


@app.get("/filesystem-browse")
async def browse_filesystem(path: str = Query("/")):
    """Browse filesystem"""
    return services.handlers['api'].browse_filesystem(path)


@app.get("/jobs")
async def list_jobs():
    """List scheduled jobs"""
    return services.handlers['job_scheduler'].list_jobs()


@app.get("/api/highball/jobs")
async def get_jobs(state: Optional[str] = Query(None), fields: Optional[str] = Query(None)):
    """API endpoint for jobs"""
    return services.handlers['api'].get_jobs(state, fields)


@app.get("/check-repository-availability")
async def check_repository_availability(job: str = Query("")):
    """Check repository availability"""
    return services.handlers['validation_pages'].check_repository_availability_htmx(job)


@app.get("/unlock-repository") 
async def unlock_repository_get(job: str = Query("")):
    """Unlock repository (GET)"""
    return services.handlers['validation_pages'].unlock_repository_htmx(job)


# =============================================================================
# POST ENDPOINTS
# =============================================================================

@app.post("/save-job")
async def save_job(request: Request):
    """Save backup job"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['post_pages'].save_backup_job(form_data)


@app.post("/delete-job")
async def delete_job(request: Request):
    """Delete backup job"""
    form = await request.form()
    job_name = form.get('job_name', '')
    return services.handlers['post_pages'].delete_backup_job(job_name)


@app.post("/run-backup")
async def run_backup(request: Request):
    """Run backup job"""
    form = await request.form()
    job_name = form.get('job_name', '')
    return services.handlers['operations'].run_backup_job(job_name, False)


@app.post("/dry-run-backup")
async def dry_run_backup(request: Request):
    """Dry run backup job"""
    form = await request.form()
    job_name = form.get('job_name', '')
    return services.handlers['operations'].run_backup_job(job_name, True)


@app.post("/validate-source-paths")
async def validate_source_paths(request: Request):
    """Validate source paths from form"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['validation_pages'].validate_source_paths(form_data)


@app.post("/initialize-restic-repo")
async def initialize_restic_repo(request: Request):
    """Initialize Restic repository"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['api'].initialize_restic_repo(form_data)


@app.post("/preview-config-changes")
async def preview_config_changes(request: Request):
    """Preview configuration changes"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['post_pages'].preview_config_changes(form_data)


@app.post("/save-config")
async def save_config(request: Request):
    """Save structured configuration"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['post_pages'].save_structured_config(form_data)


@app.post("/save-config/raw")
async def save_raw_config(request: Request):
    """Save raw YAML configuration"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['post_pages'].save_raw_config(form_data)


@app.post("/schedule-job")
async def schedule_job(request: Request):
    """Schedule a job"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['operations'].schedule_job(form_data)


@app.post("/restore")
async def process_restore_request(request: Request):
    """Process restore request"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['operations'].process_restore_request(form_data)


@app.post("/check-restore-overwrites")
async def check_restore_overwrites(request: Request):
    """Check restore overwrites"""
    form = await request.form()
    form_data = {}
    for key, value in form.items():
        if key in form_data:
            if not isinstance(form_data[key], list):
                form_data[key] = [form_data[key]]
            form_data[key].append(value)
        else:
            form_data[key] = [value]
    return services.handlers['operations'].check_restore_overwrites(form_data)


@app.post("/test-telegram-notification")
async def test_telegram_notification(request: Request):
    """Test Telegram notification"""
    form = await request.form()
    test_message = form.get('test_message', 'Test notification from Highball')
    return services.handlers['api'].test_telegram_notification(test_message)


@app.post("/test-email-notification")
async def test_email_notification(request: Request):
    """Test email notification"""
    form = await request.form()
    test_message = form.get('test_message', 'Test notification from Highball')
    return services.handlers['api'].test_email_notification(test_message)


@app.post("/unlock-repository")
async def unlock_repository_post(request: Request):
    """Unlock repository (POST)"""
    form = await request.form()
    # Extract job name from query params for POST
    url_parts = str(request.url).split('?')
    if len(url_parts) > 1:
        from urllib.parse import parse_qs
        params = parse_qs(url_parts[1])
        job_name = params.get('job', [''])[0]
    else:
        job_name = ''
    return services.handlers['validation_pages'].unlock_repository_htmx(job_name)


# =============================================================================
# HTMX ROUTES
# =============================================================================

@app.post("/htmx/{action}")
async def handle_htmx_request(action: str, request: Request):
    """Handle HTMX requests"""
    html = services.handlers['forms'].handle_htmx_request(request, action)
    return HTMLResponse(content=html)


# =============================================================================
# OPTIONS for CORS
# =============================================================================

@app.options("/api/{path:path}")
async def handle_options(path: str):
    """Handle CORS preflight requests for API endpoints"""
    return services.handlers['api'].handle_options()


# =============================================================================
# STATIC FILES
# =============================================================================

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    if os.path.exists('favicon.ico'):
        return FileResponse('favicon.ico')
    else:
        raise HTTPException(status_code=404)


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8080
    port = int(os.environ.get('PORT', '8080'))
    
    print(f"Starting Highball on port {port}")
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=port,
        reload=False,
        access_log=True
    )