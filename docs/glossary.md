# Glossary

## Core Concepts

### Agent
An AI system that can take actions via tools. Icron implements an agent loop that processes user messages, calls LLMs, executes tools, and returns responses.

### Agent Loop
The central execution cycle in `icron/agent/loop.py`. Receives messages → calls LLM → processes tool calls → returns response.

### Context Window
The maximum number of tokens an LLM can process in a single request. Icron manages this via token-based history trimming.

### Gateway
The HTTP server (implemented in `icron/cli/commands.py`) that exposes endpoints for interacting with the agent and serves the web UI.

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

## Slash Commands & Templates

### Slash Command

A command prefixed with `/` that is processed directly by icron without going through the LLM. Provides instant responses for session management, help, and quick actions.

### CommandHandler

The component (`icron/agent/commands.py`) that processes slash commands. Routes commands to appropriate handlers and delegates some (like `/search`, `/remind`) to the agent.

### Template

A pre-defined workflow with instructions for the agent. Templates provide structured prompts for common tasks like morning briefings, research, or conversation recaps. Triggered via `/template [name]`.

### Skill

A reusable capability module defined in a `SKILL.md` file. Skills teach the agent how to perform specific tasks (weather lookups, GitHub operations, summarization). Loaded dynamically and can be workspace-specific or built-in.

### SkillsLoader

The component (`icron/agent/skills.py`) that discovers and loads skills from both the workspace and built-in directories.

## Tool Categories

### File Tools

- `read_file` - Read file contents
- `write_file` - Create/overwrite files
- `edit_file` - Modify existing files
- `list_dir` - List folder contents
- `glob` - Find files by pattern
- `grep` - Search file contents

### Memory Tools

- `memory_write` - Save/update memory entries
- `memory_search` - Search stored memories semantically
- `memory_list` - List all memory files
- `memory_get` - Read specific memory file

### Reminder Tools

- `set_reminder` - Schedule future notification
- `list_reminders` - View pending reminders
- `cancel_reminder` - Remove a reminder by ID

### Shell Tools

- `exec` - Execute terminal commands (bash/PowerShell)

### Web Tools

- `web_search` - Search the web via Brave API
- `web_fetch` - Retrieve web page content
- Uses httpx for static content, Playwright for dynamic

### Screenshot Tool

- `screenshot` - Capture web page screenshots using Playwright

### Spawn Tools

- `spawn` - Delegate work to background subagent

### Message Tool

- `message` - Send messages to user, supports media attachments

## Technical Terms

### Token

The unit of text processing for LLMs. Roughly ~4 characters per token. Used for billing and context limits.

### Token Budget

The maximum tokens allocated for conversation history. Older messages are trimmed when history exceeds budget.

### Path Traversal

A security attack using `../` to access files outside the workspace. Icron validates and blocks these attempts.

### Setup Wizard

Interactive CLI command (`icron setup`) that guides users through configuration. Prompts for API provider, key, and model selection with connection testing.

### Validate Command

CLI command (`icron validate`) that checks configuration for errors, validates JSON syntax, schema compliance, API key formats, and optionally tests API connections.
