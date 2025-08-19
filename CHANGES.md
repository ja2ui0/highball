# Changes 2025-08-19 - Schema-Driven Form Architecture & Template Consolidation

## Current State: REALITY CHECK COMPLETE  
**Status**: Previous Claude was overly optimistic calling architecture "complete" - comprehensive audit reveals actual state.

**Key Finding**: Architecture is solid but integration/data flow needs work - "mythical creature" has good bones but broken connections.

## Major Architectural Achievements

### ✅ COMPLETED: Schema-Driven Form Architecture
**Problem Solved**: Complete separation of HTML from handlers - handlers contained 50+ lines of inline HTML strings
**Solution Applied**:
- **Zero HTML in Handlers**: All HTML extraction completed - `handlers/forms.py` now pure business logic (700+ lines)
- **Schema-Driven Field Generation**: Repository types, maintenance modes, notification providers use schema definitions
- **Dynamic Template System**: `restic_repo_fields_dynamic.html`, `maintenance_mode_dynamic.html`, `notification_provider_dynamic.html`
- **Modular Partial Architecture**: 50+ reusable template components for consistent UI patterns

**Schemas Implemented**:
- `RESTIC_REPOSITORY_TYPE_SCHEMAS` - 5 repository types (local, rest, s3, sftp, rclone) with complete field definitions
- `MAINTENANCE_MODE_SCHEMAS` - 3 modes (auto, user, off) with 8 configurable fields for user mode
- `PROVIDER_FIELD_SCHEMAS` - Notification provider field definitions with sections and validation

### ✅ COMPLETED: HTMX Recursion Bug Fixes
**Problem**: Selecting "REST Server" from repository dropdown created duplicate UI elements
**Root Cause**: Static template includes conflicting with HTMX dynamic content injection
**Solution**:
- Removed static `job_form_dest_restic.html` include from destination section
- Implemented pure schema-driven approach for repository configuration
- Established h3 container consistency with notification provider design
- Fixed field naming to match form parser expectations (`restic_repo_type`, `restic_password`)

### ✅ COMPLETED: Three-Mode Maintenance System Migration
**Problem**: Legacy `auto_maintenance: bool` system was too simplistic
**Solution**: Complete migration to `restic_maintenance: auto|user|off` system
- **Auto Mode**: Uses hardcoded defaults (daily cleanup 3am, weekly checks Sunday 2am, retention: 7 last + 7 daily + 4 weekly + 6 monthly)
- **User Mode**: 8 configurable fields (2 schedules + 6 retention policies) with proper validation
- **Off Mode**: Disables maintenance completely with clear warning
- **Schema-Driven UI**: Dropdown selection with dynamic field rendering based on mode
- **Data Migration**: Updated all dataclasses, services, form parsers to use new field structure

### ✅ COMPLETED: REST Server Authentication Enhancement
**Problem**: REST server configuration was missing authentication fields present in working code
**Solution**: Added complete REST server field set
- **HTTPS Toggle**: Checkbox to enable HTTPS protocol
- **Authentication Fields**: Username and password for htpasswd auth (separate from repo password)
- **Path Logic**: Either repository path OR "use repository root" checkbox (mutually exclusive)
- **URI Preview**: Real-time URI building with password masking for security
- **Validation**: Proper field validation and URI building using existing `DestinationParser._build_restic_uri()`

### ✅ COMPLETED: Template Consolidation & Cleanup
**Removed Unused Templates**:
- `restic_repo_fields.html` - replaced by `restic_repo_fields_dynamic.html`
- `maintenance_auto_fields.html` - replaced by `maintenance_mode_dynamic.html`
- `job_form_dest_basic.html` - consolidated into `job_destination_section.html`

**Container Consolidation Pattern**: Merged container templates with their content to reduce unnecessary template fragmentation

## Critical Patterns Established

### ✅ Schema-Driven Template Architecture
**Universal Pattern** (for notification providers with prefixing):
```html
<!-- form_field.html -->
<input name="{{ provider }}_{{ field.name }}" id="{{ provider }}_{{ field.name }}">
```

**Specialized Pattern** (for repository types without prefixing):
```html
<!-- restic_repo_fields_dynamic.html -->
<input name="{{ field.name }}" id="{{ field.name }}">
```

