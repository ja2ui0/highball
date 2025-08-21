# Changes 2025-08-21 - Same-as-Origin Repository Pattern & Critical Fixes

## 2025-08-21: Same-as-Origin Repository Implementation

### New Feature: Same-as-Origin Repository Type
**Purpose**: Support backing up to repository on same host as source (useful for file rollbacks like Timeshift)
**Use Case**: SSH source → local repository on origin host filesystem

**Implementation**:
- Added `same_as_origin` repository type to `RESTIC_REPOSITORY_TYPE_SCHEMAS`
- Schema field: `origin_repo_path` for repository path on origin host
- URI construction returns `origin_repo_path` directly

### Architecture Changes

#### SSH Context Intelligence 
**Enhanced `_should_use_ssh()` in ResticExecutionService**:
```python
# same_as_origin ALWAYS uses SSH regardless of operation type
if dest_config.get('repo_type') == 'same_as_origin':
    return True
```

#### Volume Mounting Strategy
**Dual volume mounting for same-as-origin operations**:
- Repository: `-v {repo_uri}:{repo_uri}` (read-write)
- Source paths: `-v {source_path}:{source_path}:ro` (backup) or RW (restore)

#### Restore Target Logic
**Same-as-origin restores use container root (`/`) as target**:
- Files in backup: `/home/user/data/file.txt` 
- Mounted paths: `-v /home/user/data:/home/user/data`
- Target: `/` → Files restore to mounted locations correctly

### Critical Bug Fixes

#### Missing `backup` Command
**Issue**: `ResticArgumentBuilder.build_backup_args()` missing `backup` command
**Fix**: Added `backup` as first argument in command construction

#### Volume Mounting Regression
**Issue**: Source path mounting only applied to same-as-origin, broke SSH→S3
**Fix**: Moved source mounting outside conditional to apply to ALL SSH operations

#### SSH Context for UI Operations  
**Issue**: `list_snapshots_with_ssh()` didn't use SSH for same-as-origin
**Fix**: Added same-as-origin check to force SSH execution for UI operations

#### Restore Import Error
**Issue**: `handlers/operations.py` importing from wrong module path
**Fix**: Updated import from `services.restic_repository_service` to `models.backup`

### Testing Results
**SSH→same-as-origin**: Backup (1.19s), restore with file overwrite verified
**SSH→S3**: Backup (3.29s), restore (8 files/dirs) verified - confirmed no regression
**Overwrite protection**: Restore operations correctly warn and restore changed files only

### Files Modified
- `models/backup.py`: Added schema, URI construction, fixed missing backup command
- `services/execution.py`: Enhanced SSH context detection, volume mounting  
- `handlers/operations.py`: Updated restore logic, fixed imports
- `config/config.yaml`: Added test job with `container_runtime: docker`

---

## Previous Session Context (2025-08-20)

### Schema-Driven Architecture Migration
**Eliminated 100+ lines of hardcoded if/elif logic** using:
- `SOURCE_TYPE_SCHEMAS` for source type dispatch
- Enhanced `DESTINATION_TYPE_SCHEMAS` with complete field coverage
- Type-based validation and form rendering

### Job Form System Enhancements
**Dual Storage Pattern**: Store both URIs (execution) and discrete fields (editing)
**Smart Edit Forms**: Auto-populate fields from config, dynamic button text, HTMX change detection
**Complete S3 Support**: Added region, access_key, secret_key, endpoint fields
**Three-Mode Maintenance**: `restic_maintenance: auto|user|off` (replaced boolean)

### SSH+S3 Integration Completed
**From COMPREHENSIVE_TEST_RESULTS.md updates**:
- Fixed SSH container S3 credentials via centralized `ResticArgumentBuilder.build_ssh_environment_flags()`
- Fixed volume mounting pattern from `/backup-source-N` to `{path}:{path}:ro`
- SSH→S3 backup execution tested end-to-end (3.4s completion)
- S3 repository initialization via SSH verified
- **Status**: Both LOCAL→S3 and SSH→S3 working

### Template System Migration  
**Complete Jinja2 conversion**: All templates from legacy `{{VARIABLE}}` to Jinja2 conditionals
**Modular partial system**: 50+ reusable template components

### Critical 2025-08-20 Bug Fixes
- **S3 URI Construction**: Fixed format to `s3:https://endpoint/bucket/prefix`
- **Restic Include Patterns**: Removed invalid `--include` flags  
- **Job Name Tagging**: Added job_name to job_config for snapshot tagging
- **Centralized S3 Credentials**: Unified environment builders

### Open Items
**UX Improvements**:
- Context-aware forms (hide include/exclude for restic destinations) 
- Dashboard status clarity (jobs show "Enabled" when running)

**Testing Gaps**:
- Real backup execution verification
- Notification system testing
- Maintenance operations testing

---

## 2025-08-21 Continued: Error Handling Refactor

### Error Handling Decorator Implementation
**Applied `@handle_page_errors` decorator to 17 methods** in `handlers/pages.py`, eliminating repetitive try/catch blocks:
- Fixed broken `show_edit_job_form` indentation 
- Tested each method individually with `./rr` and curl
- **Result**: Methods now focus on business logic, centralized error handling

**Next Phase Options**: HTTP method separation (GETHandlers/POSTHandlers/ValidationHandlers) or template data builder extraction