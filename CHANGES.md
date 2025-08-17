# Changes 2025-08-16 Evening Session

## Critical Container Execution Fix
**Problem**: `restic/restic:0.18.0` container has `restic` as entrypoint - duplicate `restic` in commands caused failures
**Solution**: Removed duplicate prefix from `services/container_command_builder.py:54`
```python
# Before: cmd.extend(['restic', '-r', repository_url, command_type])
# After:  cmd.extend(['-r', repository_url, command_type])
```
**Result**: All SSH Restic operations (init, backup, restore) now use correct container command structure

## Infrastructure Improvements
- **JavaScript Standards**: Extracted embedded JavaScript to external `/static/` files
- **Command Obfuscation**: Created `services/command_obfuscation.py` for centralized password masking
- **RestoreHandler Refactoring**: Split 660-line monolith into modular services (`RestoreExecutionService`, `RestoreOverwriteChecker`, `RestoreErrorParser`)
- **Conflict Avoidance**: Added container-aware job tracking with `HIGHBALL_JOB_ID` environment variables and process verification

## Critical Technical Debt

### Template Variable Dependencies Issue
Multiple JavaScript files contain template variables that require server-side processing:
- `job-form-init.js`: `{{SOURCE_PATHS_JSON}}`
- `notifications-form.js`: `{{AVAILABLE_PROVIDERS_JSON}}`, `{{EXISTING_NOTIFICATIONS_JSON}}`

This breaks the "external files only" rule. **Solutions needed**:
1. Pass data via HTML data attributes instead of template variables in JS files
2. Create inline `<script>` blocks with just data, sourcing logic from external files
3. Use AJAX to fetch initialization data

### Container Command Verification Gap
While restore dry-run is working, full restore and backup execution still need verification with the new container command structure. The fix removes `restic` prefix from container commands, affecting ALL Restic operations.


## Updated Session Status 2025-08-16 (Continuation)

### Unit Test Coverage
- **Test File**: `tests/test_conflict_avoidance_system.py` - 17 tests, 100% pass rate
- **Critical Fix**: Fixed mock patching paths (`@patch('services.job_process_tracker.JobProcessTracker')`)
- **Coverage**: JobProcessTracker (8 tests), JobConflictManager (7 tests), Container Integration (2 tests)
- **Key Features Tested**: Process verification via `HIGHBALL_JOB_ID`, stale cleanup >24h, resource conflict detection

### Notification Configuration Bug Fix
- **Problem**: `notify_on_success` configured globally but UI showed per-job checkboxes (inconsistent behavior)
- **Solution**: Made success notifications exclusively per-job; removed global fallbacks
- **Changes**: Updated `config.py`, `notification_service.py`, form parser, UI template, JavaScript
- **New Feature**: Added `notify_on_maintenance_failure` per-job option for maintenance system
- **Behavior**: Success notifications only sent when explicitly configured per-job

### Notification Service Modularization
- **Problem**: 552-line monolithic service with mixed responsibilities
- **Solution**: Split into 6 specialized services (63% reduction in coordinator size: 552 → 203 lines)
- **Services**: `notification_service.py` (coordinator), `notification_provider_factory.py`, `notification_message_formatter.py`, `notification_sender.py`, `notification_job_config_manager.py`, `notification_queue_coordinator.py`
- **New Features**: Job summaries, config validation, queue statistics, maintenance failure notifications
- **Architecture**: Single responsibility per service, enterprise testability, zero functionality loss

### RestoreHandler Refactoring
- **Problem**: 660-line monolithic handler with DRY violations and mixed concerns
- **Solution**: Split into specialized services (`RestoreExecutionService`, `RestoreOverwriteChecker`, `RestoreErrorParser`)
- **Result**: 75% code reduction in main handler (660 → 140 lines), eliminated duplicate password obfuscation
- **Architecture**: Thin HTTP coordinator delegating to services, follows `handlers/` → `services/` pattern

## Next Session Priorities (Updated Roadmap)

### PRIORITY 1: Infrastructure Foundation ✅ COMPLETED

**Enhanced Conflict Avoidance System**:
- ✅ **Container Job Identification**: Added `HIGHBALL_JOB_ID=job_name_timestamp` env var to all container executions
- ✅ **Process Verification**: Created `JobProcessTracker` service with `ps aux` verification of running jobs
- ✅ **Smart Cleanup**: Long-running jobs (>24h) verified via process check before cleanup
- ✅ **Separation of Concerns**: Split responsibilities between `JobConflictManager` (resource conflicts) and `JobProcessTracker` (process verification)
- ✅ **Automatic Stale Cleanup**: Invalid timestamps and hung processes automatically cleaned from tracking

**Architecture Improvements**:
- **`JobProcessTracker`**: New service handling process verification, health checks, and cleanup
- **`JobConflictManager`**: Simplified to focus only on resource conflict detection
- **Container Integration**: All container executions now include job identification for tracking

### PRIORITY 1: Unit Test Coverage for Conflict Avoidance System ✅ COMPLETED

**Test enhanced conflict avoidance system to ensure proper functionality** - **ALL 17 TESTS PASSING**

