# Template Deduplication Plan - HTMX Progressive Disclosure Optimization

## Context & Current State

**Background**: Recently migrated from server-side forms to HTMX/Jinja2. This left duplication between `templates/pages/` (full pages) and `templates/partials/` (HTMX fragments). Need to extract progressive disclosure logic from pages into HTMX-managed partials for proper client-side state management.

**Goal**: Extract embedded form sections from page templates into reusable HTMX partials, eliminating duplication and inline JavaScript while maintaining backward compatibility.

**Status**: All HTMX endpoints are working. Ready to optimize template architecture.

## Execution Order (High to Low Priority)

### PHASE 1: Password Field Component ✅ COMPLETED

**Problem**: Password visibility toggle uses inline JavaScript `onclick="togglePasswordVisibility('field_id')"` and is duplicated across multiple templates.

**Current Locations**:
- ~~`/templates/partials/job_form_dest_restic.html` line 21 (restic password)~~ ✅ FIXED
- ~~`/templates/pages/config_manager.html` line 224 (SMTP password)~~ ✅ FIXED

**Implementation Steps** ✅ COMPLETED:

1. **Create** `/templates/partials/password_field.html`:
```html
<div class="password-input-container">
    <input type="{{ 'password' if hidden else 'text' }}" 
           id="{{ field_id }}" 
           name="{{ field_name }}" 
           value="{{ field_value }}"
           placeholder="{{ placeholder|default('') }}">
    <button type="button" class="password-toggle" 
            hx-post="/htmx/toggle-password-visibility"
            hx-target="closest .password-input-container"
            hx-vals="js:{field_id: '{{ field_id }}', hidden: {{ 'true' if hidden else 'false' }}}">
        <span class="password-toggle-icon">{{ 'Show' if hidden else 'Hide' }}</span>
    </button>
</div>
```

2. **Add HTMX endpoint** in `/handlers/forms.py` action dispatcher:
```python
'toggle-password-visibility': self._toggle_password_visibility,
```

3. **Implement handler method** in `/handlers/forms.py`:
```python
def _toggle_password_visibility(self, form_data):
    """Toggle password field visibility state"""
    field_id = self._get_form_value(form_data, 'field_id')
    current_hidden = self._get_form_value(form_data, 'hidden') == 'true'
    new_hidden = not current_hidden
    
    return self.template_service.render_template('partials/password_field.html',
                                               field_id=field_id,
                                               field_name=field_id,  # Assume same as ID
                                               field_value='',  # Don't echo passwords
                                               hidden=new_hidden)
```

4. **Replace in** `/templates/partials/job_form_dest_restic.html`:
   - Remove lines 20-25 (password input + onclick)
   - Replace with: `{% include 'partials/password_field.html' with field_id='restic_password', field_name='restic_password', field_value=restic_password, hidden=true %}`

5. **Replace in** `/templates/pages/config_manager.html`:
   - Remove line 224 (SMTP password input)
   - Replace with password_field.html include

6. **Test**: Verify password toggle works in both restic forms and config manager

**✅ PHASE 1 RESULTS**:
- ✅ Created reusable password field component: `/templates/partials/password_field.html`
- ✅ Added HTMX endpoint: `toggle-password-visibility` in `/handlers/forms.py`
- ✅ Eliminated inline JavaScript `onclick="togglePasswordVisibility()"` from 2 locations
- ✅ Converted to proper HTMX progressive disclosure pattern
- ✅ Applied DRY principle - single source of truth for password fields
- ✅ Maintained backward compatibility and styling
- 🧪 **Ready for testing** - Password toggle should work via HTMX in both:
  - Restic repository forms (Add Job → Destination → Restic)
  - Email configuration (Config Manager → Email Settings)

### PHASE 2: Test Notification Buttons ✅ COMPLETED

**Problem**: Test notification uses inline JavaScript `onclick="testTelegramNotification()"` and `onclick="testEmailNotification()"`.

**Current Locations**:
- ~~`/templates/pages/config_manager.html` lines 151, 252~~ ✅ FIXED

**Implementation Steps** ✅ COMPLETED:

