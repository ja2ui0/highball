# Restore Functionality - IMPLEMENTATION COMPLETE ✅

## Status: Ready for Testing

**Implementation Complete**: Core restore functionality fully implemented with clean HTML structure and modular JavaScript architecture
**Next Step**: End-to-end testing of restore operations (dry run and actual restore execution)

## Core Architecture

**Dashboard-centric workflow**: Restore initiated from dashboard "Inspect" buttons → `/inspect?name=<jobname>` → integrated restore interface
**MVP Provider**: Restic-only initially, modular JavaScript architecture designed for multi-provider expansion  
**Restore Location**: `/restore` directory in container (ephemeral for development, bind-mount ready for production)

## User Workflow

1. **Dashboard** → Click "Inspect" button for any job
2. **Inspect Page** (`/inspect?name=<jobname>`) contains:
   - Job logs and status information
   - Backup browser with restore controls
   - Restore progress display
3. **Restore Selection**:
   - Browse snapshots (latest first) 
   - Use existing checkbox system for granular file/folder selection
   - "Select All" button for full snapshot restore (Restic native)
4. **Restore Options**:
   - "Restore to Highball" target (files restored to `/restore` in container)
   - Dry run capability (enabled by default for safety)
   - Password confirmation modal for security
5. **Progress Monitoring**: Real-time progress display with phase updates

## Technical Implementation - COMPLETED ✅

### Core Components

**Backend**:
- ✅ `/handlers/restore_handler.py` - Complete RestoreHandler with Restic command building
- ✅ `/handlers/inspect_handler.py` - Per-job inspection hub 
- ✅ `/templates/job_inspect.html` - Integrated interface with restore controls
- ✅ Routes: `GET /inspect?name=<jobname>`, `POST /restore`

**Frontend - Modular JavaScript Architecture**:
- ✅ `/static/restore-core.js` - Generic restore UI and provider orchestration
- ✅ `/static/restore-restic.js` - Restic-specific implementation
- ✅ Extensible provider registration system for future backup types

**UI Components**:
- ✅ Modal password confirmation with restore summary
- ✅ Progress modal with phase-based updates  
- ✅ Restore controls integrated into backup browser
- ✅ CSS styling using existing theme variables

### Key Features

**Restore Execution**:
- ✅ Dry run support with command preview and output display
- ✅ Actual restore with background execution and progress tracking
- ✅ Password validation for security
- ✅ Error handling with user-friendly messages

**Command Building**:
- ✅ Restic restore command construction with proper repository handling
- ✅ Support for both full snapshot restore and granular file selection
- ✅ Include/exclude path handling for selected items
- ✅ Proper environment variable and password management

**Progress Monitoring**:
- ✅ Background restore execution with threading
- ✅ Progress tracking and status updates
- ✅ Job logger integration for restore operation tracking
- ✅ Simulated progress phases (ready for `restic --json` parsing)

## Implementation Phases - ALL COMPLETED ✅

### ✅ Phase 1: Core Infrastructure (COMPLETED)
1. ✅ Created `/inspect?name=<jobname>` endpoint and InspectHandler
2. ✅ Moved job logs to per-job inspect pages, `/logs` → `/dev`
3. ✅ Extended backup browser with restore controls and "Select All" toggle
4. ✅ Implemented restore UI with "Restore to Highball" target and dry run (default on)
5. ✅ Dashboard "History" → "Inspect" buttons, preserved job status information
6. ✅ Separated system debugging to `/dev` with network scanner

### ✅ Phase 2: Restore Execution (COMPLETED)
1. ✅ Created RestoreHandler for processing restore requests
2. ✅ Implemented Restic restore command building and execution
3. ✅ Background restore execution with progress tracking infrastructure
4. ✅ Modular JavaScript architecture with provider system
5. ✅ Modal password confirmation for restore operations
6. ✅ Complete unit test coverage (13/13 RestoreHandler, 9/9 JavaScript, 13/13 multi-path)

