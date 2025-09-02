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
# God object handlers eliminated - functionality moved to domain-specific pillars
from origins.handlers.pages import origins_handler
from dests.handlers.pages import destinations_handler
from jobs.handlers.pages import jobs_handler
from admin.handlers.pages import admin_handler

# Services
from admin.services.init import HighballServices


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
# MAIN DASHBOARD AND PAGES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard():
    """Main dashboard page"""
    return jobs_handler.show_dashboard()


@app.get("/add-job", response_class=HTMLResponse)
async def show_add_job_form():
    """Add new backup job form"""
    return jobs_handler.show_add_job_form()


@app.get("/edit-job", response_class=HTMLResponse)
async def show_edit_job_form(name: str = Query("")):
    """Edit existing backup job form"""
    return jobs_handler.show_edit_job_form(name)


@app.get("/config", response_class=HTMLResponse)
async def show_config_manager():
    """Configuration manager page"""
    return admin_handler.show_config_manager()


@app.get("/config/raw", response_class=HTMLResponse)
async def show_raw_editor():
    """Raw YAML configuration editor"""
    return admin_handler.show_raw_editor()


@app.get("/dev", response_class=HTMLResponse)
async def show_dev_logs(type: str = Query("app")):
    """Development logs and debugging"""
    return admin_handler.show_dev_logs(type)


@app.get("/inspect", response_class=HTMLResponse)
async def show_job_inspect(name: str = Query("")):
    """Job inspection page"""
    return jobs_handler.show_job_inspect(name)


# =============================================================================
# SSH ORIGIN MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/ssh", response_class=HTMLResponse)
async def show_ssh_origins():
    """SSH origins management page"""
    return origins_handler.show_ssh_origins()


@app.post("/ssh/add")
async def add_ssh_origin(request: Request):
    """Add new SSH origin"""
    form_data = dict(await request.form())
    return origins_handler.add_ssh_origin(form_data)


@app.post("/ssh/save")
async def save_ssh_origin(request: Request):
    """Save SSH origin changes"""
    form_data = dict(await request.form())
    return origins_handler.save_ssh_origin(form_data)


@app.get("/ssh/edit/{origin_name}")
async def edit_ssh_origin(origin_name: str):
    """Load SSH origin for editing"""
    return origins_handler.edit_ssh_origin(origin_name)


@app.delete("/ssh/{origin_name}")
async def delete_ssh_origin(origin_name: str):
    """Delete SSH origin"""
    return origins_handler.delete_ssh_origin(origin_name)


@app.post("/ssh/validate")
async def validate_ssh_origin(request: Request):
    """Validate SSH origin configuration"""
    form_data = dict(await request.form())
    return origins_handler.validate_ssh_origin(form_data)

@app.get("/ssh/progress/{session_id}")
async def get_ssh_progress(session_id: str):
    """Get SSH validation progress for a session"""
    return origins_handler.get_ssh_progress(session_id)

# SSH Origin HTMX Partials
@app.post("/htmx/toggle-auth-method")
async def toggle_ssh_auth_method(request: Request):
    """Toggle SSH authentication method (HTMX partial)"""
    form_data = dict(await request.form())
    return origins_handler.toggle_ssh_auth_method(form_data)



# =============================================================================
# DESTINATIONS MANAGEMENT ROUTES
# =============================================================================

@app.get("/dests", response_class=HTMLResponse)
async def show_destinations():
    """Destinations management page"""
    return destinations_handler.show_destinations()


@app.post("/dests/add")
async def add_destination(request: Request):
    """Add new destination"""
    form_data = dict(await request.form())
    return destinations_handler.add_destination(form_data)


@app.post("/dests/save")
async def save_destination(request: Request):
    """Save destination changes"""
    form_data = dict(await request.form())
    return destinations_handler.save_destination(form_data)


@app.post("/dests/delete")
async def delete_destination(name: str = Query("")):
    """Delete destination"""
    return destinations_handler.delete_destination(name)