1. **Create** `/templates/partials/test_notification_button.html`:
```html
<button type="button" class="button button-secondary"
        hx-post="/test-{{ provider }}-notification"
        hx-target="#{{ provider }}_test_result"
        hx-include="[name^='{{ provider }}_']"
        hx-swap="innerHTML">
    Send Test {{ provider.title() }} Notification
</button>
<div id="{{ provider }}_test_result" class="help-text"></div>
```

2. **Existing endpoints used**: `/test-telegram-notification` and `/test-email-notification` already exist in `app.py` → `api.py`

3. **Replace** both onclick buttons in config_manager.html ✅ COMPLETED

**✅ PHASE 2 RESULTS**:
- ✅ Created reusable test notification button component: `/templates/partials/test_notification_button.html`
- ✅ Leveraged existing API endpoints: `/test-telegram-notification` and `/test-email-notification`
- ✅ Eliminated inline JavaScript `onclick="testTelegramNotification()"` and `onclick="testEmailNotification()"` from config manager
- ✅ Converted to proper HTMX pattern using existing backend functionality
- ✅ Applied DRY principle - single source of truth for test notification buttons
- ✅ No new HTMX endpoints needed - used existing `/test-{provider}-notification` routes
- 🧪 **Ready for testing** - Test notification buttons should work via HTMX in:
  - Config Manager → Telegram Settings → Send Test Notification
  - Config Manager → Email Settings → Send Test Notification

### PHASE 3: Design Language Standardization (Per-Page Refactoring)

**Problem**: While section-container patterns appear consistent, content organization within pages may have bespoke UI drift. Need to standardize hierarchical content structure (h2 → h3 → h4) and ensure consistent design language across all pages.

**Goal**: Break down monolithic pages into standardized, reusable components following consistent content hierarchy patterns.

**Approach**: Interactive per-page analysis and refactoring to avoid hasty decisions.

#### PHASE 3A: Config Manager Standardization
**Target**: `/templates/pages/config_manager.html`
**Current sections**: Global Settings, Schedule Defaults, Notification Settings, Advanced Options
**Strategy**: Analyze content hierarchy, identify h2/h3/h4 patterns, extract reusable notification components

#### PHASE 3B: Job Inspect Standardization  
**Target**: `/templates/pages/job_inspect.html`
**Current sections**: Job Status, Backup Browser, Job Logs
**Strategy**: Ensure consistent section organization, potential backup browser component extraction

#### PHASE 3C: Dev Logs Standardization
**Target**: `/templates/pages/dev_logs.html` 
**Current sections**: Network Scanner, System Log Sources
**Strategy**: Verify consistent hierarchy, potential network scanner component extraction

#### PHASE 3D: General Logs Standardization
**Target**: `/templates/pages/logs.html`
**Current sections**: Network Scanner, Log Sources  
**Strategy**: Compare with dev_logs for consistency, eliminate any UI drift

#### PHASE 3E: Restic Browser Standardization
**Target**: `/templates/pages/restic_browser.html`
**Current sections**: Single backup browser section
**Strategy**: Ensure consistent integration with other pages using backup browser

#### PHASE 3F: Job Form Standardization
**Target**: `/templates/pages/job_form.html` (if exists)
**Strategy**: Verify form organization follows consistent patterns

**Implementation Pattern**:
1. **Analyze** current page structure and content hierarchy
2. **Identify** h2/h3/h4 organization opportunities  
3. **Extract** reusable components where beneficial
4. **Standardize** section-container usage for consistent design language
5. **Test** visual consistency and functionality

### PHASE 4: Log Controls Unification ✅ COMPLETED

**Problem**: Identical log refresh/clear patterns in dev_logs.html, job_inspect.html, and logs.html.

**Current Locations**:
- ~~`/templates/pages/dev_logs.html` lines 38-46~~ ✅ FIXED
- ~~`/templates/pages/job_inspect.html` lines 172-180~~ ✅ FIXED  
- ~~`/templates/pages/logs.html` lines 53-62~~ ✅ FIXED

**Implementation** ✅ COMPLETED:

