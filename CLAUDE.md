# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

# 🚨 CRITICAL EXECUTION PATTERNS (READ FIRST)

**CRITICAL**: The command builder factory pattern and SSH execution intelligence are fundamental to backup functionality. These patterns were discovered through painful debugging in 2025-08-18 session after backup execution was completely broken.

## SSH vs Container Execution Intelligence (CRITICAL)

**Pattern**: `_should_use_ssh(source_config, operation_type)` determines execution context:
- **UI Operations** (snapshot listing, browsing, validation): ALWAYS execute locally from Highball container  
- **Source Operations** (backup, restore-to-source): ALWAYS execute via SSH+container on source host
- **Repository Operations** (init, maintenance): Execute via SSH when source is SSH

**Container Runtime Location (CRITICAL)**:
```yaml
# CORRECT - container_runtime in source_config
source_config:
  container_runtime: docker  # ✅ HERE
  hostname: host
  username: user

# WRONG - container_runtime at job level  
container_runtime: docker  # ❌ NOT HERE
source_config:
  hostname: host
```

**Execution Service Usage (CRITICAL)**:
- Use existing `ContainerService.build_backup_container_command()` for command building
- Use existing `ExecutionService.execute_ssh_command()` for SSH execution  
- **NEVER** try to manually build container commands or SSH execution
- Services in `services/binaries.py` and `services/execution.py` contain proven patterns

## Primary Critical Testing Requirements (Next Session)

**BEFORE ANY FRAMEWORK MIGRATION**, these core systems must be tested:

1. **Real backup execution** (not just dry-run) - verify actual data transfer
2. **Restore operations with overwrite protection** - critical safety feature
3. **Notification system** (email/telegram success/failure notifications)
4. **Restic maintenance operations** (discard/prune/check scheduling and execution)
5. **Rsync patterns** - multi-provider support verification

**UI functionality** - forms, validation, basic workflows are now FULLY FUNCTIONAL as of 2025-08-19.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Pattern**: handlers transform data, templates render HTML, HTMX handles dynamic behavior.
**Principles**: Thin handlers, centralized validation in `models/validation.py`, file-based logging, dataclass-driven configuration

**Rule: Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings). Definitions contain one or more paths with per-path include/exclude rules. This architecture balances user workflow simplicity with granular control and tool efficiency.

**Rule: Pure Orchestration Layer**: Highball orchestrates backup/restore operations by SSH-ing to hosts and running binaries there. Backup: SSH to source host → run restic/rsync → direct to destination. Restore: SSH to target host → run restic restore → files appear on target. Exception: Highball can restore to itself at `/restore` when source hosts no longer exist (designed for bind-mount persistence). This design enables ANY host to ANY destination with Highball providing coordination, not data intermediation.

**Rule: Container Execution Strategy**: Use official `restic/restic:0.18.0` containers on remote hosts to solve version mismatch problems. Remote hosts may have outdated restic versions (e.g., 0.16.4 missing `--dry-run` for restore) while Highball has 0.18.0. Container execution ensures version consistency across all operations. SSH validation auto-detects docker/podman availability and populates `container_runtime` in job config. **CRITICAL**: `restic/restic:0.18.0` has `restic` as entrypoint - container commands use `-r repository command` NOT `restic -r repository command`.

**Rule: SSH vs Local Execution Intelligence**: 
- **UI Operations** (snapshot listing, browsing, validation): Always execute locally from Highball container using local restic binary and credentials
- **Source Operations** (backup, restore-to-source): Always execute via SSH+container on source host  
- **Repository Operations** (init, maintenance): Execute via SSH when source is SSH for lock detection and pipeline validation
- **Pattern**: `_should_use_ssh(source_config, operation_type)` determines execution context - 'ui' operations always local, 'init'/'maintenance' operations use SSH when source is SSH

**Rule: DRY Principle & Provider Separation**: Don't Repeat Yourself. Restore services orchestrate provider-agnostic operations (overwrite detection, validation, progress tracking). Provider-specific functionality is consolidated into unified services. SSH patterns, authentication, environment management shared across all operations. This separation enables cohesive multi-provider support without code duplication.