@app.post("/dests/validate")
async def validate_destination(request: Request):
    """Validate destination configuration"""
    form_data = dict(await request.form())
    return destinations_handler.validate_destination(form_data)

# Destination HTMX Partials
@app.post("/htmx/destination-type-fields")
async def destination_type_fields(request: Request):
    """Load destination type-specific fields (HTMX partial)"""
    form_data = dict(await request.form())
    return destinations_handler.destination_type_fields(form_data)


# =============================================================================
# VALIDATION ENDPOINTS
# =============================================================================

@app.get("/scan-network")
async def scan_network_for_rsyncd(range: str = Query("192.168.1.0/24")):
    """Scan network for rsyncd services"""
    return destinations_handler.scan_network_for_rsyncd(range)


@app.get("/validate-ssh")
async def validate_ssh_source(source: str = Query("")):
    """Validate SSH source configuration"""
    return origins_handler.validate_ssh_source(source)




# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/restic-repo-info")
async def get_repository_info(job: str = Query("")):
    """Get Restic repository information"""
    return services.restic_api.get_repository_info(job)


@app.get("/restic-snapshots")
async def list_snapshots(job: str = Query("")):
    """List Restic repository snapshots"""
    return services.restic_api.list_snapshots(job)


@app.get("/restic-snapshot-stats")
async def get_snapshot_stats(job: str = Query(""), snapshot: str = Query("")):
    """Get statistics for specific snapshot"""
    return services.restic_api.get_snapshot_stats(job, snapshot)


@app.get("/restic-browse")
async def browse_directory(job: str = Query(""), snapshot: str = Query(""), path: str = Query("/")):
    """Browse directory in snapshot"""
    return services.restic_api.browse_directory(job, snapshot, path)


@app.get("/restic-init")
async def init_repository(job: str = Query("")):
    """Initialize Restic repository"""
    return services.restic_api.init_repository(job)


@app.get("/filesystem-browse")
async def browse_filesystem(path: str = Query("/")):
    """Browse filesystem"""
    return jobs_handler.browse_filesystem(path)


@app.get("/jobs")
async def list_jobs():
    """List scheduled jobs"""
    return services.handlers['job_scheduler'].list_jobs()




@app.get("/check-repository-availability")
async def check_repository_availability(job: str = Query("")):
    """Check repository availability"""
    return jobs_handler.check_repository_availability_htmx(job)


@app.get("/unlock-repository") 
async def unlock_repository_get(job: str = Query("")):
    """Unlock repository (GET)"""
    return jobs_handler.unlock_repository_htmx(job)


# =============================================================================
# POST ENDPOINTS
# =============================================================================

@app.post("/save-job")
async def save_job(request: Request):
    """Save backup job"""
    return await jobs_handler.save_backup_job_htmx(request)


@app.get("/delete-job")
async def delete_job(name: str = Query("")):
    """Delete backup job"""
    return jobs_handler.delete_backup_job(name)


@app.get("/purge-job")
async def purge_job(name: str = Query("")):
    """Permanently purge backup job from deleted jobs"""
    return jobs_handler.purge_backup_job(name)


@app.get("/restore-job")
async def restore_job(name: str = Query("")):
    """Restore backup job from deleted jobs"""
    return jobs_handler.restore_backup_job(name)


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
    return await jobs_handler.validate_source_paths_htmx(request)


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
    return services.restic_api.initialize_restic_repo(form_data)


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
    return admin_handler.preview_config_changes(form_data)


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
    return admin_handler.save_structured_config(form_data)


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
    return admin_handler.save_raw_config(form_data)


@app.post("/admin/add-global-notification-provider")
async def add_global_notification_provider(request: Request):
    """Add global notification provider"""
    return await admin_handler.add_global_notification_provider_htmx(request)


