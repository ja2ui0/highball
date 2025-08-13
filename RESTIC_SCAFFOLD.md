# Restic Provider Scaffold

This document describes the Restic backup provider scaffold implementation and the next steps required for full execution.

## Architecture Overview

The Restic provider follows the existing Highball patterns with these key components:

### Core Components
- **`services/restic_runner.py`** - Command planning service, builds SSH execution plans for restic binary
- **`handlers/restic_validator.py`** - Validation logic for Restic configurations and binary availability  
- **`handlers/restic_form_parser.py`** - Form data parsing for Restic-specific fields
- **`handlers/restic_handler.py`** - HTTP handlers for planning and validation endpoints

### Modular Form Parser Architecture
- **`handlers/local_form_parser.py`** - Local filesystem form parsing
- **`handlers/ssh_form_parser.py`** - SSH source/destination form parsing
- **`handlers/rsyncd_form_parser.py`** - Rsyncd destination form parsing
- **`handlers/restic_form_parser.py`** - Restic destination form parsing
- **`handlers/job_form_parser.py`** - Main parser delegates to specialized parsers

### Integration Points
- **`handlers/job_validator.py`** - Updated to delegate Restic validation
- **`handlers/job_form_parser.py`** - Refactored to use modular parsing delegation
- **`handlers/job_display.py`** - Updated to display Restic job destinations
- **`services/form_data_service.py`** - Refactored to modular architecture with nested dataclasses for maintainability
- **`app.py`** - Updated with Restic routing and handler initialization

## Implicit Enablement Pattern

The Restic provider uses **implicit enablement** - no feature flags required:
- Restic appears in destination dropdown only when Restic jobs exist in config OR when explicitly selected
- Detection via `JobFormData.should_show_restic_option(backup_config)`
- Clean auto-discovery without configuration complexity

## Command Planning Abstraction

The scaffold implements a **planning-first architecture**:

### ResticPlan Structure
```python
@dataclass
class ResticPlan:
    job_name: str
    commands: List[ResticCommand]  # SSH executable commands
    estimated_duration_minutes: int
    requires_binary_check: bool = True
    requires_init: bool = False
    retention_policy: Optional[Dict] = None
```

### Transport Methods
- **SSH**: Execute restic binary on source system via SSH (primary method)
- **Local**: Execute restic locally in container (fallback)
- **Container**: Reserved for future container-based execution

### Endpoints Return 202 + Plan
All execution endpoints return HTTP 202 with structured plan payload instead of executing:
- `/plan-restic-backup` - Generate backup execution plan
- `/validate-restic` - Validate repository configuration
- `/check-restic-binary` - Verify restic binary availability
- `/restic-repo-info` - Get repository information

## Current Implementation Status

### ✅ Completed (Scaffold + UI)
- [x] Restic job schema and validation
- [x] Form parsing and UI integration  
- [x] Command planning abstraction
- [x] HTTP handlers with 202 responses
- [x] Routing integration
- [x] Minimal event logging
- [x] Job CRUD operations (create, edit, list, delete)
- [x] Implicit enablement pattern
- [x] Modular form parser architecture (all destination types)
- [x] Comprehensive test suite coverage
- [x] **Complete Restic HTML templates** - Full Restic job creation and editing UI with all repository types
- [x] **Restic form validation endpoint** - `/validate-restic-form` for real-time validation during job creation  
- [x] **Restic URI preview generation** - Live URI building for REST, S3, rclone, SFTP repository types
- [x] **Restic JavaScript module** - `job-form-restic.js` handles all Restic-specific form logic
- [x] **Restic execution implementation** - `ResticCommandBuilder` and `CommandBuilderFactory` enable actual Restic job execution

### ✅ Recently Completed

#### 1. Real Connectivity Validation
**Status**: ✅ **COMPLETE**
- ✅ Network connectivity testing to REST servers
- ✅ Repository access validation with credentials  
- ✅ Binary availability checking on source systems
- ✅ Actual restic repository operations (snapshots, repository status)
- ✅ Meaningful error messages for connection failures
- ✅ Detailed validation results showing existing repositories with snapshot counts
- ✅ Clear binary missing detection with installation instructions

### ⚠️ Next Implementation Steps

#### 1. Enhanced Execution Features
**Current**: Basic Restic execution with repository initialization and backup commands
**Required**: 
- JSON progress parsing from restic output
- Real-time status updates and progress reporting
- Enhanced error handling and retry logic