**Rule: Just In Time, Progressive Disclosure**: User sees what they need when they need it. Ask only what can't be inferred. Do not overwhelm with choices.

**Rule: Naming is Immutable**: Method, function, variable, class and filenames NEVER change when refactoring. If, during regular development you want to change a name to make it more specific or more broad for context, you MUST stop everything else and update ALL references to that name everywhere it occurs in the code immediately!

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Jinja2, Docker, rsync/SSH. HTMX. Javascript requires permission.

## Architecture Overview

### Core System
- `app.py` (routing), `config.py` (YAML config)

### HTTP Layer (handlers/)
- **Page Rendering**: `pages.py` (consolidated: dashboard, config, inspection, logs, network)
- **Operations**: `operations.py` (backup/restore execution and coordination)
- **Forms**: `forms.py` (HTMX form processing and validation)
- **API**: `api.py` (JSON endpoints for HTMX updates, external integrations, repository introspection)
- **Scheduling**: `scheduler.py` (job scheduling and cron management)

## API Handler Usage Rules (CRITICAL - Unplanned Evolution)

**IMPORTANT**: `api.py` has evolved beyond its original scope of read-only dashboard widgets. These rules govern its usage going forward:

### ✅ GREEN LIGHTS (belongs in api.py):
- **Public API Endpoints** (`/api/highball/*`): External dashboard widgets (require bearer token)
- **Internal HTMX Endpoints** (no `/api/` prefix): Dynamic UI updates for internal app use (session auth)
- **Repository Introspection**: Read-only operations like snapshot listing, browsing, availability checks
- **Real-Time Form Validation**: Endpoints that validate form data and return JSON responses
- **Non-destructive Repository Operations**: Quick checks, unlock operations, validation

### ❌ RED FLAGS (belongs elsewhere):
- **Primary Form Submission**: Main form processing belongs in `forms.py` 
- **Page Rendering**: HTML page generation belongs in `pages.py`
- **Complex Business Operations**: Multi-step operations belong in `operations.py`
- **Job Management**: CRUD operations belong in appropriate handlers

### 🔍 Decision Framework:
1. **Does it return JSON?** → Likely api.py
2. **Is it for HTMX dynamic updates?** → Likely api.py  
3. **Is it repository introspection?** → Likely api.py
4. **Is it primary user workflow?** → Likely other handlers
5. **Does it render HTML pages?** → Definitely other handlers

**Rationale**: HTMX architecture requires JSON endpoints for dynamic UI updates. Repository introspection operations enable progressive disclosure UX patterns. This separation maintains clean concerns while supporting modern web patterns.

### Business Logic (services/)
- **Execution**: `execution.py` (unified command execution and obfuscation)
- **Repositories**: `repositories.py` (repository abstraction and filesystem browsing)
- **Restore**: `restore.py` (restore execution, overwrite checking, error parsing)
- **Maintenance**: `maintenance.py` (repository maintenance and cleanup operations)
- **Scheduling**: `scheduling.py` (scheduler management and schedule loading)
- **Management**: `management.py` (job management and lifecycle operations)
- **Data Services**: `data_services.py` (form data building and snapshot introspection)
- **Template**: `template.py` (template rendering and variable substitution)
- **Binaries**: `binaries.py` (binary availability checking and validation)

### Data Models (models/)
- **Validation**: `validation.py` (consolidated validation logic and rules)
- **Forms**: `forms.py` (form data structures and parsing logic)
- **Backup**: `backup.py` (backup-related data structures and operations)
- **Notifications**: `notifications.py` (notification system and queue management)
- **Rsync**: `rsync.py` (rsync-specific models and configurations)

### Frontend (static/)
- **Core Features**: `backup-browser.js` (697 lines - file tree navigation), `restore-core.js` + `restore-restic.js` (progress tracking, restore system), `job-inspect.js` (inspection hub, reduced from 265→215 lines)
- **Utilities**: `nav.js`, `network-scan.js`
- **HTMX Architecture Complete**: Schema-driven forms with dynamic field rendering, complete separation of HTML from handlers, modular partial system
- **Multi-Path Management**: Dynamic source path arrays with safe add/remove operations, automatic array reindexing, DOM-safe HTMX targeting

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps
- `/var/log/highball/running_jobs.txt` - currently running jobs for conflict detection
- `/var/log/highball/notification_queues/{provider}_state.yaml` - notification queue state and pending messages

