# handlers/

Responsibilities
- Parse and validate input.
- Orchestrate services.
- Choose a template and context.

Files
- `dashboard.py`: overview pages and summaries.
- `backup.py`: run/preview jobs, show results.
- `config_handler.py`: load/save config safely.
- `job_manager.py`: CRUD for jobs and hosts.
- `job_form_parser.py`: form → normalized job dict.
- `job_validator.py`: schema and business rules.
- `logs.py`: log listing and tail view.

Guidelines
- Keep functions short.
- No direct shell calls here. Use services.
- Return simple dicts to templates.

