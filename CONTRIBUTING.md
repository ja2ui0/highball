# Contributing Guide
This project is structured around feature pillars (`jobs/`, `origins/`, `dests/`, `admin/`), each with their own handlers, schemas, and services.

Legacy directories (`handlers/`, `models/`, `services/`) still exist so the app runs, but **all new or refactored code must go into the clean schema.**
## 1. Entrypoint
- `app.py` is the only entrypoint.
- It must only:
	- Create the FastAPI app
	- Register routers (`app.include_router(...)`)
	- Configure middleware, startup/shutdown events
- 🚫 Never add business logic or routes here.

Example:
```python
from fastapi import FastAPI
from jobs.handlers import pages as jobs_pages
from origins.handlers import pages as origins_pages

app = FastAPI()
app.include_router(jobs_pages.router, prefix="/jobs")
app.include_router(origins_pages.router, prefix="/origins")
```
## 2. Feature Pillars
Each feature folder (`jobs/`, `origins/`, `dests/`, `admin/`) contains:
- `handlers/pages.py` → all endpoints for that feature
	- GET: render templates / pages / HTMX fragments
	- POST/PUT/DELETE: process form submissions, call services
	- Handlers must stay thin: parse request, call service, return result
- `schema.py` → Pydantic models and validation logic
	- Defines request/response shapes
	- No side effects, no business logic
- `services/` → business logic for that feature
	- One module per concern (`backup.py`, `restore.py`, `schedule.py`, etc.)
	- Handlers never contain business logic — always delegate to services

Example structure:
```bash
jobs/
  handlers/
    pages.py
  schema.py
  services/
    backup.py
    restore.py
    schedule.py
```
## 3. Config
- `config/` → runtime YAML, secrets, and environment files
- `config.py` → CRUD accessor for config values
  - Only `config.py` reads/writes config files
  - Handlers and services must never touch raw YAML/ENV directly
## 4. Presentation
- `templates/` → Jinja2 templates (`pages/` and `partials/`)
- `static/` → CSS, JS, images, themes
- 🚫 No business logic. Templates and static files only consume data passed from handlers.
## 5. Legacy Code
- `handlers/`, `models/`, `services/` (top-level) = legacy.
- Keep existing code here until refactored, but:
  - 🚫 Never put new code here.
  - ✅ When refactoring, move code into the correct pillar and update imports.
## 6. Growth Rules
- If a feature grows too big, split further under its pillar:
```bash
jobs/
  services/
    scheduler/
      cron.py
      validation.py
```
- If you need a new global concern (e.g. auth), create a new pillar (`auth/`) with the same structure.
- Only use top-level `handlers/` for true global routes (e.g. `/health`, `/login`) until a proper pillar exists.
## 7. Guiding Principles
- Handlers glue things together. Thin, endpoint-focused.
- Services do the work. Fat, domain-specific logic.
- Schemas define shapes. Pure data, no side effects.
- Config feeds everything. Always through `config.py`.
- Templates and static show it. No logic.

✅ Follow this structure when creating or moving code.
🚫 Do not add new modules under legacy folders.
