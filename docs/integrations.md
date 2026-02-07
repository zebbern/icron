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

## Web Tools

### web_search

Search the web using Brave Search API:

```python
# Agent uses this tool automatically when searching
web_search(query="python async tutorial", count=5)
```

Requires `BRAVE_SEARCH_API_KEY` or config setting `tools.web.search.apiKey`.

### web_fetch

Fetch URL and extract readable content:

```python
# Automatically extracts main content, converts HTML to markdown
web_fetch(url="https://example.com", extractMode="markdown")
```

Parameters:
- `url` - URL to fetch
- `extractMode` - "markdown" (default) or "text"
- `maxChars` - Maximum characters to return

## Screenshot Tool

Capture screenshots of web pages using Playwright's headless Chromium browser.

### Tool: `screenshot`

**Description:** Capture a screenshot of a web page. Returns the file path for attachment. Supports full-page screenshots and custom viewport dimensions.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | ✅ | - | URL of the web page to capture (must be http/https) |
| `full_page` | boolean | ❌ | `false` | Capture the full scrollable page |
| `width` | integer | ❌ | `1280` | Viewport width in pixels (320-3840) |
| `height` | integer | ❌ | `720` | Viewport height in pixels (240-2160) |

### Usage Examples

**Basic screenshot:**
```
"Take a screenshot of https://example.com"
```

**Full page capture:**
```
"Capture a full page screenshot of https://github.com"
```

**Custom dimensions:**
```
"Screenshot https://mobile-site.com with width 375 and height 812" (iPhone dimensions)
```

### Setup Requirements

```bash
pip install playwright
playwright install chromium
```

### Output

Screenshots are saved to `workspace/media/screenshots/` with auto-generated filenames:
- Format: `screenshot_{timestamp}_{url_hash}.png`
- Example: `screenshot_20260206_143022_a1b2c3d4.png`

The tool returns the relative path for easy attachment in chat responses.

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