## Features

**Job Management**: Full CRUD, validation, cron scheduling, per-job conflict avoidance, custom rsync options, multi-path sources
**Scheduling**: Runtime conflict detection, automatic queuing, configurable defaults
**Logging**: Per-job logs, SSH validation caching (30min), refresh-based viewing
**Notifications**: `notifiers` library backend, Telegram/email, spam-prevention queuing with configurable intervals, batch message formatting, per-job integration with template variables, test capabilities, emoji-free. `notify_on_success` configured per-job (not global)
**UI**: Schema-driven HTMX forms with dynamic field rendering, real-time validation, complete separation of HTML from handlers, modular partial template system, theming, password toggles, multi-path management, per-job inspection hubs (`/inspect?name=<jobname>`), source path validation buttons with [OK]/[WARN]/[ERROR] feedback
**Restic Integration**: Repository connectivity testing, binary availability checking, existing repository detection, content fingerprinting, complete repository browser with snapshot statistics and file tree navigation, three-mode maintenance system (auto/user/off) with schema-driven configuration
**Backup Browser**: Multi-provider backup browsing system supporting Restic (repository snapshots), rsync/SSH/local/rsyncd (filesystem directories) with unified interface, provider-specific terminology, and expandable file trees
**Restore System**: Complete Restic restore functionality with intelligent overwrite protection, dual restore targets (safe Highball `/restore` vs. risky source location), pre-flight risk assessment via `/check-restore-overwrites` endpoint, progressive disclosure confirmation system (no modals), dry run capability (default enabled), background execution with progress tracking, and modular JavaScript architecture extensible to future providers (rsync, borg, kopia) - full implementation with smart safety controls
**REST API**: GET `/api/highball/jobs` endpoint for external dashboard widgets with query filtering (`state`, `fields`), CORS support, and authentication-ready architecture
**Debug System**: System debugging interface (`/dev`) with network scanner, 8 unified log sources (system + operational) with organized 2-row layout, separated from per-job inspection

## Common Patterns

### Container Execution Strategy
- Use official `restic/restic:0.18.0` containers on remote hosts for version consistency
- SSH validation auto-detects docker/podman availability, populates `container_runtime` in job config
- Local operations use direct subprocess execution

### Form Processing Architecture (COMPLETED 2025-08-19)
- **Schema-Driven HTMX Architecture**: All form operations use server-side HTMX with dynamic field rendering based on schemas
- **Complete HTML Separation**: Zero HTML in handlers - all presentation logic in Jinja2 templates
- **Dynamic Field Systems**: Repository types, maintenance modes, and notification providers use schema-driven field generation
- **Dual Storage Pattern**: Store both constructed URIs (execution) and discrete fields (editing) for perfect round-trip data integrity
- **Smart Edit Forms**: "Code agent" auto-populates ALL fields from config, dynamic button text ("Create Job" vs "Commit Changes"), real-time change detection
- Multipart form data throughout (not URL-encoded)
- Source paths as array format: `[{'path': '/path', 'includes': [], 'excludes': []}]`
- **Parser Resilience Pattern**: Skip empty paths instead of failing
- **Error Data Preservation Pattern**: Use parsed config from payload over raw form data when available
- **Template Variables Pattern**: Server data via HTML data attributes to JavaScript

### Validation Patterns
- Real-time validation with dedicated endpoints (`/validate-*`)
- 30-minute SSH validation caching
- Permission checking: RX (backup capable), RWX (restore-to-source capable)

### Frontend Architecture
- **Schema-Driven HTMX**: All form operations use server-side HTMX with dynamic field rendering
- **Complete HTML Separation**: Zero HTML in handlers - all presentation logic in Jinja2 templates using schema definitions
- **Modular Partial System**: 50+ reusable template components for consistent UI patterns
- **Remaining JavaScript**: Stable, functional features - `backup-browser.js` (file tree), `restore-core.js` (progress tracking), utilities
- No inline scripts in templates - external modules only
- **Data Flow Pattern**: Server data flows through HTML data attributes to JavaScript (e.g., `data-source-paths='{{SOURCE_PATHS_JSON}}'` → `container.dataset.sourcePaths`)
- Provider-agnostic patterns for multi-backup-type support