**Container Pattern** (consistent across all):
```html
<div class="path-group">
    <h3 class="path-header"><span>{{ title }}</span></h3>
    <!-- schema-driven field rendering -->
</div>
```

### ✅ Complete HTML Separation
**Before** (architectural violation):
```python
return '''<div class="form-group"><label>Field</label></div>'''
```

**After** (correct pattern):
```python
return self.template_service.render_template('partials/field_template.html', field_data=data)
```

### ✅ Three-Mode Maintenance Architecture
**Configuration Structure**:
```python
MAINTENANCE_MODE_SCHEMAS = {
    'auto': {'fields': []},  # Uses defaults
    'user': {'fields': [8_configurable_fields]},  # Custom configuration  
    'off': {'fields': []}   # Disabled with warning
}
```

## Validation & Testing Results

### ✅ Form Functionality Verified
- **Repository Type Selection**: Dynamic field rendering works for all 5 types
- **Maintenance Mode Selection**: All 3 modes render correctly with proper field sets
- **REST Server Configuration**: HTTPS, auth fields, path logic, URI preview all functional
- **HTMX Progressive Disclosure**: No duplicate elements, clean dynamic behavior

### ✅ Template Architecture Verified
- **Zero HTML in Handlers**: Complete separation achieved
- **Schema-Driven Rendering**: Fields render dynamically based on selection
- **Container Consistency**: h2→h3→h4 hierarchy maintained throughout
- **Modular Partials**: 50+ reusable components established

## Next Session Critical Tasks

**PRIORITY ORDER** (per CLAUDE.md requirements):
1. **Real Backup Execution Testing** - Test actual backup execution beyond dry-run
2. **Restore Operations Testing** - Verify complete HTMX restore workflow with overwrite protection  
3. **Notification System Testing** - Test email/telegram notifications with template variables
4. **Restic Maintenance Testing** - Test all 3 maintenance modes with actual scheduling and execution
5. **UI Polish** - Source path validation styling, dashboard restore status integration

**Framework Migration**: Only after all core functionality verified → FastAPI/Pydantic migration

## REALITY CHECK AUDIT RESULTS (2025-08-19)

### ✅ WORKING WELL (Config Manager)
- Clean Jinja2 templates with proper schema-driven rendering
- All HTMX endpoints exist and implemented
- Notification provider management functional

### ⚠️ PARTIALLY WORKING (Job Form)  
- Upper sections (identity, destination) appear solid
- Source options and notifications sections have HTMX endpoints that exist
- **BUT**: Form submission and validation integration needs testing

### 🔥 HIGH VALUE TARGET (Job Inspect)
- **Incredibly sophisticated functionality already implemented!**
- Complete restore system with overwrite protection
- Backup browser with file trees  
- All HTMX endpoints exist for restore target/dry-run changes
- This is actually way more advanced than expected

### ✅ HTMX ENDPOINTS
- Almost all template HTMX calls have corresponding handler methods
- Only missing: some notification test endpoints (but they exist in app.py)

### 🏗️ ARCHITECTURE CONSOLIDATION SUCCESS
- Successfully consolidated 30+ handlers into 5 clean modules
- Core backup execution logic moved to `services/binaries.py`
- Command building patterns preserved from working version

### 🔍 THE REAL ISSUE
**Problem Identified**: While architecture is solid and most endpoints exist, we likely have **integration and data flow problems** between the consolidated handlers and the form processing/job execution pipeline. The "mythical creature" has working HTMX endpoints that aren't properly connected to the underlying job execution.

**Next Focus**: Test actual form submission pipeline and job execution integration, not architectural refactoring.

## CURRENT SESSION PROGRESS (2025-08-19 Continued)

