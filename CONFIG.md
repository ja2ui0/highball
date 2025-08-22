# Config Hierarchy Migration Plan

## Overview
Migrate Highball from monolithic `config/config.yaml` to distributed config hierarchy with per-job files and secrets separation. This enables better security, scalability, and prepares for future multi-user support.

## Current vs Target Architecture

### Current (Legacy)
```
config/config.yaml  # Everything in one file:
  global_settings: {...}
  backup_jobs:
    job_name: {source_type, source_config, dest_type, dest_config, schedule, enabled...}
  deleted_jobs:
    job_name: {...}
```

### Target (New Hierarchy)
```
config/
  config.yaml                 # Legacy fallback (will be removed)
  local/                      # Template user (like /etc/skel) + current single user
    local.yaml               # User-specific global settings
    jobs/
      <job_name>.yaml        # Individual job config (flattened)
      deleted/
        <job_name>.yaml      # Deleted jobs with deleted_on timestamp
    secrets/
      local.env              # User-specific secrets/tokens  
      jobs/
        <job_name>.env       # Per-job secrets (passwords, keys)
        deleted/
          <job_name>.env     # Deleted job secrets (preserved)
```

### Future Multi-User Pattern (Template System)
```
config/
  local/                      # Template user (like Linux /etc/skel)
    local.yaml               # Default settings template
    secrets/local.env        # Empty secrets template
    jobs/
      example.yaml.disabled  # Example job templates
  shane/                     # Real user (copied from local/)
    shane.yaml               # User's global settings
    secrets/shane.env        # User's secrets
    jobs/...                 # User's jobs
  alice/                     # Another user
    alice.yaml
    secrets/alice.env
    jobs/...
```

## Key Changes

### 1. Job Config Flattening
**Before** (nested under `backup_jobs.job_name`):
```yaml
backup_jobs:
  my_job:
    source_type: ssh
    source_config: {hostname: host, username: user}
    dest_type: restic
    # ... rest of config
```

**After** (direct in `jobs/my_job.yaml`):
```yaml
source_type: ssh
source_config: {hostname: host, username: user}  
dest_type: restic
# ... rest of config (flattened, no job: wrapper)
```

### 2. Secrets Separation
**Before** (passwords in main config):
```yaml
dest_config:
  password: "secret123"
  repo_uri: "s3:https://..."
```

**After** (secrets in separate `.env`):
```yaml
# jobs/my_job.yaml
dest_config:
  repo_uri: "s3:https://..."
  
# secrets/jobs/my_job.env  
RESTIC_PASSWORD=secret123
S3_ACCESS_KEY=AKIA...
S3_SECRET_KEY=abc123...
```

### 3. Deleted Jobs
- Move from `deleted_jobs` section to `jobs/deleted/` directory
- Add `deleted_on: 2025-08-21T10:30:00Z` timestamp for tombstone tracking
- Preserve both config and secrets files for potential restoration

## Implementation Phases

### Phase 1: Config Loading Infrastructure

#### 1.1 Update config.py Path
```python
# Change from:
CONFIG_PATH = "/config/config.yaml"
# To:
CONFIG_PATH = "/config/local/local.yaml"
```

#### 1.2 Create New Config Loader
- **File**: `config.py` 
- **Method**: `BackupConfig.__init__()`
- **Logic**:
  1. Load global settings from `/config/local/local.yaml`
  2. Scan `/config/local/jobs/*.yaml` for active jobs
  3. Scan `/config/local/jobs/deleted/*.yaml` for deleted jobs
  4. For each job, attempt to load secrets from `/config/local/secrets/jobs/<job>.env`

#### 1.3 Job-Secrets Merging
- **Purpose**: Combine job config with environment secrets
- **Pattern**: Environment variables override config values
- **CRITICAL**: Not all jobs have secrets - check file existence first
- **Example**: 
  ```python
  # Load job config
  job_config = yaml.load("jobs/my_job.yaml")
  
  # Load secrets ONLY if .env file exists
  secrets_file = f"/config/local/secrets/jobs/{job_name}.env"
  if os.path.exists(secrets_file):
      secrets = dotenv.load(secrets_file)
      # Merge: secrets override config
      merged_config = {**job_config, **secrets}
  else:
      # No secrets file = job has no secrets (rsync, SSH key auth, etc.)
      merged_config = job_config
  ```

### Phase 2: Job Operations Rewrite

#### 2.1 Save Job Operation
- **Current**: Update `backup_jobs` section in monolithic config
- **New**: Write atomic job+secrets pair
- **Files**: 
  - `jobs/<job_name>.yaml` (config without secrets)
  - `secrets/jobs/<job_name>.env` (environment variables - only if job has secrets)
- **Atomicity**: Use temporary files, then atomic rename both simultaneously
- **Secret Handling**: Only create `.env` file if job actually has secrets

#### 2.2 Delete Job Operation  
- **Current**: Move from `backup_jobs` to `deleted_jobs` in same file
- **New**: Move files to `deleted/` subdirectories
- **Steps**:
  1. Add `deleted_on: <timestamp>` to job config
  2. Move `jobs/<job>.yaml` → `jobs/deleted/<job>.yaml`
  3. Move `secrets/jobs/<job>.env` → `secrets/jobs/deleted/<job>.env`
- **Atomicity**: Both files moved together or operation fails

#### 2.3 Restore Deleted Job
- **Reverse of delete**: Move files back from `deleted/` directories
- **Remove** `deleted_on` field from config
- **Validation**: Ensure job name doesn't conflict with existing active job

