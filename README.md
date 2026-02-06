<div align="center">
  <img src="nanobot_logo.png" alt="icron" width="500">
  <h1>icron the `lightweight` Personal AI Assistant</h1>
</div>

**icron** is a **lightweight** personal AI assistant designed for simplicity and extensibility.
Built with Python, it supports multiple chat channels (Discord, Telegram, WhatsApp) and can connect to any OpenAI-compatible LLM provider (Anthropic, OpenRouter, Together, Groq, vLLM). With a modular architecture and built-in tools for file operations, web search, shell execution, memory, and scheduling, icron is your personal assistant for research, coding, reminders, and more.

### Core Capabilities

| Category | Tools |
|----------|-------|
| **File Operations** | `read_file`, `write_file`, `edit_file`, `list_dir`, `rename_file`, `move_file`, `copy_file`, `create_dir` |
| **Code Search** | `glob` (find files), `grep` (search content) |
| **Shell Execution** | `exec` (run commands with safety controls) |
| **Web Access** | `web_search` (Brave API), `web_fetch` (extract content) |
| **Memory** | `memory_store`, `memory_search`, `memory_list`, `memory_delete` |
| **Scheduling** | `reminder_set`, `reminder_list`, `reminder_cancel` |
| **Slash Commands** | `/help`, `/sessions`, `/session`, `/remind`, `/search`, `/memory` |
| **Screenshots** | `screenshot` (capture web pages with Playwright) |
| **Subagents** | `spawn` (background task delegation) |
| **MCP** | Connect external MCP servers for unlimited extensibility |

## 📦 Install

**From source** (recommended for development)

```bash
git clone https://github.com/zebbern/icron.git
cd icron
pip install -e .
```

**From PyPI** (stable)

```bash
pip install icron
```

## 🚀 Quick Start

**1. Initialize** (choose one)

```bash
# Guided setup wizard (recommended for first-time users)
icron setup

# Or quick initialization
icron onboard
```

**2. Configure** (`~/.icron/config.json`)

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-20250514"
    }
  }
}
```

**3. Chat**

```bash
icron agent -m "What is 2+2?"
```

## Local Models (vLLM)

Run icron with your own local models using vLLM or any OpenAI-compatible server.

**1. Start your vLLM server**

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. Configure** (`~/.icron/config.json`)

```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

**3. Chat**

```bash
icron agent -m "Hello from my local LLM!"
```

> The `apiKey` can be any non-empty string for local servers.

## 💬 Chat Channels

Talk to icron through Telegram, WhatsApp, or Discord.

| Channel | Status | Setup |
|---------|--------|-------|
| **Discord** | ✅ Full support | Easy (bot token) |
| **Telegram** | ✅ Full support + voice | Easy (bot token) |
| **WhatsApp** | ✅ Basic support | Medium (QR scan) |

<details>
<summary><b>Discord Setup</b></summary>

**1. Create a Discord bot**

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application, go to **Bot**, copy the token
3. Enable **Message Content Intent**
4. Go to **OAuth2 → URL Generator**, select `bot` scope with permissions: Send Messages, Read Messages, Read Message History
5. Invite bot to your server

**2. Configure**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": [YOUR_USER_ID],
      "allowedChannels": []
    }
  }
}
```

**3. Run**

```bash
icron gateway
```

</details>

<details>
<summary><b>Telegram Setup</b></summary>

**1. Create a bot**
- Open Telegram, find `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

**2. Configure**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> Get your user ID from `@userinfobot` on Telegram.

**3. Run**

```bash
icron gateway
```

> **Voice transcription**: If you configure a Groq API key, voice messages will be automatically transcribed via Whisper.

</details>

<details>
<summary><b>WhatsApp Setup</b></summary>

Requires **Node.js ≥18**.

**1. Start the bridge**

```bash
icron channels login
# Scan QR with WhatsApp → Settings → Linked Devices
```

**2. Configure**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. Run** (two terminals)

```bash
# Terminal 1 - WhatsApp bridge
icron channels login

# Terminal 2 - Gateway
icron gateway
```

