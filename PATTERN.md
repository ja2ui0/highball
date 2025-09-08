# Layering Fix Pattern

## Context
The `.refactor/refactor.sh --claude-one` script identifies web-stack imports in domain services that violate layering rules.

## Problem Pattern
Services containing `from fastapi.responses import JSONResponse` and returning `JSONResponse` objects mix web concerns with business logic.

## Solution Pattern

### 1. Fix the Service Method
- Remove `from fastapi.responses import JSONResponse` import
- Add `@handle_service_errors("Operation name")` decorator
- Return plain data structures (dicts with success/error keys)
- Fix any broken method calls (e.g. `analyze_content` -> `analyze_repository_content`)
- Ensure service class has all required dependencies in constructor

### 2. Create Handler Method
- Add method to appropriate domain `handlers/pages.py`
- Use `@handle_page_errors("Operation name")` decorator  
- Import domain service: `from domain.services.module import service_name`
- Call service method and wrap result: `return JSONResponse(content=result)`

### 3. Update App Routing
- Change app.py route from calling service directly to calling handler
- Pattern: `return domain_handler.method_name(params)` instead of `return services.api.method_name(params)`

### 4. Export Service Instance
- Add service export at bottom of service file with required config
- Pattern: `service_name = ServiceClass(required_config)`

## Example
```python
# Service (domain/services/module.py)
@handle_service_errors("Get info")
def get_info(self, param):
    # business logic
    return {'success': True, 'data': result}

# Handler (domain/handlers/pages.py) 
@handle_page_errors("Get info")
def get_info(self, param):
    from domain.services.module import service_instance
    result = service_instance.get_info(param)
    return JSONResponse(content=result)

# App routing (app.py)
return domain_handler.get_info(param)
```

## Remaining Work
- 4 more methods in `dests/services/restic.py` need same fix
- Run `.refactor/refactor.sh --claude-one` to find remaining violations