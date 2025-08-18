# Template Indentation Fix

## Status: Partially Complete

### **Fixed Files (4/21+):**
- ✅ `job_form_source.html` - Left-aligned, proper indentation
- ✅ `job_form_dest_basic.html` - Left-aligned, proper indentation  
- ✅ `job_form_dest_restic.html` - Complete rewrite, left-aligned
- ✅ `job_form_actions.html` - Left-aligned, proper indentation

### **Remaining Files (17+):**
Files with excessive leading whitespace (12+ spaces) that need left-alignment:

```
/templates/partials/toggle_switch.html
/templates/partials/job_form_schedule.html
/templates/partials/job_actions_section.html
/templates/partials/password_field.html
/templates/partials/job_notifications_section.html
/templates/partials/schedule_defaults_section.html
/templates/partials/job_form_maintenance.html
/templates/partials/notification_provider_dynamic.html
/templates/partials/source_path_entry.html
/templates/partials/global_settings_section.html
/templates/partials/validation_button_with_results.html
/templates/partials/job_row.html
/templates/partials/notification_section.html
/templates/partials/config_form_actions.html
/templates/partials/log_controls.html
/templates/partials/job_source_options_section.html
/templates/partials/job_identity_section.html
/templates/partials/form_field.html
```

## **Fix Pattern:**
1. **Remove excessive leading whitespace** (8-16+ spaces)
2. **Left-align content** - treat each partial as document root
3. **Use 4-space indentation** from root level
4. **Preserve HTML structure** - only fix indentation

## **Command to Find Files:**
```bash
find /templates/partials -name "*.html" -exec grep -l "^            " {} \;
```

## **Example Fix:**
**Before:**
```html
            <div class="form-group">
                <label>Content</label>
            </div>
```

**After:**
```html
<div class="form-group">
    <label>Content</label>
</div>
```

**Priority**: Low - functional but cosmetic issue.