### Phase 3: Future Enhancements
1. **Real Progress Parsing**: Implement `restic restore --json` output parsing for accurate progress
2. **Dashboard Status Integration**: Show "Restoring... N%" in main dashboard job table
3. **Restore to Source**: Add option to restore files back to original locations
4. **Multi-Provider Support**: Extend to rsync, borg, kopia using established provider pattern
5. **Advanced Features**: Include/exclude patterns, progress notifications, single file download

## File Structure - COMPLETED ✅

**Routes**:
- ✅ `GET /inspect?name=<jobname>` → Job inspection hub (InspectHandler)
- ✅ `POST /restore` → Execute restore operation (RestoreHandler) 
- ✅ `GET /dev` → System debugging (LogsHandler.show_dev_logs)

**Backend Files**:
- ✅ `/handlers/restore_handler.py` → Complete restore request processing
- ✅ `/handlers/inspect_handler.py` → Per-job inspection interface
- ✅ `/templates/job_inspect.html` → Integrated job status, backup browser, restore controls, logs
- ✅ Updated `/app.py` → Routing and handler integration

**Frontend Files**:
- ✅ `/static/restore-core.js` → Generic restore functionality and provider orchestration  
- ✅ `/static/restore-restic.js` → Restic-specific restore implementation
- ✅ CSS additions in `/static/style.css` and theme files for modal and progress styling

**Testing**:
- ✅ `/tests/test_restore_handler.py` → Comprehensive RestoreHandler testing (13 tests)
- ✅ `/tests/test_restore_core_js.py` → JavaScript architecture validation (9 tests)
- ✅ `/tests/test_backup_command_builder_multipath.py` → Multi-path support verification (13 tests)

## Technical Notes

**Form Data Handling**:
- **Current Implementation**: Multipart form data (`multipart/form-data`)
- **Frontend**: `FormData` in `restore-restic.js` for form data building
- **Backend**: `cgi.FieldStorage` in `app.py` with backward compatibility for URL-encoded
- **Benefits**: Better array handling, enhanced security, file upload ready

**Modular JavaScript Architecture**:
- Provider registration system allows easy addition of new backup types
- Clean separation between UI logic (restore-core.js) and provider-specific logic
- Extensible interface pattern for consistent provider implementation

**Restic Integration**:
- Complete command building with repository URI, password, and path handling
- Dry run and actual restore operation support
- Background execution with progress tracking infrastructure
- Password obfuscation in logs (`echo "***"` replacement)
- Ready for `restic restore --json` progress parsing implementation

**Security & Safety**:
- **Intelligent Overwrite Protection**: Pre-flight checks determine if source files would be overwritten
- **Progressive Disclosure Confirmation**: Only shows confirmation when actual risk exists
- **Restore Target Options**: Safe container restore (`/restore`) vs. risky source restore (original paths)
- **Smart Confirmation Text**: User types "OVERWRITE" to confirm data replacement operations
- **No Modal State Management**: Eliminated race conditions with inline progressive disclosure UI
- **Dry Run Default**: Enabled by default to prevent accidental data operations
- **Form Validation**: Real-time validation and error handling throughout workflow

## Architecture Implementation Plan

**Provider Separation Design**: 
- **RestoreHandler**: Provider-agnostic orchestration, overwrite detection, validation, progress tracking
- **ResticRunner**: Restic-specific command building and execution (backup AND restore operations)
- **Future Providers**: BorgRunner, KopiaRunner follow same pattern

**SSH Restore Implementation**:
1. **Extend ResticRunner**: Add `CommandType.RESTORE` support and `plan_restore_job()` method
2. **Command Building**: Use existing SSH patterns (`to_ssh_command()`) for restore operations
3. **Target Host Logic**: For "restore to source", SSH to source host and run restore there
4. **Overwrite Detection**: SSH to target host, run `find` commands to check file existence

**Command Execution Pattern**:
```bash
# SSH Restore to Source
ssh user@source_host "export RESTIC_PASSWORD='***'; restic -r repo_url restore snapshot_id --target /"

# Local Restore to Highball  
restic -r repo_url restore snapshot_id --target /restore
```

