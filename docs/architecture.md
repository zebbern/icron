# Architecture

## Overview

Icron is a Python-based AI agent framework with a modular architecture designed for extensibility and self-improvement.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Gateway (Flask)                     │
│                    localhost:3883                           │
├─────────────────────────────────────────────────────────────┤
│  /         - Basic settings UI                               │
│  /app      - Full Svelte UI                                  │
│  /exec     - Agent execution endpoint (POST)                 │
│  /session  - Session management                              │
│  /memory   - Memory API                                      │
│  /reminders- Reminder API                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Command Handler (commands.py)               │
├─────────────────────────────────────────────────────────────┤
│  • Handles slash commands (/help, /sessions, /skills, etc.) │
│  • Manages message templates                                 │
│  • Routes delegated commands to agent                        │
│  • Provides instant responses for session management         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (loop.py)                      │
├─────────────────────────────────────────────────────────────┤
│  • Manages conversation flow                                 │
│  • Processes tool calls                                      │
│  • Handles context window management                         │
│  • Coordinates with session manager                          │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Tool Registry  │  │ Session Manager │  │  LLM Provider   │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ • File tools    │  │ • History       │  │ • Anthropic     │
│ • Shell tools   │  │ • Token mgmt    │  │ • OpenAI        │
│ • Memory tools  │  │ • Persistence   │  │ • vLLM          │
│ • Web tools     │  │                 │  │ • Ollama        │
│ • Spawn tools   │  │                 │  │ • Gemini        │
│ • Screenshot    │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Skills Loader (skills.py)                  │
├─────────────────────────────────────────────────────────────┤
│  • Loads skill definitions from SKILL.md files               │
│  • Provides builtin skills (weather, github, summarize)      │
│  • Supports workspace-level custom skills                    │
│  • Validates skill requirements/dependencies                 │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
icron/
├── agent/           # Core agent loop and orchestration
│   ├── loop.py      # Main agent processing loop
│   ├── commands.py  # Slash command handler & templates
│   ├── context.py   # System prompt builder
│   ├── memory.py    # Persistent memory
│   ├── skills.py    # Skills loader
│   ├── subagent.py  # Background task execution
│   └── tools/       # Built-in tools
├── bus/             # Message routing
│   ├── events.py    # Event definitions
│   └── queue.py     # Message queue
├── channels/        # Chat channel integrations
│   ├── discord.py   # Discord bot
│   ├── telegram.py  # Telegram bot
│   ├── whatsapp.py  # WhatsApp bridge
│   └── manager.py   # Channel coordinator
├── cli/             # CLI commands
│   └── commands.py  # setup, validate, agent, gateway, etc.
├── config/          # Configuration management
│   ├── loader.py    # Config file loading
│   └── schema.py    # Pydantic models for config
├── cron/            # Scheduled task execution
│   ├── service.py   # Cron service
│   └── types.py     # Job definitions
├── heartbeat/       # Proactive task checking
│   └── service.py   # Heartbeat service
├── mcp/             # MCP server integration
│   ├── client.py    # MCP client
│   └── tool_adapter.py # Tool wrapper
├── providers/       # LLM provider integrations
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   └── factory.py   # Provider factory
├── session/         # Session and history management
│   └── manager.py   # Conversation history, token trimming
├── skills/          # Built-in skills
│   ├── weather/     # Weather lookups
│   ├── github/      # GitHub operations
│   ├── summarize/   # Content summarization
│   └── tmux/        # Tmux session control
└── utils/           # Shared utilities
    ├── tokens.py    # Token counting
    └── helpers.py   # Path validation, utilities
```

## Memory System

Icron features an OpenClaw-style semantic memory system for persistent, searchable knowledge storage.

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory System                             │
├─────────────────────────────────────────────────────────────┤
│  MemoryStore (store.py)                                      │
│  • MEMORY.md - Curated long-term memory (never auto-trimmed)│
│  • Daily logs (memory/YYYY-MM-DD.md) - Append-only notes    │
│  • Markdown format for human readability                     │
├─────────────────────────────────────────────────────────────┤
│  VectorIndex (index.py)                                      │
│  • sqlite-vec for vector storage (fallback: Python cosine)  │
│  • Hybrid search: BM25 keyword + vector similarity          │
│  • Automatic chunking and indexing                          │
├─────────────────────────────────────────────────────────────┤
│  EmbeddingProviders (embeddings.py)                          │
│  • Auto-detect: OpenAI → Gemini → Ollama → Local            │
│  • Configurable embedding model                              │
│  • Graceful fallback chain                                   │
└─────────────────────────────────────────────────────────────┘
```

### Memory Architecture

- **Permanent Storage**: Unlike conversation history, memories are never auto-summarized or trimmed
- **Hybrid Search**: Combines BM25 keyword matching with vector similarity for accurate retrieval
- **Provider Flexibility**: Auto-detects available embedding provider from configured LLM providers
- **Human-Readable**: All memories stored as Markdown files for easy inspection and editing

## Data Flow

1. **Request** → Gateway receives user message
2. **Session** → Load/create session with history
3. **Context** → Build messages with token budget
4. **LLM** → Send to configured provider
5. **Tools** → Execute any tool calls
6. **Response** → Return assistant reply
7. **Persist** → Save session history

## Key Design Decisions

See [decisions.md](decisions.md) for rationale behind architectural choices.
