# Task 001 — Make SSH source → rsyncd destination work

## Problem
When source is SSH (`user@host:/path`) and destination is rsync daemon (`rsync://host/module` or `host::module`), running rsync locally fails with: “The source and destination cannot both be remote.”

## Goal
For SSH-source + rsyncd-dest, run **rsync on the source host via SSH**: /usr/bin/ssh user@src -- "/usr/bin/rsync [existing opts] <remote_src_path> rsync://<dst_host>/<module>"

Keep all other flows unchanged (local↔ssh, local↔rsyncd).

## Where to edit
Modify the existing rsync command build/execute code (where we currently log `COMMAND EXECUTED:`). Keep the change as small as possible. No broad refactors.

## Implementation sketch
- Detect endpoints:
  - SSH source matches `^[^:@\s]+@[^:\s]+:.+`
  - rsyncd dest matches `^(rsync://[^/\s]+/.+|[^:/\s]+::[^/\s]+(?:/.*)?)$`
- If SSH→rsyncd:
  - Split `user@host:/path` → `user@host`, `/path`
  - Build the same rsync argv as today (preserve flags: `-a`, `--dry-run`, `--verbose`, `--info=stats1`, `--delete`, `--delete-excluded`, includes/excludes)
  - Convert that argv into a **single quoted string** for the remote shell (use `shlex.join`)
  - Execute locally: `["/usr/bin/ssh", userhost, "--", remote_cmd_string]`
- Log exactly what will run.

## Constraints
- Docker-only app. **Do not** change Dockerfiles or add dependencies.
- No new Python packages; use stdlib (`shlex`).
- Keep existing behavior for all non-SSH→rsyncd cases.

## Acceptance criteria
- Previous failure case succeeds (dry run returns 0 if hosts reachable).
- Log shows, for SSH→rsyncd:
COMMAND EXECUTED:
/usr/bin/ssh root@yeti -- "/usr/bin/rsync -a --dry-run --verbose --info=stats1 --delete --delete-excluded /mnt/data/archive/retro rsync://nuc/retro"

- Other flows (local↔ssh, local↔rsyncd) unchanged.
- Minimal code diff; no new deps.

## Optional tiny helper (if needed)
```python
import re, shlex
SSH = re.compile(r"^[^:@\s]+@[^:\s]+:.+")
RSYNCD = re.compile(r"^(rsync://[^/\s]+/.+|[^:/\s]+::[^/\s]+(?:/.*)?)$")
def is_ssh(s): return bool(SSH.match(s))
def is_rsyncd(s): return bool(RSYNCD.match(s))
def split_ssh_source(src):
  userhost, path = src.split(":", 1)
  return userhost, path
def wrap_remote(rsync_bin, opts, src_ssh, dst_rsyncd, ssh_bin="/usr/bin/ssh"):
  userhost, remote_path = split_ssh_source(src_ssh)
  remote_cmd = shlex.join([rsync_bin, *opts, remote_path, dst_rsyncd])
  return [ssh_bin, userhost, "--", remote_cmd], remote_cmd


