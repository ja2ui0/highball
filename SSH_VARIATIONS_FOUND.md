# SSH Command Implementation Variations Found

## Remaining Inconsistencies to Address Before Factory Replacement

### 1. **AUTHENTICATION MODES**
- **Password auth** (services/execution.py:562): 
  - Uses `sshpass -p password`
  - **NO BatchMode** (password interactive)
  - **NO -i key**
- **Key auth**: Uses `-i /config/local/secrets/.ssh/id_highball` + `BatchMode=yes`

### 2. **PORT HANDLING**
- **dests/services/rsync.py:393**: Has conditional port handling
  ```python
  if port and port != '22':
      cmd.extend(['-p', port])
  ```
- **Others**: No port handling visible

### 3. **TEMPLATE SUBSTITUTION**
- **dests/schema.py:246**: Uses template variables `{sftp_username}@{sftp_hostname}`
- **Others**: Direct variable interpolation

## Remaining Locations to Replace

### services/execution.py (1 PATTERN REMAINING)
1. **Password SSH** (line 562): `sshpass + ssh` (no BatchMode, no key)

### dests/services/rsync.py (2 INSTANCES)
1. **test_destination()** (line 263): Standard key SSH
2. **validate_rsync_destination()** (line 384): Key SSH + **port handling**

### jobs/services/restore.py (1 INSTANCE)
1. **Path validation** (line 335): Standard key SSH

### dests/schema.py (1 INSTANCE)  
1. **SFTP quick check** (line 246): Template variables

## Factory Requirements Still Needed

The SSHCommandFactory must support:
- ❌ **Port handling** (missing from current factory)
- ❌ **Template substitution support** (for schema definitions)