### UI Patterns
- Progressive disclosure (show complexity when needed)
- Per-job inspection hubs (`/inspect?name=<jobname>`) replace separate pages
- Conditional UI elements (e.g., init button appears only for empty repositories)
- No modals - inline confirmation flows instead

### Multi-Path Source Management (CRITICAL HTMX Pattern)
- **DOM-Safe HTMX**: Never target parent containers that contain the triggering button - causes DOM corruption and HTMX re-scanning failures
- **Add Operation**: Button targets child list (`#source_paths_list`) with `hx-swap="beforeend"` to append new entries
- **Remove Operation**: Button targets own container (`#path_entry_{{ index }}`) with `hx-swap="outerHTML"` for clean removal
- **Form Array Safety**: HTML forms auto-reindex `name="field[]"` arrays, eliminating index gaps from removals
- **JavaScript Index Generation**: Uses `document.querySelectorAll().length` for unique DOM IDs, not form logic
- **Protection**: Path 0 never shows remove button (`{% if path_index > 0 %}`), ensuring at least one path remains

## Known Issues & Technical Debt

- **Source Path Validation Styling**: Functional but needs UX polish
- **Dashboard Restore Status**: No polling/progress display in main job table yet

## Development Rules (Critical - Reference First)

### Environment & Workflow

**Development Environment**: Claude runs in distrobox container with package installation capabilities. Use `./rr` for rebuild/restart during development iterations.
**Testing Paradigm**: Create unit tests before human testing for dramatic subsystem changes. Test files in `tests/` with mocking patterns to avoid dependency issues. Sequence: unit tests → implementation → human integration testing. Use `test_*_standalone.py` for comprehensive pipeline testing with proper component isolation.
**Curl Testing Rule**: ALWAYS use `--max-time 3` (or similar short timeout) when testing with curl. NEVER wait more than a few seconds for hanging requests - timeout indicates bugs that need investigation.
**Decision Authority**: Claude owns technical implementation decisions (patterns, algorithms, code structure). Shane is tech director/product manager - owns design decisions, architectural direction, and product requirements. When uncertain about design preferences or high-level architecture, ask before implementing rather than having changes aborted for clarification. **Present options with reasoned recommendations** - not just choices, but grounded opinions based on sound practice and project cohesiveness.
**Context Management**: Two-file documentation workflow. **CLAUDE.md** (permanent): architecture, patterns, rules, technical debt. **CHANGES.md** (temporal): current session focus, progress, technical notes, next priorities. Session end: fold architectural insights into CLAUDE.md, update CHANGES.md for next session. Post-compression: feed both files to restore complete context efficiently.

### Code Architecture
**Separation of Concerns**: Thin handlers (HTTP coordination), fat services (business logic), validators in `services/` not `handlers/`
**Modularization**: Proactively break up monolithic components. Single responsibility principle. Extract when files exceed ~500 lines.
**Data Structures**: Dataclasses everywhere, `pathlib.Path` operations, type hints
**Multi-provider Pattern**: Unified services with provider-specific logic consolidated

### Frontend Standards
**HTMX**: Schema-driven server-side form rendering with dynamic field generation. JavaScript only for complex interactive features (file trees, progress tracking)
**Templates**: Pure Jinja2 with conditional logic (`{% if %}`, `{% for %}`). **ABSOLUTE RULE: NO HTML in handlers** - all presentation logic in templates using schema definitions.
**Schemas**: `RESTIC_REPOSITORY_TYPE_SCHEMAS`, `MAINTENANCE_MODE_SCHEMAS`, `PROVIDER_FIELD_SCHEMAS` drive dynamic field rendering
**JavaScript**: Always in `/static/` files, never inline in templates. Modular single-responsibility architecture.
**CSS**: Colors ONLY in `/static/themes/{theme}.css`. Structure ONLY in `/static/style.css`
**Assets**: External only - no emoji, no inline styles/scripts
**Forms**: Schema-driven HTMX rendering, multipart form data, dedicated parsers, real-time validation