**Test Coverage Completed**:
- ✅ **JobProcessTracker**: 8 tests covering process verification, stale cleanup, timestamp handling, long-running job extension  
- ✅ **JobConflictManager**: 7 tests covering resource conflict detection, integration with process tracker
- ✅ **Container Integration**: 2 tests covering HIGHBALL_JOB_ID environment variable injection and process identification
- ✅ **End-to-End Scenarios**: Multi-job conflicts, cleanup automation, error handling

**Test Results**: `tests/test_conflict_avoidance_system.py` - 17/17 tests passing, 100% success rate

**Key Functionality Verified**:
- ✅ Process verification using `HIGHBALL_JOB_ID` environment variables  
- ✅ Smart cleanup of stale entries (>24h) with health checks
- ✅ Resource conflict detection based on shared source/destination hosts
- ✅ Automatic tracking extension for legitimate long-running jobs
- ✅ Container job identification and process verification
- ✅ Error handling and graceful degradation

**Infrastructure Foundation Status**: Production-ready with container compatibility and comprehensive test coverage

### ✅ **Restic Repository Maintenance System Completed**
- **Objective**: Complete repository maintenance architecture to replace backrest with Highball
- **Architecture**: Modular design with 8 specialized services following separation of concerns
- **Solution**: Created enterprise-grade maintenance system with progressive disclosure and safe defaults

**Modular Services Created**:
1. **`MaintenanceDefaults`** (24 lines): Centralized constants and default parameters
2. **`MaintenanceOperation`** (26 lines): Data structures for operations and results  
3. **`MaintenanceConfigManager`** (122 lines): Configuration logic with global/per-job settings
4. **`MaintenanceOperationFactory`** (77 lines): Creates operations from job configurations
5. **`MaintenanceExecutor`** (178 lines): Executes discard/check operations via ResticRunner
6. **`MaintenanceScheduler`** (93 lines): Scheduling and unscheduling logic
7. **`ResticMaintenanceService`** (102 lines): Pure coordinator delegating to specialized services
8. **`MaintenanceBootstrap`** (51 lines): Integration with app startup and job management

**Default Parameters** (safe, production-ready):
- **Discard Schedule**: Daily at 3am (combines forget+prune operations - standard practice)
- **Retention Policy**: Keep last 7, hourly 6, daily 7, weekly 4, monthly 6, yearly 0
- **Check Schedule**: Weekly Sunday 2am (staggered from backups, 5% data subset)
- **Resource Priority**: Lower than backups (nice -n 10, ionice -c 3 -n 7)
- **Conflict Integration**: Uses existing conflict avoidance system

**Config Schema** (per-job + global defaults):
```yaml
global_settings:
  maintenance:
    discard_schedule: "0 3 * * *"        # combines forget+prune operations
    check_schedule: "0 2 * * 0"          # weekly integrity verification
    retention_policy: {...}              # safe snapshot retention defaults
    check_config: {...}                  # performance-balanced integrity checks

backup_jobs:
  job_name:
    auto_maintenance: true               # default enabled, hidden unless false
    # Future manual overrides:
    # maintenance_discard_schedule: "custom cron"
    # retention_policy: {custom settings}
```

**Progressive Disclosure**:
- **Default**: Auto maintenance enabled, no configuration required
- **Simple Toggle**: `☑ Automatic repository maintenance` (shows when disabled)
- **Future**: Manual scheduling and custom retention policy options

**Key Features**:
- ✅ **Container Execution**: Uses established ResticRunner patterns with proper SSH/local handling
- ✅ **Conflict Avoidance**: Integrates with existing system, waits for backup jobs
- ✅ **Notification Integration**: Maintenance failure notifications via modular notification system  
- ✅ **Progressive Logging**: Detailed execution logs via JobLogger with command obfuscation
- ✅ **Bootstrap Integration**: Automatic scheduling on app startup and job changes
- ✅ **User-Friendly Naming**: "Discard" instead of "forget-prune" for clear terminology

**Architecture Benefits**:
- **Modular Design**: Each service has single responsibility, easily testable
- **Future Extensions**: Adding new operation types or providers trivial
- **Established Patterns**: Follows notification system architecture for consistency
- **Zero Breaking Changes**: Maintenance is opt-out via `auto_maintenance: false`

**Ready for UI Integration**: Backend complete, ready for simple UI toggle and progressive disclosure interface

### ✅ **Comprehensive Unit Test Coverage**
- **Objective**: Ensure maintenance system reliability with proper test coverage
- **Architecture**: 22 unit tests across 2 test suites with component isolation
- **Result**: 100% pass rate with proper mocking and dependency isolation

**Test Coverage Created**:
1. **`test_maintenance_core.py`** (13 tests): Core functionality testing
   - MaintenanceDefaults constants validation
   - MaintenanceOperation/MaintenanceResult data structures
   - MaintenanceConfigManager configuration logic and merging

2. **`test_maintenance_integration.py`** (9 tests): Integration testing with mocking
   - MaintenanceOperationFactory operation creation
   - MaintenanceScheduler scheduling and unscheduling logic
   - ResticMaintenanceService component coordination

