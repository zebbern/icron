# Code Conventions

## Python Style

- **Version**: Python 3.10+
- **Style**: PEP 8 with 100-char line limit
- **Types**: Use type hints for all public functions
- **Docstrings**: Google style for public APIs

```python
def function_name(param: str, optional: int = 10) -> dict:
    """Short description.
    
    Args:
        param: Description of param
        optional: Description with default
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param is invalid
    """
```

## File Organization

- One class per file when class is substantial
- Related utilities can share a file
- `__init__.py` should export public API only

## Naming

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `session_manager.py` |
| Classes | PascalCase | `SessionManager` |
| Functions | snake_case | `get_history()` |
| Constants | UPPER_SNAKE | `MAX_ITERATIONS` |
| Private | `_prefix` | `_internal_method()` |

## Tool Implementation

Tools must:
1. Inherit from base tool class (or follow protocol)
2. Define `name`, `description`, `parameters` schema
3. Implement `execute(params) -> result`
4. Handle errors gracefully with clear messages
5. Respect workspace restrictions when applicable

```python
class MyTool:
    name = "my_tool"
    description = "What this tool does"
    parameters = {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "..."}
        },
        "required": ["param"]
    }
    
    def execute(self, params: dict) -> str:
        # Implementation
        return result
```

## Configuration

- All config in `~/.icron/config.json`
- Use Pydantic models in `config/schema.py`
- Environment variables for secrets:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `ICRON_WORKSPACE`

## Error Handling

- Raise specific exceptions, not generic `Exception`
- Log errors with context
- Return user-friendly messages from tools
- Never expose stack traces to LLM responses

## Testing

- Tests in `tests/` mirroring source structure
- Use pytest
- Mock external services (LLM, network)
- Test both success and error paths