#### 3. Binary Bootstrap and Management
**Current**: Basic availability check via SSH
**Required**:
- Automatic restic binary installation on source systems
- Version compatibility checking
- Binary update mechanism
- Package manager integration (apt, yum, brew, etc.)
- Manual installation instructions and verification

#### 4. Secret Management
**Current**: Passwords stored in plain text in config
**Required**:
- Encrypted secret storage
- Environment variable injection pattern
- Secret rotation capabilities
- Integration with external secret managers (optional)
- Secure transmission over SSH

#### 5. Retention Policy and Safety
**Current**: Basic retention parsing
**Required**:
- Retention policy validation and preview
- Safety checks before destructive operations
- Backup verification after completion
- Repository health monitoring
- Automatic repository maintenance scheduling

#### 6. Advanced Features
**Required for production**:
- Incremental backup progress tracking
- Repository snapshots listing and browsing
- Restore functionality and file recovery
- Repository repair and maintenance
- Performance monitoring and optimization
- Multi-repository support

#### 7. Advanced Retention and Maintenance
**Enhanced retention policies**:
- Granular time-bucketed retention (hourly, daily, weekly, monthly, yearly)
- Repository maintenance policies with separate schedules
- Automated prune and check operations
- Repository health monitoring and alerts

#### 8. Repository Lock Management
**Lock detection and investigation**:
- Repository lock detection and status reporting
- Lock investigation tools (who, when, what process)
- Stale lock detection and alerting
- Manual lock removal with safety checks
- Lock troubleshooting guidance and logs

#### 9. Process Control and Performance (Low Priority)
**System optimization features**:
- CPU priority control (nice levels)
- I/O priority control (ionice)
- Resource usage monitoring
- Backup performance optimization

#### 10. Restore and Recovery Features
**Roadmap for restore capabilities**:
- Review and restore restic snapshots to source system
- Review and restore restic snapshots to arbitrary path
- Review and restore restic snapshots for download
- Review and restore rsync targets to source system
- Review and restore rsync targets to arbitrary path
- Review and restore rsync targets for download
- Unified restore interface across backup types
- Restore progress tracking and validation

## Configuration Schema

### Minimal Restic Job
```yaml
backup_jobs:
  my-restic-backup:
    source_type: "ssh"
    source_config:
      hostname: "source.example.com"
      username: "backup"
      path: "/home/user/documents"
    dest_type: "restic"
    dest_config:
      repo_type: "sftp"
      repo_location: "backup@storage.example.com:/backup/repo"
      password: "repository-password"
      auto_init: true
      retention_policy:
        keep_daily: 7
        keep_weekly: 4
        keep_monthly: 12
    schedule: "daily"
    enabled: true
```

### Repository Types Supported
- **local**: Local filesystem path
- **sftp**: SFTP remote repository
- **s3**: Amazon S3 bucket (requires AWS credentials)

## Testing and Validation

### Basic Testing Checklist
- [x] App starts without errors with Restic scaffold
- [x] Restic option appears in UI when appropriate (implicit enablement)
- [x] Restic job can be created and saved (backend complete)
- [x] Restic job appears in dashboard listing
- [x] Restic job can be edited and deleted
- [x] Planning endpoints return 202 with valid JSON
- [x] Validation endpoints work correctly
- [x] Binary check functions properly
- [x] Job logs show planning events
- [x] Modular form parsing works for all destination types

### Integration Testing
- [x] Existing rsync jobs continue to work
- [x] No regression in SSH or local job functionality
- [x] Configuration loading/saving works with Restic jobs
- [x] Job conflict resolution includes Restic jobs
- [x] Form parser refactoring maintains backward compatibility

### Test Suite Coverage
- [x] **`tests/test_restic_scaffold.py`** - Complete Restic provider testing
- [x] **`tests/test_form_parsers.py`** - Modular form parser validation
- [x] All individual component tests pass
- [x] Integration flow tests pass
- [x] Error handling and edge cases covered

## Dependencies

### Current Dependencies (Minimal)
- No new Python packages required
- Uses existing `dataclasses`, `subprocess`, `pathlib` patterns
- Follows existing validation and logging architecture

### Future Dependencies (For Execution)
- Consider `pexpect` for interactive SSH session management
- JSON streaming parser for large restic output
- Proper async/await patterns for long-running operations

