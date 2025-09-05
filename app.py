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

# Domain Handlers - Pure Switchboard Pattern
from origins.handlers.pages import origins_handler
from dests.handlers.pages import destinations_handler
from dests.handlers.htmx import destinations_htmx
from jobs.handlers.pages import jobs_handler as job_pages
from jobs.handlers.htmx import htmx_handlers as job_htmx
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
# MAIN PAGES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard():
    return job_pages.show_dashboard()

@app.get("/jobs/add", response_class=HTMLResponse)
async def show_add_job_form():
    return job_pages.show_add_job_form()

@app.get("/jobs/edit", response_class=HTMLResponse)
async def show_edit_job_form(name: str = Query("")):
    return job_pages.show_edit_job_form(name)

@app.get("/config", response_class=HTMLResponse)
async def show_config_manager():
    return admin_handler.show_config_manager()

@app.get("/config/raw", response_class=HTMLResponse)
async def show_raw_editor():
    return admin_handler.show_raw_editor()

@app.get("/dev", response_class=HTMLResponse)
async def show_dev_logs(type: str = Query("app")):
    return admin_handler.show_dev_logs(type)

@app.get("/inspect", response_class=HTMLResponse)
async def show_job_inspect(name: str = Query("")):
    return job_pages.show_job_inspect(name)

# =============================================================================
# SSH ORIGINS
# =============================================================================

@app.get("/ssh", response_class=HTMLResponse)
async def show_ssh_origins():
    return origins_handler.show_ssh_origins()

@app.post("/ssh/add")
async def add_ssh_origin(request: Request):
    return await origins_handler.add_ssh_origin_htmx(request)

@app.post("/ssh/save")
async def save_ssh_origin(request: Request):
    return await origins_handler.save_ssh_origin_htmx(request)

@app.get("/ssh/edit/{origin_name}")
async def edit_ssh_origin(origin_name: str):
    return origins_handler.edit_ssh_origin(origin_name)

@app.delete("/ssh/{origin_name}")
async def delete_ssh_origin(origin_name: str):
    return origins_handler.delete_ssh_origin(origin_name)

@app.post("/ssh/validate")
async def validate_ssh_origin(request: Request):
    return await origins_handler.validate_ssh_origin_htmx(request)

@app.get("/ssh/progress/{session_id}")
async def get_ssh_progress(session_id: str):
    return origins_handler.get_ssh_progress(session_id)

@app.get("/ssh/stream/{session_id}")
async def stream_ssh_progress(session_id: str, request: Request):
    return await origins_handler.stream_ssh_progress(session_id, request)

@app.post("/htmx/toggle-auth-method")
async def toggle_ssh_auth_method(request: Request):
    return await origins_handler.toggle_ssh_auth_method_htmx(request)

# =============================================================================
# DESTINATIONS
# =============================================================================

@app.get("/dests", response_class=HTMLResponse)
async def show_destinations():
    return destinations_handler.show_destinations()

@app.post("/dests/add")
async def add_destination(request: Request):
    return await destinations_htmx.add_destination_htmx(request)

@app.post("/dests/save")
async def save_destination(request: Request):
    return await destinations_htmx.save_destination_htmx(request)

@app.post("/dests/delete")
async def delete_destination(name: str = Query("")):
    return destinations_handler.delete_destination(name)

@app.post("/dests/validate")
async def validate_destination(request: Request):
    return await destinations_htmx.validate_destination_htmx(request)

@app.post("/htmx/destination-type-fields")
async def destination_type_fields(request: Request):
    return await destinations_handler.destination_type_fields_htmx(request)

# =============================================================================
# JOBS - CRUD OPERATIONS
# =============================================================================

@app.post("/jobs/save")
async def save_job(request: Request):
    return await job_htmx.save_backup_job_htmx(request)

@app.get("/jobs/delete")
async def delete_job(name: str = Query("")):
    return job_pages.delete_backup_job(name)

@app.get("/jobs/purge")
async def purge_job(name: str = Query("")):
    return job_pages.purge_backup_job(name)

@app.get("/jobs/restore")
async def restore_job(name: str = Query("")):
    return job_pages.restore_backup_job(name)

@app.post("/jobs/validate-source-paths")
async def validate_source_paths(request: Request):
    return await job_htmx.validate_source_paths_htmx(request)

# =============================================================================
# JOBS - EXECUTION
# =============================================================================

@app.post("/jobs/run-backup")
async def run_backup(request: Request):
    return await job_htmx.run_backup_htmx(request)

@app.post("/jobs/dry-run-backup")
async def dry_run_backup(request: Request):
    return await job_htmx.dry_run_backup_htmx(request)

