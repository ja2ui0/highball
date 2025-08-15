# Highball Subsystems

## 🚨 CURRENT FOCUS: Container Execution Integration

**Most Recent Work (2025-08-15)**: Container-based restore execution tested and working, but critical gaps remain in backup execution and RestoreHandler integration.

**IMMEDIATE TASKS**:
1. **Update backup execution pipeline** to use ResticRunner container commands for SSH sources (never tested before)
2. **Complete RestoreHandler integration** - replace manual command building with ResticRunner.plan_restore_job()
3. **Test end-to-end flow**: SSH source backup → container execution → restore workflow

**Container Execution Status**:
- ✅ **WORKING**: Container restore execution verified: `ssh root@yeti.home.arpa docker run --rm -e 'RESTIC_PASSWORD=***' -v /:/restore-target restic/restic:0.18.0 -r rest:http://yeti.home.arpa:8000/yeti restore snapshot_id --target /restore-target --include /path --dry-run`
- ✅ SSH capability detection (docker/podman) and job config population complete
- ✅ Secret obfuscation implemented (all password instances hidden in logs)
- ❌ **CRITICAL GAP**: Backup execution still uses local restic binary instead of containers
- ❌ **INTEGRATION NEEDED**: RestoreHandler manually builds commands instead of using ResticRunner patterns

**Files Needing Updates**:
- `services/restic_runner.py`: Add plan_restore_job() method (container command building complete)
- `handlers/restore_handler.py`: Replace manual command building with ResticRunner calls
- Backup execution pipeline: Integrate ResticRunner container patterns for SSH sources

## Restore System

**Status**: Complete implementation with smart overwrite protection, dual restore targets (container vs. source), progressive disclosure UI, and modular JavaScript architecture ready for multi-provider expansion.

## Implementation Details

**Multi-Path Jobs**: Job = Source + Destination + Definition. Jobs support multiple source paths with per-path include/exclude rules. UI uses progressive disclosure with "+ Add Another Path" button.

**Multipart Form Data**: Repo-wide conversion from URL-encoded to multipart with auto-detection and backward compatibility. All JavaScript uses `FormData`, all HTML templates have `enctype="multipart/form-data"`.

**Restic Provider**: Complete execution and repository browser. Container-based command building (`restic/restic:0.18.0`). Repository types: Local, REST, S3, SFTP, rclone.

**Notification System**: `notifiers` library backend with spam-prevention queuing. Telegram/Email providers. Per-job configuration with template variables. Event-driven queue with file persistence.

## Critical Status Notes

**Container Execution Gaps**:
- ✅ Restore execution uses containers (tested and working)
- ❌ Backup execution still uses local restic binary (never tested with SSH sources)
- ❌ ResticRunner container integration not connected to backup pipeline

**Immediate Priorities**:
1. Update backup execution to use ResticRunner container commands
2. Complete RestoreHandler integration with ResticRunner.plan_restore_job()
3. Test end-to-end SSH source → container backup flow