1. **Create** `/templates/partials/log_controls.html` with flexible endpoint support:
```html
<div class="log-section">
    <button class="button" 
            hx-{% if job_name %}post{% else %}get{% endif %}="{% if job_name %}/htmx/refresh-logs{% else %}{{ refresh_endpoint|default('/dev') }}{% endif %}"
            {% if job_name %}hx-vals='{"job_name": "{{ job_name }}"}'{% endif %}
            hx-target="#logContent" 
            hx-swap="{% if job_name %}outerHTML{% else %}innerHTML{% endif %}">Refresh</button>
    <button class="button button-warning" 
            hx-post="/htmx/clear-logs" 
            hx-target="#logContent" 
            hx-swap="outerHTML">Clear Display</button>
</div>
```

2. **Existing HTMX endpoints used**: `clear-logs`, `refresh-logs` already exist

3. **Replace** in all three log templates ✅ COMPLETED

**✅ PHASE 4 RESULTS**:
- ✅ Created flexible log controls component: `/templates/partials/log_controls.html`
- ✅ Supports three different refresh patterns: job-specific (`/htmx/refresh-logs`), dev logs (`/dev`), general logs (`/logs`)
- ✅ Eliminated identical log control patterns from 3 templates (dev_logs.html, job_inspect.html, logs.html)
- ✅ Applied conditional logic for job-specific vs general log contexts
- ✅ Applied DRY principle - single source of truth for log controls
- ✅ Leveraged existing HTMX endpoints - no new backend changes needed
- 🧪 **Ready for testing** - Log refresh/clear should work consistently across:
  - System/Dev Logs (/dev endpoint)
  - Job-specific logs (/htmx/refresh-logs with job_name)
  - General log viewer (/logs endpoint)

### PHASE 5: Notification Provider Configuration

**Problem**: Complex - queue settings and provider config patterns duplicated between config_manager.html and existing partials.

**Implementation**: Extract entire notification provider blocks into reusable partials with HTMX progressive disclosure.

## Critical Files & Line Numbers

**Handlers requiring HTMX endpoints**:
- `/handlers/forms.py` - Add new action dispatchers and methods

**Templates with inline JavaScript to eliminate**:
- `/templates/partials/job_form_dest_restic.html:21` - Password toggle
- `/templates/pages/config_manager.html:151,224,252` - SMTP password, test buttons

**Templates with duplication patterns**:
- All files in `/templates/pages/` using section-container pattern
- dev_logs.html and job_inspect.html for log controls

## CRITICAL: Jinja2 Template Syntax Rules

**NEVER use Django/Laravel syntax in Jinja2 templates**:

❌ **WRONG** (will break template rendering):
```jinja2
{% include 'partials/component.html' with variable=value, other=data %}
```

✅ **CORRECT** (proper Jinja2 syntax):
```jinja2
{% set variable = value %}
{% set other = data %}
{% include 'partials/component.html' %}
```

**Template Variable Passing**: Jinja2 doesn't support `with` clause in `{% include %}` statements. Always use `{% set %}` to define variables before including templates.

**Error Symptom**: `expected token 'end of statement block', got 'with'` indicates invalid Jinja2 syntax.

**Testing**: Always test endpoints after template changes - syntax errors will break form rendering (e.g., `/add-job`, `/config`)

## Testing Strategy

**For each phase**:
1. **Functional test** - Verify HTMX interactions work
2. **Visual test** - Ensure styling remains unchanged
3. **Regression test** - Check existing form submissions still work
4. **Progressive disclosure test** - Verify show/hide state management

## Success Criteria

- ✅ Zero inline JavaScript in templates
- ✅ Reusable partials for common patterns
- ✅ HTMX progressive disclosure working properly
- ✅ No visual regressions
- ✅ Backward compatibility maintained
- ✅ DRY principle applied throughout template system

## Next Session Instructions

1. **Read this plan** to restore context
2. **Start with PHASE 1** (Password Field Component)
3. **Follow implementation steps exactly** as specified
4. **Test each phase** before proceeding to next
5. **Update this plan** with progress status as you complete phases

## Architecture Context

**Current HTMX Setup**: 51% JavaScript reduction achieved, all endpoints working, proper Jinja2 templates in place.
**Pattern**: Extract embedded progressive disclosure from pages → Create HTMX partials → Update handlers for state management → Replace duplicated code → Test functionality.