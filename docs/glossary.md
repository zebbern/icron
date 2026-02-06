# Glossary

## Core Concepts

### Agent
An AI system that can take actions via tools. Icron implements an agent loop that processes user messages, calls LLMs, executes tools, and returns responses.

### Agent Loop
The central execution cycle in `icron/agent/loop.py`. Receives messages → calls LLM → processes tool calls → returns response.

### Context Window
The maximum number of tokens an LLM can process in a single request. Icron manages this via token-based history trimming.

### Gateway
The Flask web server (`icron/gateway/app.py`) that exposes HTTP endpoints for interacting with the agent.

### Session
A conversation thread with history. Sessions are persisted to `~/.icron/workspace/sessions/`.

### Subagent
A background agent instance spawned via SpawnTool to handle long-running tasks without blocking the main conversation.

### Tool
A discrete capability the agent can invoke. Examples: read_file, run_shell, store_memory. Tools are discovered and exposed to the LLM.

### Workspace
The configured directory (`workspace` in config) where the agent operates. File tools can be restricted to this directory for security.

## Configuration Terms

### ExecToolConfig
Configuration passed when executing the agent: model, API key, workspace path, max tokens, etc.

### MCP Server
An external process providing additional tools via the Model Context Protocol. Icron can connect to MCP servers for extended capabilities.

### Provider
The LLM service backend: Anthropic, OpenAI, vLLM, or Ollama.

## Tool Categories

### File Tools
- `read_file` - Read file contents
- `write_file` - Create/overwrite files
- `edit_file` - Modify existing files
- `list_directory` - List folder contents
- `file_search` - Find files by glob pattern

### Memory Tools
- `store_memory` - Save key-value data
- `recall_memory` - Retrieve stored data
- `clear_memory` - Delete memory entries

### Reminder Tools
- `set_reminder` - Schedule future notification
- `list_reminders` - View pending reminders
- `cancel_reminder` - Remove a reminder

### Shell Tools
- `run_shell` - Execute terminal commands (bash/PowerShell)

### Web Tools
- `fetch_url` - Retrieve web page content
- Uses httpx for static content, Playwright for dynamic

### Spawn Tools
- `spawn_task` - Delegate work to background subagent

## Technical Terms

### Token
The unit of text processing for LLMs. Roughly ~4 characters per token. Used for billing and context limits.

### Token Budget
The maximum tokens allocated for conversation history. Older messages are trimmed when history exceeds budget.

### Path Traversal
A security attack using `../` to access files outside the workspace. Icron validates and blocks these attempts.