**Current Session Tasks**:
1. **ResticRunner Extension**: Add RESTORE command type and planning method
2. **RestoreHandler Refactor**: Replace manual command building with ResticRunner calls
3. **SSH Overwrite Detection**: Implement remote file existence checking
4. **Unified Architecture**: Ensure all restore operations use consistent patterns

## SSH Restore Implementation Plan

### Phase 1: Extend ResticRunner
1. **Add `plan_restore_job()` method** after `plan_backup_job()` in `restic_runner.py`
   - Reuse existing `_determine_transport()`, `_build_repository_url()`, `_build_environment()` 
   - Add restore-specific args building: `--target`, `--include` paths, `--dry-run`
   - Handle both SSH and LOCAL transport types

2. **Update `to_ssh_command()` method** to handle RESTORE command type
   - Add restore path handling (no source_paths for restore)
   - Include target directory and selected paths in args

### Phase 2: Refactor RestoreHandler
3. **Replace `_build_restic_restore_command()`** with ResticRunner calls
   - Use `restic_runner.plan_restore_job()` for all restore operations
   - Execute commands via `command.to_ssh_command()` or `command.to_local_command()`
   - Maintain existing dry run and progress tracking

4. **Implement SSH overwrite detection** in `_check_destination_files_exist()`
   - Build SSH commands to run `find` on target hosts
   - Use same SSH connection patterns as ResticRunner
   - Keep logic in RestoreHandler (provider-agnostic)

### Phase 3: Target Host Logic
5. **Fix restore target determination**
   - "restore to source": Use source host credentials, target "/"
   - "restore to highball": Use local execution, target "/restore"
   - Handle both local and SSH source types correctly

**Files to Modify:**
- `services/restic_runner.py`: Add restore planning
- `handlers/restore_handler.py`: Replace manual command building
- Test restore to source with yeti job (SSH source)

**Maintains DRY principles and sets up clean provider separation for future borg/kopia integration.**

## Current State - Implementation In Progress

**✅ Implementation Complete**:
- **Progressive Disclosure UI**: Eliminated modals, implemented intelligent confirmation system
- **Overwrite Risk Assessment**: Pre-flight endpoint `/check-restore-overwrites` with filesystem checks
- **Dual Restore Targets**: Safe Highball container (`/restore`) and risky source location restore
- **Smart Confirmation Logic**: Only requires "OVERWRITE" confirmation when files would be replaced
- **Multipart Form Handling**: Complete conversion from URL-encoded with backward compatibility
- **Clean JavaScript Architecture**: No modal state management, inline progress display
- **Backend Restore Logic**: Handles both container and source restore targets via restic commands
- **Comprehensive Testing**: Unit test coverage for multipart forms and restore logic (43/43 tests passing)

**🧪 Next Steps - Testing Phase**:
1. **End-to-End Testing**: Test actual restore operations (dry run and execution)
2. **Error Handling**: Verify proper error display and recovery
3. **Progress Monitoring**: Confirm simulated progress works correctly
4. **Modal Flow**: Test password confirmation and restore workflow

**🚀 Future Enhancements**:
1. **Real Progress Parsing**: Replace simulated progress with actual `restic restore --json` output parsing
2. **Dashboard Integration**: Add restore status polling and display "Restoring... N%" in main dashboard job table  
3. **Provider Expansion**: Add rsync restore support using established modular architecture
4. **Advanced Overwrite Detection**: Detect timestamp conflicts, size differences, content changes
5. **Restore History**: Track restore operations with detailed logs and rollback capabilities
6. **Single File Download**: Direct file download from repository browser without full restore

## Testing Readiness Checklist

- ✅ HTML structure fixed and containers properly nested
- ✅ Selection controls (Select All/Clear) always visible  
- ✅ Job logs properly contained within main page layout
- ✅ Debugging code cleaned up and removed
- ✅ Modal system with proper `.hidden` CSS class
- ✅ JavaScript provider architecture modular and extensible
- ✅ Unit tests passing for all core components
- 🧪 **Ready for restore operation testing**
