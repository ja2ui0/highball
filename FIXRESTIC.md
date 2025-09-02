# RESTIC DESTINATION FORM REGRESSION FIX

## PROBLEM SUMMARY
Restic repository type selection on destinations form (/dests) is broken - selecting repository type (REST, S3, etc.) shows no sub-fields, form appears incomplete.

## ROOT CAUSE IDENTIFIED
`/dests/restic-repo-fields` endpoint returns empty response due to form value extraction bug.

## TECHNICAL DETAILS

### Current Status
- Template: `/templates/partials/restic_repo_fields_dynamic.html` expects `field_values` parameter
- Handler: `dests/handlers/pages.py:render_restic_repo_fields_htmx()` was missing `field_values={}`
- ✅ FIXED: Added `field_values={}` to template call (line 247)

### Remaining Issue  
Form value extraction in `_get_form_value()` method:
- Debug shows: `repo_type = "['rest']"` (string repr of list)
- Should be: `repo_type = "rest"` (actual string value)
- Form data: `{'repo_type': ['rest']}` (correct - FastAPI form parsing)

### Problem Location
File: `dests/handlers/pages.py` lines 102-107
```python
def _get_form_value(self, form_data: Dict[str, Any], key: str, default: str = '') -> str:
    value = form_data.get(key, default)
    if isinstance(value, list) and len(value) > 0:
        return value[0]  # This should return 'rest' but returns "['rest']"
    return value if value else default
```

### Expected Template Logic
Template checks: `{% if repo_type and repo_schemas[repo_type] %}`
- Needs `repo_type = "rest"` to find `RESTIC_REPOSITORY_TYPE_SCHEMAS['rest']`
- Currently gets `repo_type = "['rest']"` which doesn't match schema key

### Next Steps
1. Fix `_get_form_value()` to properly extract string from list
2. Test: `curl -X POST http://localhost:8087/dests/restic-repo-fields -d "repo_type=rest"`
3. Should return hostname/port fields for REST server configuration
4. Remove debug print statement after fix confirmed

### Working Schemas
- `RESTIC_REPOSITORY_TYPE_SCHEMAS['rest']` exists in `dests/schema.py`
- Has `hostname`, `port`, `path` fields defined
- Progressive disclosure system was implemented but plumbing broke

### Test Command
```bash
curl -X POST http://localhost:8087/dests/restic-repo-fields -d "repo_type=rest" -H "Content-Type: application/x-www-form-urlencoded"
```

Should return HTML with hostname/port input fields, currently returns empty.

## CONTEXT
This regression occurred during mega-dispatcher obliteration refactor. Restic progressive disclosure worked before - we're restoring existing functionality, not building new features.