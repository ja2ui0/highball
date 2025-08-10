# Decisions (ADR-lite)

- Routing in `app.py`, not a framework router. Keeps app minimal.
- Jobs and hosts live in YAML for now. DB can come later if needed.
- Rsync is the first engine. rclone and restic follow with the same job schema.
- Validation is centralized in `handlers/job_validator.py`.
- All multi-file edits should be small and reversible. Prefer multiple commits over one huge one.
- Docker is first-class and required, compose is preferred. Local Python runs are up to the user to figure out.
