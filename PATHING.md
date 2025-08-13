# Multi-Path Jobs Architecture Change

## Context
User discovered existing restic repository with TWO paths, revealing limitation of current "One Job = One Source Path + One Destination" Prime Directive. Need to support multiple source paths per job while maintaining clean architecture.

## Problem Statement
- Current: Single path per job creates artificial job proliferation
- Users naturally want to backup multiple related paths to same destination
- Restic natively supports multiple paths efficiently
- Current UI forces unnatural workflow

## Solution: Multi-Path Jobs

### New Prime Directive
**"Job = Source + Destination + Definition"**

Where:
- **Source**: Host connection + multiple related paths (with per-path rules)
- **Destination**: Repository location and configuration  
- **Definition**: Schedule, conflicts, job-level settings

### UI Container Restructure
1. **Job Identity & Source** (CHANGED: removes "local path" field)
2. **Backup Destination** (unchanged)
3. **Source Options** (NEW: expanded from "Schedule & Options"):
   - Source Path #1
   - Include Patterns #1  
   - Exclude Patterns #1
   - **[+ Add Another Path]** button (styled like password show/hide)
   - *(repeating path/include/exclude triads)*
4. **Actions** (CLARIFIED: job-level functions):
   - Schedule definition
   - Enabled checkbox
   - Conflict resolution settings
   - Create Job / Cancel buttons

### Data Schema Change
```yaml
# OLD
source_config:
  hostname: "host"
  username: "user"
  path: "/single/path"        # Single path
includes: ["pattern"]         # Job-level
excludes: ["pattern"]         # Job-level

# NEW  
source_config:
  hostname: "host"
  username: "user"
  source_paths:               # Array of path objects
    - path: "/path/one"
      includes: ["*.pdf"]     # Per-path
      excludes: ["temp/**"]   # Per-path
    - path: "/path/two"
      includes: ["*.jpg"]
      excludes: ["cache/**"]
```

### Implementation Strategy
1. **Backward Compatibility**: Migrate single `path` → `source_paths[0].path`
2. **Progressive Disclosure**: Single path by default, "+ Add Another Path" for complexity
3. **Conflict Detection**: Check all paths in job A vs all paths in job B
4. **Command Generation**: 
   - Restic: Single command with multiple paths
   - Rsync: Sequential commands per path

### Why This Change
- **Natural**: Matches user mental model ("backup my important stuff")
- **Efficient**: Leverages tool efficiency (restic multi-path)
- **Granular**: Maintains per-path includes/excludes control
- **Simple**: Reduces config complexity for common cases
- **Logical**: Clean separation of concerns (Source + Destination + Definition)

### Files to Modify
- Form templates (job_form.html, source sections)
- Form parsers (ssh_form_parser.py, local_form_parser.py)
- Job validator (path conflict detection)
- Command builders (multi-path support)
- Documentation (CLAUDE.md Prime Directive)

### Current Status
- ✅ Architecture designed and agreed
- ✅ UI restructured with new containers
- ✅ Form parser updated for multi-path support
- ⚠️ Schema changes in progress 
- ❌ Conflict detection updates needed
- ❌ Command builder updates needed

## Implementation Progress

### ✅ Completed
1. **UI Restructure**: New container layout
   - Job Identity & Source (hostname/username only)
   - Backup Destination (unchanged)
   - Source Options (multi-path with per-path includes/excludes)
   - Actions (schedule, enabled, conflict resolution, buttons)

2. **Form Templates**: 
   - `job_form_source_options.html` (multi-path with + Add Another Path)
   - `job_form_actions.html` (job-level settings)
   - CSS styling for path groups and add/remove buttons

3. **Form Parser Updates**:
   - `JobFormParser.parse_multi_path_options()` handles arrays
   - SSH/Local source parsers updated (no more individual path)
   - New schema: `source_config.source_paths[{path, includes, excludes}]`

### 🚧 In Progress
4. **Schema Validation**: Test new data structure
5. **Backward Compatibility**: Migration for existing jobs

### ❌ Next Steps
6. **Conflict Detection**: Multi-path aware conflict checking
7. **Command Builders**: Update for new source_paths structure
8. **Documentation**: Update Prime Directive and CLAUDE.md