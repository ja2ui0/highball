# Core mental model

Offer **three restore targets**, each with a clear, simple path:

1. **Restore to source**
  - Default and most common.
  - Requires re-entering the repo password and confirming overwrites.
  - Supports partial restores (selected folders/files).
  - Safe by default: preflight size estimate and a “dry run” summary before touching disk.
        
2. **Restore to highball**
  - Restores into a persistent folder inside the container (bind-mount recommended).
  - Useful for inspecting or hand-picking files, or when the source host path is offline.
  - Makes follow-up actions easy (manual copy, diff, malware scan, etc.).
        
3. **Download a file**
  - Single file recovery only for early versions
        
# How the user picks

- **Backup source**
  - discovered on Inspect page

- **Snapshot / Filesystem**
  - latest snapshots on top
  - filesystem isn't versioned

- **Selection**:
  - "Select All" for repo types only (like restic, borg, kopia)
    - will automatically trigger a full "snapshot restore" for providers with this option
  - File browser for filesystem types (rsync, rclone) and also for snapshots
  - Checkboxes on folders/files in the browser view
        
- **Target**:
  - Source (default for all types)
  - Highball (Local - default for filesystem types)
    - User should bind mount a local directory for this to be useful
  - Download
    - Single files only (for now) - visible only when exactly one file is selected

- **Safety**:
  - **Dry run** toggle (on by default)
  - For repo types: Overwrite policy
    1. Skip existing
    2. Overwrite newer only
    3. Overwrite all
  - User must supply password for any restore operation that would overwrite any files at source for backup methods that support passwords, or a "random" phrase for methods that don't
        
# Under the hood

- Estimate size / counts
- Background the process and tail a restore log for Source and Highball (Local) types
- Preserve ownership and permissions vs Restore as current user?
- Symlinks, sockets, device files: show a different icon in the file browser?
  - X icon for device files / sockets - skip these files, Highball won't handle them (and not planned)
  - 'link' icon for symlinks. Hard link handling for supported types?
- Nice / ionice the restore provess?
- Hard kill switch in UI?
  - Dashboard: RESTORING status, KILL button replaces RUN, FOLLOW replaces DRY RUN, EDIT goes away
- Design review - do we keep file browser in the Inspect tab, or do we move job inspection to a button on the dashboard, and select all the options based on that? MUCH easier for the user and less confusing.
- Fork process and tail log so user can watch the process in browser
- Mark restores (log) clearly with job type, snapshot id, and selection summary.
- Keep the dry run summary attached to the job for auditing
    
# Roadmap / Wishlist
- Include / Exclude patterns for repos that support full snapshot restores
- Multi-file Download with tar.gz or zip, with warnings (and disk space check) for large size / many files, quotas, timeouts
- progress monitoring / notification
- "mount snapshot" for supported types, probably to a subdir of a bind mounted "restore" volume

# Glossary
- App will feature a help section, advance restore ops will be linked
