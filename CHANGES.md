# Changes 2025-08-19 - Job Form System Completion

## Major Architectural Achievements

### ✅ Schema-Driven Form Architecture
**Problem Solved**: Handlers contained 50+ lines of inline HTML strings
**Solution**: Complete HTML/handler separation with dynamic field generation

**Implementation**:
- **Zero HTML in Handlers**: `handlers/forms.py` now pure business logic (700+ lines)
- **Dynamic Templates**: Schema-driven field rendering for all form sections
- **Modular Partials**: 50+ reusable template components
- **Schemas**: Repository types (5), maintenance modes (3), notification providers with complete field definitions

### ✅ Dual Storage Pattern (Round-Trip Data Integrity)
**Problem**: Edit forms couldn't populate discrete fields because only constructed URIs were stored
**Solution**: Store both constructed URI (execution) and discrete fields (editing)

**Results**:
```yaml
dest_config:
  repo_uri: rest:https://user:pass@host:8000/path  # For execution
  rest_hostname: host      # For editing
  rest_password: pass     # For editing
  # ... all discrete fields preserved
```

**Technical Implementation**:
- Enhanced `DestinationParser._store_discrete_fields()` saves all repository fields alongside URI
- Complete S3 schema with required authentication fields (region, access_key, secret_key, endpoint)
- Form data builders populate discrete fields from config for perfect edit form restoration

### ✅ Smart Edit Form UX (HTMX-Driven)
**Features**:
- **Dynamic Button Text**: "Create Job" (add) vs "Commit Changes" (edit)
- **Real-Time Change Detection**: HTMX form comparison with original config
- **Smart Button State**: Disabled when no changes, enabled when changes detected
- **Zero JavaScript**: Pure HTMX using `hx-trigger="input from:form, change from:form"`

**Implementation**:
- Original state tracking via JSON serialization in hidden field
- HTMX endpoint `/htmx/check-form-changes` compares current vs original
- Server-side deep config comparison using JSON string equality
- Template rendering via `partials/submit_button.html`

## Critical Patterns & Lessons Learned

### ✅ HTMX DOM-Safe Targeting (Critical Discovery)
**The Problem**: "Add Another Path" button wouldn't work - backend worked via curl, browser failed
**Root Cause**: HTMX button targeting its own parent container for replacement
1. Browser executes HTMX request successfully
2. Parent container gets replaced with new HTML  
3. **Original button element is destroyed** during replacement
4. HTMX loses reference to button, breaks event handling

**Working Architecture**:
```html
<div id="source_paths_container">
  <div id="source_paths_list"><!-- Path entries appended here --></div>
  <button hx-target="#source_paths_list" hx-swap="beforeend"><!-- Button stays intact --></button>
</div>
```

**Key Patterns**:
- **Add Operation**: `hx-target="#source_paths_list"` + `hx-swap="beforeend"` (preserve button)
- **Remove Operation**: `hx-target="#path_entry_{{ index }}"` + `hx-swap="outerHTML"` (self-destruct)
- **Form Inclusion**: `hx-include="closest form"` (smart form data gathering)
- **Protection**: `{% if path_index > 0 %}` prevents deletion of last path

### ✅ Three-Mode Maintenance System
**Migration**: `auto_maintenance: bool` → `restic_maintenance: auto|user|off`
- **Auto**: Hardcoded defaults (daily cleanup 3am, weekly checks Sunday 2am, retention policies)
- **User**: 8 configurable fields (2 schedules + 6 retention policies) with validation
- **Off**: Disables maintenance with clear warning

## Complete Feature Set Delivered

### ✅ Repository Support
- **5 Repository Types**: local, rest, s3, sftp, rclone with complete field sets
- **REST Server**: HTTPS toggle, authentication fields, path logic, URI preview
- **S3**: Complete authentication (region, access_key, secret_key, endpoint)
- **Dynamic Field Rendering**: Schema-driven based on repository selection

### ✅ Source Management  
- **Multi-Path Arrays**: Add/remove paths with DOM-safe HTMX targeting
- **Path Validation**: SSH execution with permission testing (RX/RWX detection)
- **Schema-Driven**: Universal `SOURCE_PATH_SCHEMA` for path/includes/excludes

### ✅ Notification System
- **Provider Management**: One-provider-per-job logic with dropdown state management
- **Schema-Driven Config**: Conditional fields and template variables
- **Template Variables**: `{job_name}`, `{duration}`, `{error_message}`
- **HTMX Progressive Disclosure**: Add/remove providers with proper state management

### ✅ Schedule Configuration
- **Schedule Types**: Manual, predefined (hourly/daily/weekly/monthly), custom cron
- **Global Config Integration**: Default cron patterns from global settings
- **HTMX Behavior**: Cron field shows/hides based on "custom" selection

### ✅ Form System
- **Perfect Edit Forms**: "Code agent" auto-populates ALL fields from config
- **Real-Time Validation**: Change detection with smart button enabling
- **Config Preview**: HTMX endpoint generates YAML preview for debugging
- **Complete Integration**: All sections functional with end-to-end workflow

## Current Status: Job Form System Complete

**Fully Functional**:
- Job creation (add) and editing with dynamic button text
- All repository types with complete field sets  
- Dual storage pattern for perfect round-trip data integrity
- Real-time form validation and change detection
- Complete source/destination/notification/schedule configuration

**Next Priority**: Core backup execution functionality testing and optimization

## Key Architecture Principles Established

1. **Complete Round-Trip Data Integrity**: Edit → Save → Edit preserves exact form state
2. **Execution vs Editing Separation**: Ready-made URIs for performance, discrete fields for UX  
3. **Zero Code Repetition**: Unified parsers handle both URI construction and field storage
4. **Pure HTMX Architecture**: No JavaScript violations, all interactivity server-driven
5. **DOM Integrity**: HTMX buttons must never destroy themselves during operation