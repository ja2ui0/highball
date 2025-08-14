# Restore Functionality Implementation Plan

## Core Architecture

**Dashboard-centric workflow**: Restore initiated from dashboard "Inspect" buttons → `/inspect?name=<jobname>` → integrated restore interface
**MVP Provider**: Restic-only initially, architecture designed for multi-provider expansion  
**Restore Location**: `/restore` directory in container (ephemeral for development, bind-mount ready for production)

## User Workflow

1. **Dashboard** → Click "Inspect" button for any job
2. **Inspect Page** (`/inspect?name=<jobname>`) contains:
   - Job logs (moved from current `/logs` page)
   - Backup browser with restore controls
   - Restore status/progress display
3. **Restore Selection**:
   - Browse snapshots (latest first) 
   - Use existing checkbox system for granular file/folder selection
   - "Select All" button for full snapshot restore (Restic native)
4. **Restore Target**: Start with "Restore to Highball" (MVP), expand to source/download later
5. **Security**: Modal password confirmation for restore operations

## Dashboard Integration  

**Job Status Changes**:
- `Enabled` → `Paused` during restore operations
- Status shows `Restoring... N%` with progress from `restic restore --json`
- Dashboard buttons adapt: `RUN`→`KILL`, `DRY RUN`→`FOLLOW`, `EDIT` hidden during restore

## Technical Implementation

**New Components**:
- `/handlers/restore_handler.py` - RestoreHandler following BackupHandler pattern
- `/services/restore_service.py` - Background restore execution with progress parsing
- `/templates/job_inspect.html` - New inspect page template
- Route: `GET /inspect?name=<jobname>` (replaces current `/logs` functionality)

**Existing Code Reuse**:
- Backup browser tree structure and checkbox system (no changes needed)
- Job logger system (extend for restore tracking)
- Background job execution patterns
- Modal UI patterns from job forms

**Progress Monitoring**:
- Parse `restic restore --json` output for file counts and progress
- Update job status with restore progress percentage  
- Real-time progress display on dashboard

## Implementation Phases

### ✅ Phase 1: Core Infrastructure (COMPLETED)
1. ✅ Created `/inspect?name=<jobname>` endpoint and InspectHandler
2. ✅ Moved job logs to per-job inspect pages, `/logs` → `/dev`
3. ✅ Extended backup browser with restore controls and "Select All" toggle
4. ✅ Implemented restore UI with "Restore to Highball" target and dry run (default on)
5. ✅ Dashboard "History" → "Inspect" buttons, preserved job status information
6. ✅ Separated system debugging to `/dev` with network scanner

### 🚧 Phase 2: Restore Execution (NEXT)
1. Create RestoreHandler for processing restore requests
2. Implement Restic restore command building and execution
3. Background restore execution with `restic restore --json` progress parsing
4. Dashboard status integration with "Restoring... N%" progress display
5. Modal password confirmation for restore operations
6. Job status changes: `Enabled` → `Paused` during restore

### Phase 3: Polish & Expand (FUTURE)
1. Restore to source target
2. Single file download capability
3. Multi-provider architecture (rsync, etc.)
4. Advanced features (include/exclude patterns, progress notifications)

## File Structure Changes

**✅ Completed Routes**:
- ✅ `GET /inspect?name=<jobname>` → Job inspection hub (InspectHandler)
- ✅ `GET /dev` → System debugging (LogsHandler.show_dev_logs)
- ✅ Dashboard "History" → "Inspect" buttons (always available)

**🚧 Next Routes**:
- `POST /restore` → Execute restore operation (RestoreHandler)
- Dashboard job status integration for restore progress

**✅ Completed Files**:
- ✅ `/handlers/inspect_handler.py` → Per-job inspection
- ✅ `/templates/job_inspect.html` → Integrated job status, backup browser, restore controls, logs
- ✅ `/templates/dev_logs.html` → System debugging with network scanner
- ✅ Updated `/handlers/job_display.py` → Inspect links
- ✅ Updated `/app.py` → Routing for new endpoints

## Technical Notes

**Restic Integration**:
- Use `restic restore --json` for progress monitoring
- Support both full snapshot restore and granular file selection
- Password required for restore operations (security confirmation)

**Architecture Patterns**:
- Follow existing BackupHandler/BackupExecutor separation of concerns
- Reuse job conflict detection system
- Extend job logger for restore operation tracking  
- Modal password pattern from existing job forms
