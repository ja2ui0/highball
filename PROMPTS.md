# Prompts

## Feature
Goal: Add <feature>.
Where: routes in app.py; logic in handlers/*.py; reusable code in services/*.py; UI in templates/.
Constraints: follow existing patterns, no new deps, small commits, show diff first.
Deliver: short plan + one unified patch block.

## Bugfix
Given: stack trace or behavior.
Task: find root cause across handlers/services; fix with smallest safe change; update validator if needed.
Deliver: short plan + diff.

## Refactor
Target: <module>.
Keep behavior the same; split long functions; add docstrings; organize imports.
Deliver: short plan + diff.

