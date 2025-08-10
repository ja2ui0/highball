# services/

Holds reusable logic with no web assumptions.

- `ssh_validator.py`: check reachability, auth, rsync/ssh binaries.
- `template_service.py`: shared template helpers.

Future
- `rclone_runner.py`
- `restic_runner.py`
- `rsync_runner.py`

Rules
- Pure functions where possible.
- No flask/request objects here.
- Return structured results (dicts with `ok`, `msg`, `data`).

