# Architecture

## Overview

Icron is a Python-based AI agent framework with a modular architecture designed for extensibility and self-improvement.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Gateway (Flask)                     │
│                    localhost:18790                           │
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
│ • Spawn tools   │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Directory Structure

```
icron/
├── agent/           # Core agent loop and orchestration
│   ├── loop.py      # Main agent processing loop
│   └── subagent.py  # Background task execution
├── config/          # Configuration management
│   └── schema.py    # Pydantic models for config
├── gateway/         # Web server and API
│   └── app.py       # Flask application
├── llm/             # LLM provider integrations
│   ├── anthropic.py # Claude integration
│   ├── openai.py    # OpenAI/vLLM integration
│   └── ollama.py    # Ollama integration
├── session/         # Session and history management
│   └── manager.py   # Conversation history, token trimming
├── tools/           # Tool implementations
│   ├── file/        # File operations (read, write, edit)
│   ├── memory/      # Persistent memory tools
│   ├── reminder/    # Scheduled reminders
│   ├── shell/       # Shell command execution
│   ├── spawn/       # Background task delegation
│   └── web/         # Web fetching (httpx + Playwright)
└── utils/           # Shared utilities
    ├── tokens.py    # Token counting
    └── security.py  # Path validation
```

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
