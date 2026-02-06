# icron

A lightweight personal AI assistant framework with multi-channel support.

## Architecture

```
User -> Channel -> MessageBus -> AgentLoop -> LLM Provider
                        |              |
                        v              v
                   SessionStore    ToolRegistry (18 tools + MCP)
```

**Channels**: Discord, Telegram, WhatsApp, Slack, Feishu  
**Providers**: Anthropic, OpenAI, OpenRouter, Together, Groq, Gemini, Zhipu, vLLM  
**Config**: `~/.icron/config.json`

## Key Directories

```
icron/
├── agent/          # Core agent loop, tools, context
├── channels/       # Discord, Telegram, WhatsApp, Slack, Feishu
├── bus/            # Async message bus
├── config/         # Pydantic config schema
├── cron/           # Scheduled jobs service
├── mcp/            # Model Context Protocol client
├── session/        # JSONL conversation storage
├── cli/            # Typer CLI commands
ui/                 # Svelte web settings UI
bridge/             # Node.js WhatsApp bridge
```

## Built-in Tools

| Category | Tools |
|----------|-------|
| Files | `read_file`, `write_file`, `edit_file`, `list_dir`, `rename_file`, `move_file`, `copy_file`, `create_dir` |
| Search | `glob`, `grep` |
| Web | `web_search` (Brave), `web_fetch` |
| Shell | `exec` |
| Memory | `remember`, `recall`, `note_today` |
| Scheduling | `set_reminder`, `list_reminders`, `cancel_reminder`, `cron` |
| Communication | `message`, `spawn` |

## Commands

```bash
icron onboard            # Initialize config + workspace
icron gateway            # Start full server (web UI at :3883)
icron agent -m "..."     # Direct chat + REPL mode
icron cron list          # Manage scheduled jobs
icron status             # Show configuration
```

## Code Patterns

### Tool Implementation

```python
class MyTool(Tool):
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {...}}

    async def execute(self, **kwargs: Any) -> str:
        try:
            return "result"
        except Exception as e:
            return f"Error: {e}"  # Return errors, don't raise
```

### Async-First

```python
async def process_message(self, message: Message) -> AsyncIterator[str]:
    async for chunk in self.llm.stream(messages):
        yield chunk
```

## Conventions

- **Type hints**: Use `X | None` not `Optional[X]`
- **Line length**: 100 chars max
- **File I/O**: Always use `encoding="utf-8"`
- **Logging**: Use loguru, no emojis in debug
- **Error handling**: Tools return error strings, don't raise exceptions
- **Imports**: Absolute imports from `icron.`

## Verification

```bash
pytest && ruff check icron/ && ruff format --check icron/
```
