# Development Workflows

## Local Development

### Setup

**Option 1: Guided Setup (Recommended)**

```bash
# Clone and install
git clone https://github.com/zebbern/icron.git
cd icron
pip install -e .

# Run guided setup wizard
icron setup
```

The setup wizard will:
- Create config directory
- Prompt for API keys
- Configure default model
- Set up channels (optional)
- Validate configuration

**Option 2: Manual Setup**

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

### Validate Configuration

```bash
# Check config for errors
icron validate
```

This validates:

- JSON syntax
- Required fields
- API key formats
- Channel configurations
- Provider connections (optional)

### Running

```bash
# Start gateway
icron gateway

# Or with environment variable
ANTHROPIC_API_KEY=sk-... icron gateway
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

## Using Slash Commands

Slash commands provide quick access to common operations without LLM processing.

### Session Management

```bash
/sessions              # List all sessions
/session clear         # Clear current session
/session new           # Start fresh session
/session rename MyChat # Rename session
```

### Quick Actions

```bash
/remind 30m Take a break       # Set reminder
/search python async tutorial  # Web search
/weather London                # Get weather
/skills                        # List skills
/skills run weather            # Run a skill
```

### Templates

Templates provide structured workflows for common tasks:

```bash
/templates                     # List all templates
/template morning              # Morning briefing
/template research AI trends   # Research a topic
/template recap                # Summarize conversation
/template daily                # Daily summary
```

### Help

```bash
/help                  # Show all commands
/help sessions         # Session management help
/help skills           # Skills system help
/help weather          # Weather command help
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