@app.post("/jobs/schedule")
async def schedule_job(request: Request):
    return await job_htmx.schedule_job_htmx(request)

@app.post("/jobs/restore-execute")
async def process_restore_request(request: Request):
    return await job_htmx.process_restore_request_htmx(request)

@app.post("/jobs/check-restore-overwrites")
async def check_restore_overwrites(request: Request):
    return await job_htmx.check_restore_overwrites_htmx(request)

# =============================================================================
# REPOSITORY OPERATIONS
# =============================================================================

@app.get("/check-repository-availability")
async def check_repository_availability(job: str = Query("")):
    return job_htmx.check_repository_availability_htmx(job)

@app.get("/unlock-repository") 
async def unlock_repository_get(job: str = Query("")):
    return destinations_handler.unlock_repository_htmx(job)

@app.post("/unlock-repository")
async def unlock_repository_post(request: Request):
    return await destinations_handler.unlock_repository_post_htmx(request)

@app.post("/initialize-restic-repo")
async def initialize_restic_repo(request: Request):
    return await destinations_handler.initialize_restic_repo_htmx(request)

# =============================================================================
# ADMIN - CONFIG MANAGEMENT
# =============================================================================

@app.post("/preview-config-changes")
async def preview_config_changes(request: Request):
    return await admin_handler.preview_config_changes_htmx(request)

@app.post("/save-config")
async def save_config(request: Request):
    return await admin_handler.save_structured_config_htmx(request)

@app.post("/save-config/raw")
async def save_raw_config(request: Request):
    return await admin_handler.save_raw_config_htmx(request)

@app.post("/admin/check-form-changes")
async def check_form_changes(request: Request):
    return await admin_handler.check_form_changes_htmx(request)

@app.post("/admin/preview-config")
async def preview_config(request: Request):
    return await admin_handler.preview_config_htmx(request)

# =============================================================================
# ADMIN - NOTIFICATIONS
# =============================================================================

@app.post("/admin/add-global-notification-provider")
async def add_global_notification_provider(request: Request):
    return await admin_handler.add_global_notification_provider_htmx(request)

@app.post("/admin/remove-global-notification-provider")
async def remove_global_notification_provider(request: Request):
    return await admin_handler.remove_global_notification_provider_htmx(request)

@app.post("/test-telegram-notification")
async def test_telegram_notification(request: Request):
    return await admin_handler.test_telegram_notification_htmx(request)

@app.post("/test-email-notification")
async def test_email_notification(request: Request):
    return await admin_handler.test_email_notification_htmx(request)

@app.post("/admin/queue-settings")
async def handle_queue_settings(request: Request):
    return await admin_handler.handle_queue_settings_htmx(request)

# =============================================================================
# ADMIN - SYSTEM MANAGEMENT
# =============================================================================

@app.post("/admin/clear-logs")
async def clear_logs(request: Request):
    return await admin_handler.clear_logs_htmx(request)

@app.post("/admin/refresh-logs")
async def refresh_logs(request: Request):
    return await admin_handler.refresh_logs_htmx(request)

@app.post("/admin/cron-field")
async def render_cron_field(request: Request):
    return await admin_handler.render_cron_field_htmx(request)

@app.post("/admin/toggle-password-visibility")
async def toggle_password_visibility(request: Request):
    return await admin_handler.toggle_password_visibility_htmx(request)

# =============================================================================
# LEGACY API ENDPOINTS (To be migrated in Phase 2)
# =============================================================================

@app.get("/scan-network")
async def scan_network_for_rsyncd(range: str = Query("192.168.1.0/24")):
    return destinations_handler.scan_network_for_rsyncd(range)

@app.get("/validate-ssh")
async def validate_ssh_source(source: str = Query("")):
    return origins_handler.validate_ssh_source(source)

@app.get("/restic-repo-info")
async def get_repository_info(job: str = Query("")):
    return services.restic_api.get_repository_info(job)

@app.get("/restic-snapshots")
async def list_snapshots(job: str = Query("")):
    return services.restic_api.list_snapshots(job)

@app.get("/restic-snapshot-stats")
async def get_snapshot_stats(job: str = Query(""), snapshot: str = Query("")):
    return services.restic_api.get_snapshot_stats(job, snapshot)

@app.get("/restic-browse")
async def browse_directory(job: str = Query(""), snapshot: str = Query(""), path: str = Query("/")):
    return services.restic_api.browse_directory(job, snapshot, path)

@app.get("/restic-init")
async def init_repository(job: str = Query("")):
    return services.restic_api.init_repository(job)

@app.get("/filesystem-browse")
async def browse_filesystem(path: str = Query("/")):
    return job_pages.browse_filesystem(path)

