# templates/

Jinja-style pages. Keep logic minimal.

Key pages
- `dashboard.html`: summary and actions.
- `add_job.html`, `edit_job.html`: job forms.
- `job_display.html`: details and run controls (if present).
- `config_editor.html`: config view/edit.
- `logs.html`: log list and tail.

Context shape
- Pass simple dicts from handlers, e.g.:
  - `jobs`: list of job dicts
  - `hosts`: list of host dicts
  - `flash`: list of notices/errors

