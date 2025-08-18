# Critical Session Advice - Delete After Reading

## 1. Architecture Enforcement Pattern
**Shane will stop you from violating architecture rules** - He has mentioned "no HTML in handlers" and "no emoji" multiple times because I kept making the same mistakes. When he corrects architectural violations, it's not a suggestion - it's a pattern you MUST internalize immediately. The Jinja2 addition was specifically to solve the "no HTML in handlers" problem. Use `{% if %}` conditionals in templates, pass simple data variables from handlers.

## 2. Working Code Adaptation Strategy  
**The legacy code at `/home/ja2ui0/src/ja2ui0/highball-main/` is your lifeline** - When functionality is broken or missing, Shane's guidance is always "look at the working code" and "implement it properly, the way we know works." But critical rule: ADAPT the patterns to current consolidated architecture, don't copy files. The SSH execution recovery was successful because I found the working pattern (`ResticValidator.list_repository_snapshots`) and implemented it properly in the current service (`ResticRepositoryService.list_snapshots_with_ssh`).

## 3. Test Early in Architectural Transitions
**You're in a critical flux state** - The restore functionality is implemented but completely untested. Jinja2 is partially implemented. Shane ended the session because it got too long during active architectural changes. Priority one should be **testing what you've built** (restore workflow) before continuing architectural changes. Untested implementations during transitions can cascade into bigger problems. Test the restore overwrite checking end-to-end immediately, then continue Jinja2 conversion systematically.