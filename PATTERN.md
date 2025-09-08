# FastAPI Layering Violation Fix Pattern

## Detection
Use `.refactor/refactor.sh --claude-one` to identify web-stack imports in domain services (*/services).

## Core Problem
Services containing `from fastapi.responses import JSONResponse` mix web concerns with business logic.

## Fix Pattern (Always Apply All Steps)

### 1. Fix Service Method
- Remove `from fastapi.responses import JSONResponse` import  
- Add `@handle_service_errors("Operation name")` decorator
- Return plain data structures instead of `JSONResponse(content=result)`
- Fix any broken method calls revealed by the change

### 2. Update Handler Method
- If handler exists: Wrap service result with `return JSONResponse(content=result)`
- If no handler exists: Create handler method in appropriate `domain/handlers/pages.py`
- Use `@handle_page_errors("Operation name")` decorator

### 3. Update App Routing (if needed)
- Change app.py route from `services.method()` to `domain_handler.method()`

### 4. Test End-to-End
- Rebuild with `./rr` then test with `curl`
- Verify proper error handling (missing params, invalid data)
- Don't commit until endpoint works correctly

## Service Import Anti-Patterns

**❌ NEVER do this (circular dependency):**
```python
from app import services  # Creates circular imports
```

**❌ NEVER do this (broken import):**
```python  
from admin.services.init import services  # services not exported
```

**✅ ALWAYS do this (direct domain import):**
```python
from domain.services.module import service_instance
# or create instance: service = ServiceClass(config)
```

## Common Issues & Fixes

**Static Method Call Error:**
```python
# ❌ Wrong: Creating instance of class with static methods
parser = DestinationParser()
result = parser.parse_restic_destination(data)

# ✅ Correct: Call static method directly  
result = DestinationParser.parse_restic_destination(data)
```

**Method Not Found Error:**
- Search for correct method name: `grep -rn "method_name" /path/to/services/`
- Check method exists in correct service class
- Example: `backup_service.initialize_repository()` → `ResticRepositoryService().initialize_repository()`

**Form Data Structure:**
- Keep resilient array structure in handlers (works with `safe_get_value()`)
- Don't change form parsing to "fix" validation errors
- Arrays are more resilient for future extensibility

## Testing Pattern
```bash
./rr                    # Rebuild (wait for success)
curl -s "http://localhost:8087/endpoint"  # Test separately
```