# Schema-Driven Validation Migration Plan

## Overview
Complete the migration from hardcoded validation logic to schema-driven validation across all components. This ensures consistency, maintainability, and adherence to the architectural principle that schemas define all field requirements.

## Current State Analysis
- **✅ COMPLETED**: ResticValidator.validate_restic_destination() password check (models/validation.py:430-435)
- **✅ COMPLETED**: Complete schema definition for restic (models/backup.py)
- **✅ COMPLETED**: Form parser hardcoded password check (models/forms.py)
- **❌ REMAINING**: 2 additional hardcoded validation areas identified

## Migration Strategy
**Atomic approach**: One issue at a time, test after each change, maintain identical operation during transition.

---

## Issue #3: Handler Validation Hardcoded Check  
**File**: `handlers/forms.py` (exact line TBD)
**Current Code**:
```python
if not password:
    return self.template_service.render_validation_status('restic', {
        'valid': False, 'error': 'Repository password is required'
    })
```

**Problem**: Handler bypasses schema validation
**Schema Source**: Same as #2

**Migration Plan**:
1. Identify exact location in handlers/forms.py
2. Replace with call to schema-driven validation service  
3. Test HTMX validation endpoint behavior
4. Verify validation status UI updates correctly

**Risk**: MEDIUM - HTMX endpoint, requires UI testing

---

## Issue #4: Repository Service Hardcoded Checks
**File**: `models/backup.py` (8 instances)
**Current Code**:
```python
if not repo_uri or not password:
    return {'valid': False, 'error': 'Repository URI and password are required'}
```

**Problem**: Business logic layer duplicates schema validation
**Schema Source**: Multiple schema types (DESTINATION_TYPE_SCHEMAS, RESTIC_REPOSITORY_TYPE_SCHEMAS)

**Migration Plan**:
1. Identify all 8 instances in ResticRepositoryService methods
2. Replace with calls to validation service
3. Consolidate error handling patterns
4. Test repository operations (init, access, snapshots, etc.)
5. Verify error propagation to UI remains functional

**Risk**: HIGH - Core repository operations, requires comprehensive testing

---

## Issue #5: Validation Service Architecture Gap
**File**: `models/validation.py` - Special case handling
**Current Code**:
```python
if dest_type == 'restic':
    restic_result = self.restic_validator.validate_restic_destination(job_config)
else:
    # Schema-driven destination validation  
```

**Problem**: Creates dual validation paths instead of unified schema-driven approach
**Schema Source**: All destination types should use same validation pattern

**Migration Plan**:
1. Remove special case for restic in _validate_dest_config()
2. Ensure restic schema has all necessary field definitions
3. Test that restic jobs validate same as other destination types
4. Verify no regression in validation error messages

**Risk**: MEDIUM - Core validation logic, affects all restic operations

---

## Testing Protocol

### Per-Issue Testing
1. **Unit Tests**: Create standalone tests for each changed validation method
2. **Integration Tests**: Test via UI form submission and HTMX validation
3. **Regression Tests**: Verify existing jobs continue to work
4. **Error Message Tests**: Ensure user-friendly error messages preserved

### Validation Test Matrix
| Scenario | Expected Behavior | Test Method |
|----------|------------------|-------------|
| Missing password | Schema-driven error message | Form submission |
| Invalid repo type | Schema-driven error message | HTMX validation |
| Missing URI | Schema-driven error message | Repository init |
| Valid config | Successful validation | End-to-end job creation |

### Rollback Strategy
- Each change isolated in own commit
- `.bak` files for critical validation methods
- Immediate rollback on any regression
- Test on existing jobs before declaring success

---

## Success Criteria
1. **Zero hardcoded field requirements** - All validation uses schema lookups
2. **Identical user experience** - Error messages and UI behavior unchanged  
3. **Unified validation paths** - All destination types use same validation logic
4. **Schema-driven extensibility** - New field requirements only need schema updates
5. **Test coverage** - All validation paths have unit test coverage

---

## Implementation Order
1. **Issue #3** (handlers/forms.py) - UI validation, observable results  
2. **Issue #5** (validation.py) - Architecture fix, remove special case handling
3. **Issue #4** (backup.py services) - Highest risk, most comprehensive testing needed

Each issue will be implemented as a separate atomic commit with full testing before proceeding to the next.