### rclone Requirements and Setup

For rclone repository type, users must ensure rclone is available and configured on the source system:

**Binary Installation:**
- rclone binary must be installed on the source system where restic runs
- Available via package managers: `apt install rclone`, `brew install rclone`, etc.
- Or download from https://rclone.org/

**Configuration Required:**
- Users must run `rclone config` on source system to configure remotes
- Configuration stored in `~/.config/rclone/rclone.conf`
- Common remotes: Google Drive, Dropbox, OneDrive, S3-compatible services, etc.

**Testing Setup:**
- Verify with `rclone listremotes` to see configured remotes
- Test access with `rclone lsd remote:` to list directories
- Validate before using with restic backups

**Documentation Needed:**
- User guide for rclone setup and configuration
- Common remote configuration examples
- Troubleshooting guide for rclone connection issues

## Simplified Form Architecture

### Organic, Context-Aware Forms

The Restic implementation uses **structured input → URI building** instead of raw URI input:

**Form Design Principles:**
- Show only relevant fields per repository type (no irrelevant options)
- Build URIs programmatically from structured inputs (no regex parsing)
- Display generated URI in help text for transparency
- Make credentials optional where appropriate (e.g., REST servers may not require auth)
- Store structured data for future secrets management

**Repository Type Examples:**

**REST Repository:**
```
Hostname: [backup.example.com] (required)
Port: [8000] (optional, default 8000)
Path: [/backups] (optional)
Use HTTPS: [✓] (checkbox)
Username: [] (optional)
Password: [] (optional)

Generated URI: rest:https://backup.example.com:8000/backups
```

**S3 Repository:**
```
Endpoint: [s3.amazonaws.com] (default)
Bucket: [my-backup-bucket] (required)
Prefix: [restic] (optional)
AWS Access Key: [] (required)
AWS Secret Key: [] (required)

Generated URI: s3:s3.amazonaws.com/my-backup-bucket/restic
```

**rclone Repository:**
```
Remote Name: [gdrive] (required - from rclone config)
Path: [backups] (optional, default: backups)

Generated URI: rclone:gdrive:backups
Note: Ensure rclone is configured on source system
```

**Architecture Benefits:**
- No URI parsing complexity or regex validation
- Eliminates user URI construction errors
- Cleaner validation and error messages
- Ready for future secrets encryption
- Follows Backrest-style patterns

## Development Guidelines

### Code Style Consistency
- Follow existing PEP 8 patterns
- Use dataclasses for structured data
- Use pathlib for file operations
- Maintain emoji-free interfaces
- Follow modular handler pattern

### Extension Pattern
- **New backup providers**: Follow pattern: `<engine>_runner.py` + `<engine>_validator.py` + `<engine>_form_parser.py` + update delegation
- **New repository types**: Add to `ResticRunner._build_repository_url()`
- **New validation**: Extend `ResticValidator` methods
- **New form fields**: Add to `ResticFormParser` and update templates
- **New commands**: Add to `CommandType` enum and `ResticCommand`
- **Form parser modularity**: Each destination type has dedicated parser with consistent `{'valid': bool, 'config'/'error': ...}` interface

## Security Considerations

### Current Security Status
- Basic input validation and sanitization
- SSH key-based authentication assumed
- Repository passwords stored in plain text (⚠️ temporary)

### Required Security Improvements
- Encrypt repository passwords
- Secure environment variable handling
- SSH connection security hardening
- Repository access control validation
- Audit logging for all operations

---

**Status**: Restic Connectivity Validation Complete - Ready for Enhanced Execution

**Completed**: 
- ✅ Complete Restic provider backend (planning, validation, form parsing)
- ✅ Comprehensive test suite with 30+ test cases
- ✅ Full integration with existing rsync functionality
- ✅ Clean extension pattern established for future providers
- ✅ **Complete Restic UI implementation** - Professional form handling with all repository types
- ✅ **Restic execution implementation** - Modular command building with repository initialization and backup execution
- ✅ **Real connectivity validation** - Network testing, repository access validation, binary availability checking
- ✅ **Enhanced error messaging** - Clear binary missing detection, authentication errors, repository status
- ✅ **Detailed validation results** - Shows existing repositories with snapshot counts and latest backup timestamps

**Next Priority**: Enhanced execution features (progress parsing, status updates, retention policies)