@app.post("/admin/remove-global-notification-provider")
async def remove_global_notification_provider(request: Request):
    """Remove global notification provider"""
    return await admin_handler.remove_global_notification_provider_htmx(request)


@app.post("/admin/clear-logs")
async def clear_logs(request: Request):
    """Clear logs"""
    return await admin_handler.clear_logs_htmx(request)


@app.post("/admin/refresh-logs")
async def refresh_logs(request: Request):
    """Refresh logs"""
    return await admin_handler.refresh_logs_htmx(request)


@app.post("/admin/queue-settings")
async def handle_queue_settings(request: Request):
    """Handle notification queue settings"""
    return await admin_handler.handle_queue_settings_htmx(request)


@app.post("/admin/cron-field")
async def render_cron_field(request: Request):
    """Render cron field"""
    return await admin_handler.render_cron_field_htmx(request)


@app.post("/admin/toggle-password-visibility")
async def toggle_password_visibility(request: Request):
    """Toggle password field visibility"""
    return await admin_handler.toggle_password_visibility_htmx(request)


@app.post("/admin/preview-config")
async def preview_config(request: Request):
    """Generate job config preview"""
    return await admin_handler.preview_config_htmx(request)


@app.post("/admin/check-form-changes")
async def check_form_changes(request: Request):
    """Check if form has changes"""
    return await admin_handler.check_form_changes_htmx(request)


@app.post("/dests/init-restic-repository")
async def init_restic_repository(request: Request):
    """Initialize Restic repository"""
    return await destinations_handler.init_restic_repository_htmx(request)


@app.post("/dests/maintenance-fields")
async def render_maintenance_fields(request: Request):
    """Render maintenance configuration fields"""
    return await destinations_handler.render_maintenance_fields_htmx(request)


@app.post("/dests/rsyncd-fields")
async def render_rsyncd_fields(request: Request):
    """Render rsyncd-specific fields"""
    return await destinations_handler.render_rsyncd_fields_htmx(request)


@app.post("/dests/maintenance-toggle")
async def render_maintenance_toggle(request: Request):
    """Render maintenance fields (same as maintenance-fields)"""
    return await destinations_handler.render_maintenance_fields_htmx(request)


@app.post("/dests/restic-repo-fields")
async def render_restic_repo_fields(request: Request):
    """Render Restic repository type fields"""
    return await destinations_handler.render_restic_repo_fields_htmx(request)


@app.post("/dests/restic-uri-preview")
async def generate_restic_uri_preview(request: Request):
    """Generate real-time URI preview"""
    return await destinations_handler.generate_restic_uri_preview_htmx(request)


@app.post("/jobs/restore-target-change")
async def handle_restore_target_change(request: Request):
    """Handle restore target change and check overwrites"""
    return await jobs_handler.handle_restore_target_change_htmx(request)


@app.post("/jobs/restore-dry-run-change")
async def handle_restore_dry_run_change(request: Request):
    """Handle dry run toggle and update warning"""
    return await jobs_handler.handle_restore_dry_run_change_htmx(request)


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


@app.post("/jobs/check-restore-overwrites")
async def check_restore_overwrites(request: Request):
    """Check restore overwrites - Jobs pillar"""
    return await jobs_handler.check_restore_overwrites_htmx(request)


@app.post("/test-telegram-notification")
async def test_telegram_notification(request: Request):
    """Test Telegram notification"""
    form = await request.form()
    test_message = form.get('test_message', 'Test notification from Highball')
    return services.notification_test.test_telegram_notification(test_message)


@app.post("/test-email-notification")
async def test_email_notification(request: Request):
    """Test email notification"""
    form = await request.form()
    test_message = form.get('test_message', 'Test notification from Highball')
    return services.notification_test.test_email_notification(test_message)


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
    return jobs_handler.unlock_repository_htmx(job_name)


# =============================================================================
# HTMX ROUTES
# =============================================================================

