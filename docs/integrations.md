# Integrations Guide

## LLM Providers

### Anthropic Claude (Default)

```json
{
  "model": "@anthropic/claude-sonnet-4-20250514",
  "api_key": "sk-ant-..."
}
```

Environment: `ANTHROPIC_API_KEY`

Supports: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku

### OpenAI

```json
{
  "model": "@openai/gpt-4o",
  "api_key": "sk-..."
}
```

Environment: `OPENAI_API_KEY`

Supports: GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo

### vLLM (Self-hosted)

For running open models locally:

```json
{
  "model": "@vllm/mistral-7b",
  "base_url": "http://localhost:8000/v1"
}
```

Setup:
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.2
```

### Ollama

```json
{
  "model": "@ollama/llama3",
  "base_url": "http://localhost:11434"
}
```

Setup:
```bash
ollama pull llama3
ollama serve
```

## MCP Servers

Icron can connect to MCP (Model Context Protocol) servers to extend capabilities.

### Configuration

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    }
  ]
}
```

### Available MCP Servers

- **filesystem** - Enhanced file operations
- **github** - GitHub API integration
- **postgres** - Database queries
- **brave-search** - Web search

See [MCP Server Registry](https://github.com/modelcontextprotocol/servers) for more.

## Web Fetching

### Built-in httpx

Simple HTTP fetching for static content:

```python
# Automatic for most URLs
fetch_url("https://example.com")
```

### Playwright (Dynamic Sites)

For JavaScript-rendered pages:

```python
# Enabled via MCP or built-in
fetch_url("https://spa-site.com", use_playwright=True)
```

Setup:
```bash
playwright install chromium
```

## External Services

### Memory & Reminders

Built-in JSON file storage at `~/.icron/workspace/`:
- `memory/` - Persistent key-value store
- `reminders/` - Scheduled notifications

No external database required.

### Future Integrations (Roadmap)

- Email (IMAP/SMTP)
- Calendar (Google Calendar, Outlook)
- Task managers (Todoist, Linear)
- Messaging (Slack, Discord)