</details>

## 🌐 Web UI

The gateway provides a web interface for configuration.

```bash
icron gateway
# Open http://localhost:18790/app
```

**Quick Settings UI:**
- Model selection
- API keys (Together, OpenRouter, Brave Search)
- Channel toggles (Telegram, WhatsApp, Discord)
- Security settings (restrict tools to workspace)
- Context limits (max tokens for conversation history)

## 🧠 Memory & Persistence

icron has persistent memory that survives restarts:

```
# Store a fact
"Remember that my project deadline is January 31st"

# Recall later
"When is my project deadline?"

# List all memories
"What do you remember about me?"
```

Memory is stored in `~/.icron/workspace/memory/` as markdown files.

## ⏰ Reminders & Scheduling

**Set reminders naturally:**

```
"Remind me in 30 minutes to take a break"
"Remind me at 2pm to call John"
"Remind me tomorrow at 9am about the meeting"
```

**Or use slash commands for quick reminders:**

```
/remind 30m take a break
/remind 2h call john
```

**Cron jobs for recurring tasks:**

```bash
# Add a daily reminder
icron cron add --name "morning" --message "Good morning!" --cron "0 9 * * *"

# Add a one-time reminder
icron cron add --name "meeting" --message "Meeting starts!" --at "2025-01-31T15:00:00"

# List and manage jobs
icron cron list
icron cron remove <job_id>
```

## ⚡ Slash Commands

Quick commands that bypass the LLM for instant response:

| Command | Description |
|---------|-------------|
| `/help` | List all commands |
| `/help [topic]` | Detailed help (sessions, memory, reminders, search) |
| `/sessions` | List all sessions |
| `/session clear` | Clear current session |
| `/session new` | Start fresh session |
| `/session rename [name]` | Rename session |
| `/session switch [id]` | Switch sessions |
| `/remind [time] [message]` | Set quick reminder |
| `/search [query]` | Quick web search |
| `/memory` | Access memory |
| `/skills` | List available skills |
| `/skills run [name]` | Run a specific skill |
| `/weather [location]` | Get weather for a location |
| `/templates` | List available templates |
| `/template [name]` | Run a template by name |

## 🔧 MCP Server Support

icron can connect to external [MCP servers](https://modelcontextprotocol.io/) for extended functionality.

**Configure MCP servers:**

```json
{
  "tools": {
    "mcp": {
      "enabled": true,
      "servers": {
        "calculator": {
          "transport": "stdio",
          "command": "python",
          "args": ["/path/to/mcp_server.py"]
        }
      }
    }
  }
}
```

MCP servers appear as additional tools the agent can use.

## 🔒 Security

**Workspace restriction:**

```json
{
  "tools": {
    "exec": {
      "restrictToWorkspace": true
    }
  }
}
```

When enabled, file operations are limited to `~/.icron/workspace/`.

**Built-in safety:**
- Dangerous shell commands are blocked (rm -rf, format, dd, etc.)
- Command execution has configurable timeout (default 60s)
- Output is truncated to prevent context overflow

## ⚙️ Configuration Reference

Config file: `~/.icron/config.json`

| Section | Key | Description |
|---------|-----|-------------|
| `agents.defaults.model` | string | Default LLM model |
| `providers.openrouter.apiKey` | string | OpenRouter API key |
| `providers.anthropic.apiKey` | string | Anthropic API key |
| `providers.together.apiKey` | string | Together AI API key |
| `providers.groq.apiKey` | string | Groq API key (for voice) |
| `tools.exec.timeout` | int | Shell command timeout (seconds) |
| `tools.exec.restrictToWorkspace` | bool | Limit file access to workspace |
| `tools.exec.maxContextTokens` | int | Max tokens for conversation history |
| `tools.web.search.apiKey` | string | Brave Search API key |
| `tools.mcp.enabled` | bool | Enable MCP servers |
| `channels.discord.enabled` | bool | Enable Discord |
| `channels.telegram.enabled` | bool | Enable Telegram |
| `channels.whatsapp.enabled` | bool | Enable WhatsApp |

<details>
<summary><b>Full config example</b></summary>

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-20250514",
      "maxToolIterations": 20
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    },
    "groq": {
      "apiKey": "gsk_xxx"
    }
  },
  "channels": {
    "discord": {
      "enabled": true,
      "token": "xxx",
      "allowFrom": [123456789],
      "allowedChannels": []
    },
    "telegram": {
      "enabled": false,
      "token": "123456:ABC...",
      "allowFrom": ["123456789"]
    },
    "whatsapp": {
      "enabled": false,
      "allowFrom": ["+1234567890"]
    }
  },
  "tools": {
    "exec": {
      "timeout": 60,
      "restrictToWorkspace": false,
      "maxContextTokens": 100000
    },
    "web": {
      "search": {
        "apiKey": "BSA..."
      }
    },
    "mcp": {
      "enabled": false,
      "servers": {}
    }
  }
}
```

</details>

## 🖥️ CLI Reference

| Command | Description |
|---------|-------------|
| `icron setup` | Guided setup wizard (recommended) |
| `icron onboard` | Initialize config & workspace |
| `icron validate` | Validate configuration file |
| `icron agent -m "..."` | Send a message |
| `icron agent` | Interactive chat mode |
| `icron gateway` | Start gateway (web UI + channels) |
| `icron status` | Show status |
| `icron channels login` | Link WhatsApp (QR scan) |
| `icron channels status` | Show channel status |
| `icron cron list` | List scheduled jobs |
| `icron cron add` | Add a scheduled job |
| `icron cron remove <id>` | Remove a scheduled job |

## 🐳 Docker

```bash
# Build the image
docker build -t icron .