### HTMX DOM-Safe Targeting (CRITICAL)
**Pattern**: HTMX buttons must NEVER target their own parent container - causes DOM destruction and event handling failures
**Add Operations**: `hx-target="#list_container"` + `hx-swap="beforeend"` (preserve triggering button)
**Remove Operations**: `hx-target="#item_{{ index }}"` + `hx-swap="outerHTML"` (self-destruct pattern)
**Form Integration**: `hx-include="closest form"` for smart form data gathering
**Protection Pattern**: `{% if index > 0 %}` prevents deletion of required elements

### Code Quality
**Standards**: PEP 8, emoji-free, external assets only
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers`, `Jinja2`
**Testing**: Standalone tests in `tests/` with mocking patterns. Use `test_*_standalone.py` for isolated unit tests.
**Containers**: Official containers only (`restic/restic`, future `kopia/kopia`)

### Schema-Driven Architecture Guidelines
**GREEN LIGHTS** (Schema-worthy patterns):
- Type-based dispatch (source types, destination types, providers)
- Field validation patterns repeated across types
- Form rendering based on type selection
- Configuration parsing with type-specific rules

**RED FLAGS** (Don't schema-ize):
- Simple binary choices (enabled/disabled, true/false)
- One-off conditional logic with no variants
- Complex business logic that doesn't follow type patterns
- Error handling or exception cases

**Testing Protocol**: Test schema changes immediately - verify all affected job types and combinations work

## Theming System

**Architecture**: Base + Theme separation - `/static/style.css` (structure) + `/static/themes/{theme}.css` (colors only)
**Loading**: Automatic via `TemplateService` - `{{THEME_CSS_PATH}}` variable
**Configuration**: `global_settings.theme` (default: "dark")
**Core Themes**: `dark.css` and `light.css` (maintained in development)
**Community Themes**: gruvbox, solarized, tokyo-night variants (not tracked in development)
**Extension**: New themes = new CSS file with color variables

## Architecture Reference (Quick Lookup)

**Templates**: Jinja2 environment with autoescape, conditionals (`{% if %}`), loops (`{% for %}`), includes (`{% include %}`)
**Data**: Dataclasses for all structures (`JobFormData`, `SourceConfig`, `DestConfig`), `pathlib.Path` operations
**Validation**: SSH 30min cache, `validators` module, centralized in `models/validation.py` (consolidated module)
**Forms**: HTMX server-side rendering, sectioned UI, dedicated parsers per destination (`_safe_get_value`), inline error display (`FormErrorHandler`)
**UI Paradigm**: Per-job inspection hubs (`/inspect?name=<jobname>`) consolidate logs, status, backup browser, and restore controls into unified interfaces (paradigm shift from separate pages)
**Container Execution**: Unified container execution for all SSH Restic operations (init, backup, restore) using `services/execution.py` with official `restic/restic:0.18.0` containers.
**Backup Browser**: Multi-provider PROVIDERS config (repository vs filesystem), unified JS interface
**Backup Execution**: Unified operation handling via `operations.py` with execution delegation to `services/`
**Restore**: Consolidated restore functionality in `services/restore.py` with unified execution, overwrite checking, and error parsing
**Notifications**: Consolidated notification system in `models/notifications.py` with unified provider management, message formatting, and queue coordination
**API**: Query filtering, CORS, field selection, JSON responses, authentication-ready
**Maintenance System**: Consolidated maintenance operations in `services/maintenance.py` with unified discard/check operations, auto-enabled with safe defaults
**Testing**: Unit coverage with mocking patterns
**Development Environment**: Live testing against `yeti.home.arpa` with actual restic repository at `rest:http://yeti.home.arpa:8000/yeti` (not example data)

## Commands

**Run**: `./rr` (intelligent rebuild and restart)
**Multi-arch**: `./rr multi` (build multiarch image for distribution)
**Debug**: `docker logs -f highball`
**Test Notifications**: `./test_notifications.py`
**Test Units**: `python3 -m unittest tests.test_form_error_handler -v`

## Configuration Schema (User-facing Only)

