# Container Service Domain Placement Analysis

## Current Status After Dead Code Removal

✅ **Completed:**
- Removed entire `BinaryCheckerService` class (dead code - 113 lines)
- Removed kopia/borg binary support (unused backup tools)
- Removed dead binary checking methods from `ContainerService`
- Reduced `services/binaries.py` from 353 to 212 lines (40% reduction)
- Tested and verified: application builds and backup functionality works correctly

## Remaining Container Service Analysis

### **What's Left in services/binaries.py:**

1. **`ContainerCommandBuilder` class** - Core container command construction
2. **`ContainerService` class** - Simple facade that wraps ContainerCommandBuilder
3. **`MountStrategy` enum** - Mount strategies for different operations

### **Current Usage Pattern:**
- **Only user:** `dests/services/restic.py` (line 907)
- **Only method used:** `build_backup_container_command()`
- **Purpose:** Builds Docker/Podman commands for restic backup operations

### **Domain Placement Question:**

The remaining `ContainerService` is used exclusively by the **destinations domain** (restic service) for building backup container commands. 

**Options:**
1. **Move to destinations domain** (`dests/services/container.py`) - since it's only used there
2. **Keep in shared services/** - since it's execution infrastructure  
3. **Move to origins domain** - your original suggestion (but evidence shows it's not SSH-specific)

### **Analysis:**

- **ContainerService builds execution commands** for any context (not SSH-specific)
- **Used by destinations** for backup operations  
- **Not used by origins** for SSH host management
- **Container execution is infrastructure** that could theoretically be used by multiple domains

### **Recommendation:**
Move to destinations domain (`dests/services/container.py`) since:
1. It's only used by destinations domain currently  
2. It's specifically for restic backup container execution
3. Following "move services to their users" principle
4. Can always be moved back to shared if other domains need it later

## Next Steps:
1. Decide on domain placement
2. Move ContainerService to chosen location
3. Update import in `dests/services/restic.py`
4. Test and commit the migration

## Files Involved:
- **Current:** `services/binaries.py` (212 lines)
- **User:** `dests/services/restic.py` (imports ContainerService on line 891)
- **Target:** TBD based on domain decision