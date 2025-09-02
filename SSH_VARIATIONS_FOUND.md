# SSH Command Implementation Variations Found

## Critical Differences That Must Be Handled

### 1. **TIMEOUT VALUES**
- **services/execution.py**: `ConnectTimeout=10`
- **dests/schema.py**: `ConnectTimeout=3` (quick check)
- **All others**: `ConnectTimeout=10`

### 2. **AUTHENTICATION MODES**
- **Password auth** (services/execution.py:562): 
  - Uses `sshpass -p password`
  - **NO BatchMode** (password interactive)
  - **NO -i key**
- **Key auth**: Uses `-i /config/local/secrets/.ssh/id_highball` + `BatchMode=yes`

### 3. **MISSING KEY SPECIFICATION**
- **jobs/services/restore.py:335**: 
  - **CRITICAL BUG**: No `-i` key specified!
  - Only has BatchMode, ConnectTimeout, StrictHostKeyChecking, UserKnownHostsFile
  - This will try to use default SSH keys instead of Highball key

### 4. **PORT HANDLING**
- **dests/services/rsync.py:393**: Has conditional port handling
  ```python
  if port and port != '22':
      cmd.extend(['-p', port])
  ```
- **Others**: No port handling visible

### 5. **COMMAND TYPES**
- **SSH**: For remote command execution
- **SCP**: For file copying (services/execution.py:660,677)
  - Note: SCP uses `-P` (capital P) for port, not `-p`

### 6. **TEMPLATE SUBSTITUTION**
- **dests/schema.py:246**: Uses template variables `{sftp_username}@{sftp_hostname}`
- **Others**: Direct variable interpolation

## Specific Locations

### services/execution.py (MULTIPLE PATTERNS)
1. **Password SSH** (line 562): `sshpass + ssh` (no BatchMode, no key)
2. **Key SSH** (line 572): `ssh -i + BatchMode`  
3. **SCP private key** (line 660): `scp -i`
4. **SCP public key** (line 677): `scp -i`

### dests/services/rsync.py (2 INSTANCES)
1. **test_destination()** (line 263): Standard key SSH
2. **validate_rsync_destination()** (line 384): Key SSH + **port handling**

### jobs/services/restore.py (1 INSTANCE)
1. **Path validation** (line 335): **MISSING -i KEY** - uses default SSH keys!

### dests/schema.py (1 INSTANCE)  
1. **SFTP quick check** (line 246): Short timeout + template variables

### services/binaries.py (1 INSTANCE)
1. **Container SSH wrapping** (line 76): Basic key SSH (our current implementation)

## CRITICAL ISSUES TO FIX

1. **jobs/services/restore.py is broken** - no SSH key specified
2. **Inconsistent timeouts** - need configurable timeout
3. **Missing port support** in most implementations  
4. **Password vs key auth** - need both modes
5. **SCP vs SSH** - different port flag (`-P` vs `-p`)

## Factory Requirements

The SSHCommandFactory must support:
- ✅ Configurable timeout (default 10, allow 3 for quick checks)
- ✅ Password auth mode (sshpass + no BatchMode)  
- ✅ Key auth mode (default)
- ❌ **Port handling** (missing from current factory)
- ❌ **SCP support** (missing from current factory) 
- ❌ **Configurable key path** (currently hardcoded)
- ❌ **Template substitution support** (for schema definitions)