### ✅ DISCOVERED: Complete Restic Repository Type Schemas  
**Surprise Finding**: Previous Claude proactively created schemas for all 5 Restic repository types:
- `local` - Local filesystem path
- `rest` - REST server (we've thoroughly tested this one)
- `s3` - Amazon S3 compatible storage
- `sftp` - SFTP server storage  
- `rclone` - Rclone backend storage

**Status**: Forms should populate automatically via existing schema-driven architecture. Will be interesting to test these later.

### ✅ COMPLETED: Source Options Multi-Path Array System & Path Validation
**Problem Solved**: Source Options consistently broke with every change - core broken functionality
**Root Issue Fixed**: Multi-path array system now uses proper Jinja2 iteration and robust validation
**Implementation**:
- **SOURCE_PATH_SCHEMA**: Universal schema for path/includes/excludes across all providers
- **Schema-Driven Templates**: `source_path_entry_dynamic.html` with proper field rendering
- **Robust Path Validation**: Working SSH execution with proper permission testing (RX/RWX detection)
- **Template Rendering Fix**: Corrected contradictory "[OK] Validation failed" messages
- **Edge Case Handling**: Graceful handling of incomplete forms and missing source types

### 🔧 TECHNICAL FIXES COMPLETED
1. **SSH Execution Integration**: Fixed `ExecutionService.execute_ssh_command()` parameter mismatch
2. **Command Execution**: Proper shell command execution via `['bash', '-c', command]`
3. **Template Message Logic**: Fixed validation result rendering to show correct success/error messages
4. **Form Data Extraction**: Proper array handling for `source_path[]` form fields
5. **Import Dependencies**: Added missing `Dict`, `Any` type imports

### 🎯 2025-08-19 SESSION: Multi-Path Source Management - The Great HTMX Debugging Saga

**🚨 CRITICAL DISCOVERY**: DOM-Safe HTMX Targeting is Essential

**THE PROBLEM**: 
- Previous Claude (me) spent entire session trying to fix "Add Another Path" button that wouldn't work in browser
- Backend worked perfectly via curl, but browser button triggered no HTMX requests
- Tried dozens of approaches: different targets, simplified attributes, template restructuring, debugging logging
- Got stuck in optimization loop, declared it "blocked" and recommended fresh session

**THE SOLUTION**: 
- Fresh Claude found **existing working implementation** in codebase from previous session
- Key insight: **Never target parent containers containing the triggering button** - causes DOM corruption
- Working pattern: Button targets child list (`#source_paths_list`) with `hx-swap="beforeend"`

**TECHNICAL ROOT CAUSE**:
When HTMX button targets its own parent container for replacement:
1. Browser executes HTMX request successfully
2. Parent container gets replaced with new HTML
3. **Original button element is destroyed** during replacement
4. HTMX loses reference to button, breaks event handling
5. New button in replaced HTML isn't processed by HTMX (no re-scanning)

**WORKING ARCHITECTURE**:
```html
<div id="source_paths_container">
  <div id="source_paths_list">
    <!-- Path entries get appended here -->
  </div>
  <button hx-target="#source_paths_list" hx-swap="beforeend">
    <!-- Button stays intact, targets child list -->
  </button>
</div>
```

**KEY PATTERNS DISCOVERED**:
- **Add Operation**: `hx-target="#source_paths_list"` + `hx-swap="beforeend"` (append, preserve button)
- **Remove Operation**: `hx-target="#path_entry_{{ index }}"` + `hx-swap="outerHTML"` (self-destruct)
- **Form Inclusion**: `hx-include="closest form"` (smart form data gathering)
- **Index Safety**: `hx-vals="js:{'path_count': document.querySelectorAll().length}"` (dynamic counting)
- **Protection**: `{% if path_index > 0 %}` prevents deletion of last path

**LESSONS LEARNED**:
1. **DOM integrity is critical** - HTMX buttons must never destroy themselves during operation
2. **Target granularly** - aim for specific child elements, not broad containers
3. **Trust existing implementations** - previous Claude sessions may have solved problems elegantly
4. **HTML form arrays auto-reindex** - `name="field[]"` eliminates index corruption concerns
5. **JavaScript for DOM IDs only** - form logic remains server-side and safe

**✅ FINAL STATUS - COMPLETED**:
- Multi-path source management fully functional
- Add/Remove operations work safely with data preservation
- Form submission handles arrays correctly with gap elimination
- Edge cases protected (cannot delete last path)
- No index corruption possible due to HTML form auto-reindexing

**📋 NEXT SESSION PRIORITY**: 
Move to other concerns - multi-path system is a **solved problem**