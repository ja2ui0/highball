# Multipart Form Data Refactor

**Completed**: 2025-08-14  
**Status**: Repo-wide conversion from URL-encoded to multipart form data

## Summary

Converted entire application from `application/x-www-form-urlencoded` to `multipart/form-data` for better array handling, enhanced security, and future file upload support.

## Changes Made

### Backend (app.py)
```python
# Before: Only URL-encoded parsing
post_data = self.rfile.read(content_length).decode('utf-8')
form_data = parse_qs(post_data)

# After: Auto-detection with backward compatibility
content_type = self.headers.get('Content-Type', '')
if content_type.startswith('multipart/form-data'):
    form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
    # Convert to dict format expected by handlers with array support
else:
    # Legacy URL-encoded support
```

### Frontend JavaScript Changes
1. **restore-restic.js**: `URLSearchParams` → `FormData`
2. **restore-core.js**: Removed `Content-Type: application/x-www-form-urlencoded` header
3. **job-form-restic.js**: Use FormData directly, removed URLSearchParams conversion
4. **config-notifications.js**: Both telegram and email test functions converted to FormData

### HTML Template Changes
Added `enctype="multipart/form-data"` to all forms:
- `templates/add_job.html`
- `templates/job_form.html` 
- `templates/config_manager.html`
- `templates/config_editor.html`

## Benefits

- **Array Handling**: Better support for multi-value fields like `selected_paths`
- **Security**: No plaintext secrets in URLs, better password handling
- **Consistency**: Unified form handling across application
- **Future-Ready**: File upload support when needed
- **Backward Compatibility**: Auto-detection supports both formats

## Rollback Instructions

If multipart parsing causes issues:

1. **Revert app.py POST handler**:
```python
def do_POST(self):
    # Simple URL-encoded only
    content_length = int(self.headers.get('Content-Length', 0))
    post_data = self.rfile.read(content_length).decode('utf-8')
    form_data = parse_qs(post_data)
```

2. **Revert JavaScript files**:
   - restore-restic.js: `FormData` → `URLSearchParams`
   - restore-core.js: Add back `Content-Type: application/x-www-form-urlencoded`
   - job-form-restic.js: Add back URLSearchParams conversion
   - config-notifications.js: Revert to string concatenation

3. **Revert HTML templates**: Remove all `enctype="multipart/form-data"` attributes

## Key Files Modified

**Backend**:
- `/app.py` - POST handler with auto-detection

**Frontend**:
- `/static/restore-restic.js` - FormData implementation
- `/static/restore-core.js` - Header removal
- `/static/job-form-restic.js` - Direct FormData usage
- `/static/config-notifications.js` - FormData for both notification types

**Templates**:
- `/templates/add_job.html` - Form encoding
- `/templates/job_form.html` - Form encoding  
- `/templates/config_manager.html` - Form encoding
- `/templates/config_editor.html` - Form encoding

## Testing

Unit tests in `/tests/test_multipart_forms.py` verify:
- Multipart form parsing with arrays
- Backward compatibility with URL-encoded forms
- JavaScript FormData generation
- All refactored endpoints function correctly

Run tests: `python3 -m unittest tests.test_multipart_forms -v`

## Debugging

If forms break:
1. Check browser Network tab - Content-Type should be `multipart/form-data; boundary=...`
2. Verify backend receives `cgi.FieldStorage` data correctly
3. Check handler expectations match new format
4. Test with both multipart and URL-encoded to verify auto-detection

## Notes

- URLSearchParams usage in job-form-core.js is for GET query parameters, not POST data - left unchanged
- All handlers expect same format, conversion happens at app.py level
- File upload ready but not implemented - would use `field.file` in FieldStorage
- Passwords now better protected in multipart vs URL params