@app.get("/jobs")
async def list_jobs():
    return services.handlers['job_scheduler'].list_jobs()

# =============================================================================
# HTMX PARTIALS (Domain-specific AJAX endpoints)
# =============================================================================

# Origins HTMX endpoints
@app.post("/origins/validate-ssh-source")
async def validate_ssh_source_endpoint(request: Request):
    return await origins_handler.validate_ssh_source_htmx(request)

@app.post("/origins/source-fields")
async def render_source_fields_endpoint(request: Request):
    return await origins_handler.render_source_fields_htmx(request)

@app.post("/origins/preview-ssh-config")
async def preview_ssh_config_endpoint(request: Request):
    return await origins_handler.preview_ssh_config_htmx(request)

# Jobs HTMX endpoints
@app.post("/jobs/validate-source-path")
async def validate_source_path_endpoint(request: Request):
    return await job_htmx.validate_source_path_htmx(request)

@app.post("/jobs/add-source-path")
async def add_source_path_endpoint(request: Request):
    return await job_htmx.add_source_path_htmx(request)

@app.post("/jobs/remove-source-path")
async def remove_source_path_endpoint(request: Request):
    return await job_htmx.remove_source_path_htmx(request)

@app.post("/jobs/notification-providers")
async def notification_providers_endpoint(request: Request):
    return await job_htmx.render_notification_providers_htmx(request)

@app.post("/jobs/add-notification-provider")
async def add_notification_provider_endpoint(request: Request):
    return await job_htmx.add_notification_provider_htmx(request)

@app.post("/jobs/remove-notification-provider")
async def remove_notification_provider_endpoint(request: Request):
    return await job_htmx.remove_notification_provider_htmx(request)

@app.post("/jobs/toggle-success-message")
async def toggle_success_message_endpoint(request: Request):
    return await job_htmx.toggle_success_message_htmx(request)

@app.post("/jobs/toggle-failure-message")
async def toggle_failure_message_endpoint(request: Request):
    return await job_htmx.toggle_failure_message_htmx(request)

@app.post("/jobs/restore-target-change")
async def handle_restore_target_change(request: Request):
    return await job_htmx.handle_restore_target_change_htmx(request)

@app.post("/jobs/restore-dry-run-change")
async def handle_restore_dry_run_change(request: Request):
    return await job_htmx.handle_restore_dry_run_change_htmx(request)

# Destinations HTMX endpoints
@app.post("/destinations/dest-fields")
async def render_dest_fields_endpoint(request: Request):
    return await destinations_handler.render_dest_fields_htmx(request)

@app.post("/destinations/restic-fields")
async def render_restic_fields_endpoint(request: Request):
    return await destinations_handler.render_restic_fields_htmx(request)

@app.post("/destinations/validate-ssh-dest")
async def validate_ssh_dest_endpoint(request: Request):
    return await destinations_handler.validate_ssh_dest_htmx(request)

@app.post("/destinations/validate-restic")
async def validate_restic_endpoint(request: Request):
    return await destinations_handler.validate_restic_htmx(request)

@app.post("/destinations/validate-origin-repo-path")
async def validate_origin_repo_path_endpoint(request: Request):
    return await destinations_handler.validate_origin_repo_path_htmx(request)

@app.post("/dests/init-restic-repository")
async def init_restic_repository(request: Request):
    return await destinations_handler.init_restic_repository_htmx(request)

@app.post("/dests/maintenance-fields")
async def render_maintenance_fields(request: Request):
    return await destinations_handler.render_maintenance_fields_htmx(request)

@app.post("/dests/rsyncd-fields")
async def render_rsyncd_fields(request: Request):
    return await destinations_handler.render_rsyncd_fields_htmx(request)

@app.post("/dests/maintenance-toggle")
async def render_maintenance_toggle(request: Request):
    return await destinations_handler.render_maintenance_fields_htmx(request)

@app.post("/dests/restic-repo-fields")
async def render_restic_repo_fields(request: Request):
    return await destinations_handler.render_restic_repo_fields_htmx(request)

@app.post("/dests/restic-uri-preview")
async def generate_restic_uri_preview(request: Request):
    return await destinations_handler.generate_restic_uri_preview_htmx(request)

# =============================================================================
# CORS & STATIC FILES
# =============================================================================

@app.options("/api/{path:path}")
async def handle_options(path: str):
    return services.handle_options()

@app.get("/favicon.ico")
async def favicon():
    return FileResponse('favicon.ico')

# =============================================================================
# STARTUP
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get('PORT', '8080'))
    print(f"Starting Highball on port {port}")
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=port,
        reload=False,
        access_log=True
    )