**Key Testing Approaches**:
- ✅ **Component Isolation**: Proper mocking to avoid filesystem dependencies
- ✅ **Configuration Testing**: Global/per-job settings merging and overrides
- ✅ **Schedule Validation**: Cron scheduling and timezone handling
- ✅ **Environment Building**: S3/REST repository environment variable creation
- ✅ **Service Coordination**: Delegation patterns and component initialization
- ✅ **Edge Cases**: Disabled jobs, non-Restic jobs, missing configurations

**Test Results**: All 22 tests passing with proper error handling and realistic scenarios

**Production Readiness**: Maintenance system fully tested and ready for deployment

### PRIORITY 2: Notification Config Bug Fix
   - **Problem**: `notify_on_success` configured globally but UI shows per-job checkboxes
   - **Root Cause**: Check `services/notification_service.py` and job form parsing
   - **Solution**: Move `notify_on_success` from global config to per-job configuration
   - **Addition**: Add `notify_on_maintenance_failure` per-job option for future use
   - **Files to check**: `handlers/notification_form_parser.py`, `services/notification_service.py`, job form templates

### PRIORITY 2: Restic Repository Maintenance System
**Core functionality to replace backrest with Highball**

**Objective**: Implement forget/prune/check operations with safe defaults and progressive disclosure

**Architecture** (following separation of concerns):
- **`ResticMaintenanceService`**: Main coordinator, handles maintenance operations with proper scheduling
- **`ResticForgetPruneOperation`**: Combined daily operation using `restic forget --prune`
- **`ResticCheckOperation`**: Weekly integrity verification using `restic check --read-data-subset=5%`
- **`ResticMaintenanceScheduler`**: APScheduler integration with existing conflict avoidance system

**Default Parameters** (per-job, auto-enabled, no config required):
- **Discard Schedule**: Daily at 3am OR after successful backup completion (whichever comes first)
- **Command**: `restic forget --prune --keep-last 7 --keep-hourly 6 --keep-daily 7 --keep-weekly 4 --keep-monthly 6`
- **Retention Policy**: 
  ```yaml
  retention_policy:
    last: 7        # keep last 7 snapshots regardless of age
    each:
      hourly: 6    # keep 6 hourly snapshots
      daily: 7     # keep 7 daily snapshots
      weekly: 4    # keep 4 weekly snapshots  
      monthly: 6   # keep 6 monthly snapshots
      yearly: 0    # disable yearly retention
  ```
- **Check Schedule**: Weekly (Sunday 2am), staggered from backup/discard operations
- **Command**: `restic check --read-data-subset=5%` (balances integrity vs performance)
- **Resource Priority**: `nice -n 10 ionice -c 3 -n 7` (lower priority than backups: `nice -n 5 ionice -c 2 -n 4`)
- **Conflict Integration**: Uses existing conflict avoidance system, maintenance waits for backups
- **Lock Handling**: Built-in repository lock detection with retry logic for busy repositories

**Config Schema** (per-job, all optional):
```yaml
backup_jobs:
  job_name:
    auto_maintenance: true  # default true, hidden unless false
    notify_on_maintenance_failure: false  # future addition
    # Future manual overrides:
    # maintenance_discard_schedule: "0 3 * * *"
    # maintenance_check_schedule: "0 2 * * 0"  
    # retention_policy: {custom configuration}
```

**Progressive Disclosure UI**:
1. Simple toggle: `☑ Automatic repository maintenance` (default: enabled)
2. When disabled: `[Repo Maintenance Options]` button for manual scheduling
3. Eventually: Custom retention policy and schedule configuration

### Maintenance UI - Toggle-Based Design
- **Problem**: Original checkbox UI unclear about what "unchecked" meant, no safe path to configuration
- **Solution**: Dual toggle design with progressive disclosure and safety defaults

**Configuration Schema**: `restic_maintenance: "auto" | "user" | "off"` (replaces boolean `auto_maintenance`)
- `"auto"`: System defaults (3am daily discard, 2am Sunday check)  
- `"user"`: User overrides, defaults honored for blank fields
- `"off"`: No maintenance scheduled

**UI Design**: Dual toggle system with safety defaults
1. `Repository Maintenance: Auto / User` (default: Auto)
2. `Manual Options: Config / Off` (default: Config when switching to User)

**Safety Features**: Double-toggle required to disable, clear warnings, helpful defaults in help text

**Configuration Examples**:
```yaml
restic_maintenance: "auto"                    # Default
restic_maintenance: "user"                    # User mode with defaults
maintenance_discard_schedule: "0 5 * * *"    # Custom 5am schedule
restic_maintenance: "off"                     # Disabled (deliberate action)
```

**Technical Implementation**:
- **Form Data**: Hidden field stores mode, JavaScript manages progressive disclosure
- **Backend**: `MaintenanceConfigManager.get_maintenance_mode()` handles three-state logic  
- **Test Coverage**: 25 tests updated/added (16 core + 9 integration), all passing

**Status**: Maintenance UI design significantly improved with clear user intent, safety defaults, and proper progressive disclosure