@app.post("/origins/validate-ssh-source")
async def validate_ssh_source_endpoint(request: Request):
    """Validate SSH source configuration - Origins pillar"""
    return await origins_handler.validate_ssh_source_htmx(request)

@app.post("/origins/source-fields")
async def render_source_fields_endpoint(request: Request):
    """Render source-specific form fields - Origins pillar"""
    return await origins_handler.render_source_fields_htmx(request)

@app.post("/origins/preview-ssh-config")
async def preview_ssh_config_endpoint(request: Request):
    """Preview SSH origin configuration - Origins pillar"""
    return await origins_handler.preview_ssh_config_htmx(request)

@app.post("/jobs/validate-source-path")
async def validate_source_path_endpoint(request: Request):
    """Validate source path with permission checking - Jobs pillar"""
    return await jobs_handler.validate_source_path_htmx(request)

@app.post("/jobs/add-source-path")
async def add_source_path_endpoint(request: Request):
    """Add new source path entry - Jobs pillar"""
    return await jobs_handler.add_source_path_htmx(request)

@app.post("/jobs/remove-source-path")
async def remove_source_path_endpoint(request: Request):
    """Remove source path entry - Jobs pillar"""
    return await jobs_handler.remove_source_path_htmx(request)

@app.post("/jobs/notification-providers")
async def notification_providers_endpoint(request: Request):
    """Render notification providers for job configuration - Jobs pillar"""
    return await jobs_handler.render_notification_providers_htmx(request)

@app.post("/jobs/add-notification-provider")
async def add_notification_provider_endpoint(request: Request):
    """Add notification provider to job configuration - Jobs pillar"""
    return await jobs_handler.add_notification_provider_htmx(request)

@app.post("/jobs/remove-notification-provider")
async def remove_notification_provider_endpoint(request: Request):
    """Remove notification provider from job configuration - Jobs pillar"""
    return await jobs_handler.remove_notification_provider_htmx(request)

@app.post("/jobs/toggle-success-message")
async def toggle_success_message_endpoint(request: Request):
    """Toggle success message visibility in job notification configuration - Jobs pillar"""
    return await jobs_handler.toggle_success_message_htmx(request)

@app.post("/jobs/toggle-failure-message")
async def toggle_failure_message_endpoint(request: Request):
    """Toggle failure message visibility in job notification configuration - Jobs pillar"""
    return await jobs_handler.toggle_failure_message_htmx(request)

@app.post("/destinations/dest-fields")
async def render_dest_fields_endpoint(request: Request):
    """Render destination-specific form fields - Destinations pillar"""
    return await destinations_handler.render_dest_fields_htmx(request)

@app.post("/destinations/restic-fields")
async def render_restic_fields_endpoint(request: Request):
    """Render Restic repository configuration fields - Destinations pillar"""
    return await destinations_handler.render_restic_fields_htmx(request)

@app.post("/destinations/validate-ssh-dest")
async def validate_ssh_dest_endpoint(request: Request):
    """Validate SSH destination configuration - Destinations pillar"""
    return await destinations_handler.validate_ssh_dest_htmx(request)

@app.post("/destinations/validate-restic")
async def validate_restic_endpoint(request: Request):
    """Validate Restic repository configuration - Destinations pillar"""
    return await destinations_handler.validate_restic_htmx(request)

@app.post("/destinations/validate-origin-repo-path")
async def validate_origin_repo_path_endpoint(request: Request):
    """Validate same-as-origin repository path - Destinations pillar"""
    return await destinations_handler.validate_origin_repo_path_htmx(request)

@app.post("/htmx/{action}")
async def handle_htmx_request(action: str, request: Request):
    """Handle HTMX requests"""
    return await services.handlers['forms'].handle_htmx_request_async(request, action)


# =============================================================================
# OPTIONS for CORS
# =============================================================================

@app.options("/api/{path:path}")
async def handle_options(path: str):
    """Handle CORS preflight requests for API endpoints"""
    return services.handle_options()


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
