# Repository Unlock Domain Migration

## Issue
Repository unlocking is currently in `jobs` handler but belongs in `dests` (destinations/restic) domain.

## What Needs To Be Done

1. **Move unlock methods from jobs to destinations handler:**
   - Move `unlock_repository_htmx(job_name: str)` from `jobs/handlers/pages.py` to `dests/handlers/pages.py`
   - Move `unlock_repository_post_htmx(request)` from `jobs/handlers/pages.py` to `dests/handlers/pages.py`

2. **Update app.py routes to call destinations handler:**
   ```python
   # Change line 270:
   return jobs_handler.unlock_repository_htmx(job)
   # To:
   return destinations_handler.unlock_repository_htmx(job)
   
   # Change line 495:
   return await jobs_handler.unlock_repository_post_htmx(request)
   # To: 
   return await destinations_handler.unlock_repository_post_htmx(request)
   ```

3. **Add note about DRY violation in MVC.md:**
   Need to document the redundant GET/POST routes issue and suggest consolidation approach.

## Context
- Part of pure switchboard refactor
- Repository operations belong in destinations domain, not jobs domain
- This addresses both domain separation and form parsing migration