```yaml
global_settings:
  scheduler_timezone: "UTC"  # default UTC, configurable
  theme: "dark"  # UI theme (dark, light, gruvbox, etc.)
  default_schedule_times:
    hourly: "0 * * * *"     # top of every hour
    daily: "0 3 * * *"      # 3am daily
    weekly: "0 3 * * 0"     # 3am Sundays
    monthly: "0 3 1 * *"    # 3am first of month
  enable_conflict_avoidance: true  # wait for conflicting jobs before running
  conflict_check_interval: 300     # seconds between conflict checks
  delay_notification_threshold: 300  # send notification after this many seconds delay
  notification:
    telegram:
      enabled: false              # enable/disable telegram notifications
      notify_on_success: false    # send telegram notifications for successful jobs
      token: ""                   # bot token from @BotFather
      chat_id: ""                 # chat ID for notifications
    email:
      enabled: false              # enable/disable email notifications
      notify_on_success: false    # send email notifications for successful jobs
      smtp_server: ""             # SMTP server hostname
      smtp_port: 587              # 587 for TLS, 465 for SSL
      use_tls: true               # use TLS encryption (mutually exclusive with SSL)
      use_ssl: false              # use SSL encryption
      from_email: ""              # sender email address
      to_email: ""                # recipient email address
      username: ""                # SMTP authentication username
      password: ""                # SMTP authentication password
  maintenance:
    discard_schedule: "0 3 * * *"         # daily at 3am - combines forget+prune operations
    check_schedule: "0 2 * * 0"           # weekly Sunday 2am (staggered from backups)
    retention_policy:
      keep_last: 7                        # always keep last 7 snapshots regardless of age
      keep_hourly: 6                      # keep 6 most recent hourly snapshots
      keep_daily: 7                       # keep 7 most recent daily snapshots  
      keep_weekly: 4                      # keep 4 most recent weekly snapshots
      keep_monthly: 6                     # keep 6 most recent monthly snapshots
      keep_yearly: 0                      # disable yearly retention by default
    check_config:
      read_data_subset: "5%"              # balance integrity vs performance

backup_jobs:
  job_name:
    source_type: "ssh|local"
    source_config: 
      hostname: "hostname" 
      username: "username"
      source_paths:  # multi-path support
        - path: "/path/one"
          includes: ["*.txt"]
          excludes: ["temp/"]
        - path: "/path/two"
          includes: []
          excludes: ["*.log"]
    dest_type: "ssh|local|rsyncd|restic"  # restic fully functional
    dest_config: {hostname, share} | {repo_type, repo_uri, password, discrete_fields...}  # dual storage: URIs + fields
    schedule: "daily|weekly|hourly|monthly|cron_pattern"
    enabled: true
    respect_conflicts: true     # wait for conflicting jobs (default: true)
    container_runtime: "docker|podman"  # detected during SSH validation, used for restic container execution
    restic_maintenance: auto            # automatic repository maintenance (auto|user|off, Restic only)
    # Optional per-job maintenance overrides (user mode only):
    # maintenance_discard_schedule: "0 4 * * *"     # custom discard schedule
    # retention_policy: {keep_last: 10, ...}        # custom retention policy
    # maintenance_check_schedule: "0 1 * * 0"       # custom check schedule

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

## Roadmap

**Completed 2025-08-20**:
1. ✅ **Schema-Driven Architecture Migration** - Eliminated 100+ lines of hardcoded if/elif logic across 8 files
2. ✅ **Type-Based Dispatch System** - SOURCE_TYPE_SCHEMAS and enhanced DESTINATION_TYPE_SCHEMAS with complete field coverage  
3. ✅ **Smart Pattern Recognition** - Guidelines for appropriate schema application vs preserving complex business logic
4. ✅ **Comprehensive Testing Protocol** - 15+ pathway tests ensuring regression-free migration

**Completed 2025-08-19**:
1. ✅ **Job Form System Complete** - Schema-driven form architecture, dual storage pattern, smart edit forms with change detection
2. ✅ **Dual Storage Pattern** - Store both URIs (execution) and discrete fields (editing) for perfect round-trip data integrity
3. ✅ **Smart Edit UX** - "Code agent" auto-populates fields, dynamic button text, HTMX change detection
4. ✅ **Complete S3 Support** - Added all required authentication fields (region, access_key, secret_key, endpoint)
5. ✅ **Three-Mode Maintenance System** - Migrated from boolean `auto_maintenance` to `restic_maintenance: auto|user|off`

**Completed 2025-08-18**: 
1. ✅ **Jinja2 Template Migration** - Complete migration from legacy `{{VARIABLE}}` syntax to pure Jinja2
2. ✅ **SSH Execution Recovery** - Fixed fundamental backup execution bugs, restored core functionality
3. ✅ **Template Architecture Overhaul** - Established modular partial system with 50+ reusable components

**Completed 2025-08-16**: 
1. ✅ **Container-Based Backup Execution** - Unified container execution for all SSH Restic operations via `CommandExecutionService`
2. ✅ **Comprehensive Unit Testing** - Full pipeline test coverage with proper mocking and component isolation
3. ✅ **Critical Container Command Fix** - Removed duplicate `restic` command from container execution; `restic/restic:0.18.0` has `restic` as entrypoint
4. ✅ **JavaScript Standards Compliance** - Extracted all embedded JavaScript from templates to external `/static/` files with modular architecture
5. ✅ **Backup Logging Enhancement** - Fixed logging to show actual container commands executed instead of simplified restic commands for debugging
6. ✅ **Command Obfuscation Utility** - Created centralized `services/command_obfuscation.py` for DRY password masking across handlers
7. ✅ **Notification System Consolidation** - Unified notification functionality into `models/notifications.py` with integrated provider management and queue coordination
8. ✅ **Restore System Consolidation** - Unified restore functionality into `services/restore.py` with integrated execution, overwrite checking, and error parsing
9. ✅ **Repository Maintenance System** - Consolidated maintenance operations in `services/maintenance.py` with unified discard/check functionality

**Current Priorities**:
1. **Inspect Endpoint Development** - Per-job management interface with integrated backup browser, restore controls, and status monitoring
2. **Core Backup Testing** - Real backup execution, restore operations, notifications, maintenance operations  
3. **Dashboard Status Integration** - Add restore status polling and display "Restoring... N%" in main dashboard job table

## Recent Development Context

**2025-08-20**: Schema-driven architecture migration completed - eliminated 100+ lines of hardcoded type logic, established schema appropriateness guidelines, comprehensive testing protocol applied  
**2025-08-19**: Job form system completed - dual storage pattern for round-trip data integrity, smart edit forms with "code agent" auto-population, HTMX change detection, complete S3 support, three-mode maintenance system
**2025-08-18**: Jinja2 template system completed - all templates converted from legacy `{{VARIABLE}}` syntax to Jinja2 conditionals and includes, architectural cleanup, backup browser SSH execution restored, restore overwrite checking implemented  
**2025-08-16-17**: Container execution unified, notification system consolidated, restore system unified, HTMX form system established

## Legacy Code Reference

**Working Code Location**: `/home/ja2ui0/src/ja2ui0/highball-main/` contains fully functional version of all features. Use as reference when implementing missing functionality - adapt patterns to current consolidated architecture rather than copying files directly.

**Critical SSH Execution Pattern**: Legacy backup browser used separate validator services. Current consolidated architecture implements same functionality via `services/repositories.py` with unified SSH execution patterns.

See CHANGES.md for current session focus and detailed implementation status.

## Next Session Priority

**CRITICAL**: These core systems must be tested before any FastAPI/Pydantic migration:

1. **Real Backup Execution** - Test actual backup execution (not dry-run) with data transfer verification
2. **Restore Operations** - Test complete restore workflow with overwrite protection 
3. **Notification System** - Test email/telegram notifications for job success/failure, queue functionality, template variables
4. **Restic Maintenance Operations** - Test discard/prune/check operations, scheduling, retention policies  
5. **Rsync Patterns** - Test multi-provider support and rsync execution patterns

**Framework Migration**: Only after core functionality verified → FastAPI/Pydantic migration with confidence

**Future Priorities**: Kopia provider support, enhanced Restic features (progress parsing, retention policies), notification template preview 

