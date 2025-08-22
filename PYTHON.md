# Python 3.13 Migration Plan

## Current State
- **Container**: Python 3.11.13 (`python:3.11-slim` base image)
- **Issue**: `cgi.FieldStorage` deprecated, causing warnings, will be removed in Python 3.13
- **Critical**: HTMX multipart form parsing **MUST NOT BREAK** - cornerstone of page handling

## Migration Requirements
1. **Upgrade base image** from `python:3.11-slim` to `python:3.13-slim` in `Dockerfile.base`
2. **Replace cgi.FieldStorage** with modern multipart parser
3. **Zero breakage** of HTMX form functionality
4. **Maintain identical behavior** for form parsing

## Current Usage Analysis Needed

### Files Using cgi.FieldStorage
- `app.py:191` - Main request handler multipart parsing
- `handlers/forms.py:747` - Form handler multipart parsing

### Usage Pattern
```python
form = cgi.FieldStorage(
    fp=self.rfile,
    headers=self.headers, 
    environ={'REQUEST_METHOD': 'POST'}
)

# Convert to dict format
form_data = {}
for field in form.list:
    # Handle arrays and single values
```

## Next Claude Tasks

### Phase 1: Architecture Review
1. **Analyze current multipart parsing**: Read `app.py:190-210` and `handlers/forms.py:745-770`
2. **Document exact behavior**: How arrays, files, and field names are handled
3. **Identify HTMX dependencies**: What form data formats HTMX expects

### Phase 2: Replacement Research  
1. **Evaluate options**:
   - `python-multipart` library (FastAPI standard)
   - `email.message` (stdlib but complex)
   - Custom parser using `email.parser`
2. **Test compatibility** with HTMX multipart submissions
3. **Verify array handling** (critical for dynamic forms)

### Phase 3: Implementation
1. **Add replacement library** to `requirements.txt` 
2. **Create drop-in replacement function** maintaining identical API
3. **Update both usage locations** with new parser
4. **Test HTMX forms thoroughly** (job creation, editing, validation)

### Phase 4: Base Image Upgrade
1. **Update Dockerfile.base**: `python:3.11-slim` → `python:3.13-slim`
2. **Rebuild and test** entire application
3. **Verify no other Python 3.13 compatibility issues**

## Success Criteria
- ✅ No deprecation warnings
- ✅ All HTMX forms work identically  
- ✅ Job creation/editing unchanged
- ✅ Multipart array handling preserved
- ✅ File upload capability maintained (if used)

## Risk Mitigation
- **Test on copy** before modifying production Dockerfile
- **Document exact form parsing behavior** before changes
- **Keep old code commented** until migration verified
- **Focus on `python-multipart`** as most likely candidate (proven with FastAPI/HTMX)