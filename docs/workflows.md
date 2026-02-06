# Development Workflows

## Local Development

### Setup

```bash
# Clone and setup
git clone https://github.com/zebbern/icron.git
cd icron

# Install dependencies
pip install -e .

# Configure
cp config.example.json ~/.icron/config.json
# Edit config.json with your API key
```

### Running

```bash
# Start gateway
python -m icron.gateway.app

# Or with environment variable
ANTHROPIC_API_KEY=sk-... python -m icron.gateway.app
```

### Testing Changes

```bash
# Run tests
pytest

# Run specific test
pytest tests/test_tools.py -v

# With coverage
pytest --cov=icron
```

## Adding a New Tool

1. **Create tool file** in appropriate `tools/` subdirectory:
   ```python
   # icron/tools/mytool/tool.py
   class MyTool:
       name = "my_tool"
       description = "What it does"
       parameters = {...}
       
       def execute(self, params):
           return "result"
   ```

2. **Register tool** in tool registry (or use auto-discovery)

3. **Add tests** in `tests/tools/test_mytool.py`

4. **Document** in README tools table

## Adding a New LLM Provider

1. **Create provider** in `icron/llm/`:
   ```python
   # icron/llm/newprovider.py
   class NewProvider:
       def complete(self, messages, tools):
           # Call API, return response
           pass
   ```

2. **Update config schema** to accept new provider

3. **Wire up** in gateway/loop

4. **Document** setup requirements

## Debugging

### Enable verbose logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect session history

Check `~/.icron/workspace/sessions/` for JSON history files.

### Test tool independently

```python
from icron.tools.file.read import ReadFileTool
tool = ReadFileTool(workspace="/path/to/workspace")
result = tool.execute({"path": "test.txt"})
print(result)
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Create git tag
5. Push to GitHub

## Git Workflow

- `main` branch is stable
- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- Commit messages: imperative mood ("Add tool" not "Added tool")