### Phase 3: Code Integration Points

#### 3.1 Handler Updates
- **File**: `handlers/pages.py`
- **Methods**: 
  - `save_backup_job()` - Use new atomic job saving
  - `delete_backup_job()` - Use new atomic job deletion
  - `show_edit_job_form()` - Load from individual job files

#### 3.2 Form Parser Updates
- **File**: `models/forms.py`
- **Change**: Parse flattened job structure (no `backup_jobs` wrapper)
- **Secrets**: Extract password/key fields to separate environment format

#### 3.3 Template Updates
- **Files**: Templates that iterate over jobs
- **Change**: Jobs now come from file-based loading, not config sections
- **Impact**: Minimal - job iteration should be transparent

### Phase 4: Secret Management

#### 4.1 Environment Loading
- **Library**: `python-dotenv` (if not already present)
- **Pattern**: Load `.env` files into environment variables
- **Scope**: Per-job secrets isolated, don't leak between jobs
- **File Existence**: Always check `os.path.exists()` before loading - not all jobs have secrets

#### 4.2 Secret Extraction
- **From Job Configs**: Extract sensitive fields to `.env` format
- **Fields**: `password`, `access_key`, `secret_key`, `token`, etc.
- **Format**: `FIELD_NAME=value` (uppercase, underscored)

#### 4.3 Security Considerations
- **File Permissions**: Ensure `secrets/` directory is properly protected
- **Environment Isolation**: Job secrets don't persist in global environment
- **Logging**: Never log secret values, use obfuscation

## Testing Strategy

### 1. Backward Compatibility Test
- Ensure legacy `config/config.yaml` path change doesn't break startup
- Verify empty jobs list when no job files present

### 2. Job Lifecycle Test
- Create job → verify `.yaml` and `.env` files created
- Edit job → verify files updated atomically  
- Delete job → verify files moved to `deleted/`
- Restore job → verify files moved back to active

### 3. Secrets Integration Test
- Job with secrets → verify secrets loaded and merged correctly
- Job without secrets → verify no `.env` file created, no errors on load
- Multiple jobs → verify secret isolation between jobs
- Missing secrets file → verify graceful handling (many jobs don't need secrets)

### 4. Migration Validation
- Compare job data before/after migration
- Verify all jobs preserved with identical functionality
- Confirm deleted jobs properly restored

## File Structure After Migration

```
config/
  local/                     # Template user + current single user
    local.yaml              # User-specific global settings
    jobs/
      my-backup.yaml         # Job config (no secrets)
      db-backup.yaml
      deleted/
        old-job.yaml         # Deleted job with deleted_on timestamp
    secrets/
      local.env              # User-specific environment variables
      jobs/
        my-backup.env        # Job-specific secrets
        db-backup.env
        deleted/
          old-job.env        # Deleted job secrets (preserved)
    keys/                    # SSH key management (future)
      known_hosts
      pub/
```

## Multi-User Benefits (Future)

### User Creation Process
```bash
# Create new user from template:
cp -r config/local/ config/newuser/
mv config/newuser/local.yaml config/newuser/newuser.yaml  
mv config/newuser/secrets/local.env config/newuser/secrets/newuser.env
# Edit configs to personalize for newuser
```

### Template Management
- **local/** serves as `/etc/skel` equivalent
- **Default settings** in `local.yaml` for new users
- **Example jobs** as `*.yaml.disabled` files for user reference
- **Admin updates** to template affect all new users
- **Existing users** remain unchanged

## Risk Mitigation

### 1. Atomic Operations
- **Problem**: Partial writes during job operations
- **Solution**: Write to temporary files, atomic rename both files simultaneously

### 2. File System Errors
- **Problem**: Disk full, permission errors during file operations
- **Solution**: Validate filesystem before operations, rollback on failure

### 3. YAML Format Validation
- **Problem**: Flattened job structure might be invalid YAML
- **Solution**: Test flattened format extensively, add `job:` wrapper if needed

### 4. Secret Exposure
- **Problem**: Secrets accidentally logged or exposed
- **Solution**: Use existing obfuscation utilities, never log secret values

## Execution Checklist

1. ✅ Update CONFIG_PATH to `/config/local/local.yaml`
2. ✅ Implement new config loading logic in `config.py`
3. ✅ Create job file operations (save/delete/restore)
4. ✅ Update form parsers for flattened structure
5. ✅ Implement secrets loading and merging
6. ✅ Update all job CRUD operations in handlers
7. ✅ Test job lifecycle end-to-end
8. ✅ Validate secrets isolation and security
9. ✅ Remove legacy config dependencies
10. ✅ Update documentation

## Migration Status

**VALIDATION COMPLETE**: Existing `config/local/` structure verified against legacy `config.yaml`:
- ✅ Job config flattening correct (no `backup_jobs` wrapper)
- ✅ Secrets properly extracted to `.env` files with variable substitution
- ✅ Only jobs with secrets have `.env` files (no empty file cruft)
- ✅ Deleted jobs properly moved to `deleted/` subdirectories
- ✅ All job data preserved with identical functionality

## Context Dependencies

- **CLAUDE.md**: Contains current architecture and development patterns
- **Codebase**: Current config loading in `config.py`, job operations in `handlers/pages.py`
- **File Structure**: Existing `config/local/` hierarchy already in place and validated
- **Security**: Existing obfuscation patterns in `services/` for secret handling