# Initialize config
docker run -v ~/.icron:/root/.icron --rm icron onboard

# Edit config
vim ~/.icron/config.json

# Run gateway
docker run -v ~/.icron:/root/.icron -p 18790:18790 icron gateway
```

**Railway deployment:**
- Uses `Dockerfile` and `railway.json`
- Set environment variables: `TOGETHER_API_KEY`, `MODEL`, `ICRON_WRITE_CONFIG=1`
- Optional: `TELEGRAM_TOKEN`, `TELEGRAM_ALLOW_FROM`, `WEBSEARCH_API_KEY`

## 📁 Project Structure

```
icron/
├── agent/          # Core agent logic
│   ├── loop.py     # Agent loop (LLM ↔ tools)
│   ├── context.py  # Prompt builder
│   ├── memory.py   # Persistent memory
│   ├── subagent.py # Background task execution
│   └── tools/      # Built-in tools
├── channels/       # Discord, Telegram, WhatsApp
├── bus/            # Message routing
├── cron/           # Scheduled tasks
├── heartbeat/      # Proactive checks
├── providers/      # LLM providers
├── session/        # Conversation sessions
├── mcp/            # MCP server integration
├── config/         # Configuration
└── cli/            # CLI commands
```

## 📚 Documentation (DRY)

Keep documentation in `/docs` for reusability:

| File | Purpose |
|------|---------|
| `architecture.md` | System overview, components, data flow |
| `decisions.md` | Why things were built this way |
| `conventions.md` | Naming, formatting, repo rules |
| `workflows.md` | How things are built, tested, deployed |
| `integrations.md` | APIs, services, auth, rate limits |
| `glossary.md` | Domain terms and meanings |

> **Rule of thumb:** If you explain it twice, document it once.

## 🤝 Contribute

PRs welcome! The codebase is intentionally small and readable.

**Roadmap:**
- [x] Discord integration
- [x] Voice transcription (Telegram/Groq)
- [x] Persistent memory
- [x] MCP server support
- [x] Scheduled reminders
- [x] Context trimming
- [ ] WhatsApp voice transcription
- [ ] Multi-modal (images, voice)
- [ ] Email integration
- [ ] Calendar integration

<p align="center">
  <sub>icron is for educational and personal use</sub>
</p>
