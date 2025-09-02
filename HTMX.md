# HTMX SSE Implementation for SSH Validation Progress - STILL BROKEN

## Problem
- HTMX polling with `hx-trigger="every 1s"` + `hx-swap-oob="delete"` doesn't terminate reliably
- Sessions accumulate in `/tmp/ssh_validation_sessions/` forever (no cleanup)
- Console spam from failed querySelector operations when polling continues after element removal
- Validation completes successfully but polling never stops

## Current Status: BROKEN - Multiple Issues Remain

### Current Errors
1. **"Session expired" message still shows** even though validation completes
2. **Literal `\n` characters appear in UI** despite template fixes
3. **JavaScript regex error**: `Pattern attribute value [a-zA-Z0-9_-]+ is not a valid regular expression`
4. **SSE MessageEvent errors** in console from HTMX 2.0.6
5. **UI shows wrong message**: Says "Session expired" instead of actual validation result

### Backend Implementation (PARTIALLY WORKING)
1. **FastAPI Route**: `/ssh/stream/{session_id}` in `app.py:108-110` ✅
2. **SSE Handler**: `stream_ssh_progress()` in `origins/handlers/pages.py:436-494` ⚠️
   - Uses `StreamingResponse` with `text/event-stream` media type ✅
   - SSE format: Multi-line data format with `data: line` per HTML line ✅
   - Event types: `progress`, `success`, `error` ✅
   - Session file creation and reading ✅
   - **BROKEN**: Template rendering includes literal `\n` despite `| replace('\n', '<br>') | safe`
   - **BROKEN**: Session expiration logic triggers incorrectly

### Frontend Implementation (ATTEMPTED, FAILING)
1. **HTMX SSE Extension**: Added to `templates/pages/ssh_config.html` ✅
   ```html
   <script src="/static/sse.min.js"></script>
   ```

2. **Progress Template**: `templates/partials/ssh_validation_progress.html` ⚠️
   ```html
   <div class="alert alert-info" id="ssh-validation-container"
        hx-ext="sse" 
        sse-connect="/ssh/stream/{{ session_id }}"
        sse-swap="progress,success,error"
        hx-target="this"
        hx-swap="outerHTML">
   ```
   **BROKEN**: HTMX 2.0.6 compatibility issues with SSE extension

3. **Result Template**: `templates/partials/ssh_validation_result.html` ⚠️
   - Added `| replace('\n', '<br>') | safe` filters
   - Removed problematic `hx-swap-oob` targeting non-existent elements
   - **BROKEN**: Still shows literal `\n` characters

### Issues Attempted But Still Broken
1. **HTMX 2.0 Upgrade**: Updated to 2.0.6 - created new compatibility issues
2. **SSE Format**: Tried escaping `\n` → `\\n`, then multi-line data format - still broken
3. **OOB Swaps**: Removed targeting non-existent elements - fixed console errors but SSE still fails
4. **Template Filters**: Added newline conversion - not working
5. **Session Management**: Files created correctly but "expired" logic wrong

### Root Cause Analysis Needed
1. **Why is "Session expired" showing** when session files exist and contain completed data?
2. **Why are `\n` characters literal** in UI despite template filters?
3. **What's causing the JavaScript regex error** in the form?
4. **Is HTMX 2.0.6 + SSE extension compatible** or should we revert?
5. **Should we abandon SSE** and try a different approach?

### Files Modified (Multiple Iterations, Still Broken)
- `app.py`: Added SSE route ✅
- `origins/handlers/pages.py`: Added SSE streaming method, multiple escape attempts ⚠️
- `templates/partials/ssh_validation_progress.html`: Multiple SSE attempts ❌
- `templates/partials/ssh_validation_result.html`: Template filter attempts ❌
- `templates/pages/ssh_config.html`: Added SSE extension ⚠️
- `static/htmx.min.js`: Updated to 2.0.6 ⚠️

### Next Session Priorities
1. **Investigate why validation shows "Session expired"** when session completes successfully
2. **Fix literal `\n` display** in final error messages  
3. **Resolve JavaScript regex error** in form validation
4. **Test if downgrading HTMX** fixes SSE compatibility
5. **Consider alternative approaches** if SSE continues to fail

### Alternative Approaches to Consider
- Return to HTMX 1.9.10 with simpler polling fix
- Use WebSockets instead of SSE
- Use regular AJAX polling with better termination logic
- Simplify to synchronous validation (no real-time progress)

## Important Notes
- **DO NOT** assume this is working based on backend logs
- **DO NOT** say "it's working" until UI shows proper validation results
- Multiple "fixes" have been attempted and failed
- Session files are created correctly but UI logic is broken
- SSE events are sent but HTMX is not processing them correctly