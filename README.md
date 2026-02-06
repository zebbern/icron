<div align="center">
  <img src="icron_logo.png" alt="icron" width="500">
  <h1>icron: Ultra-Lightweight Personal AI Assistant</h1>
</div>

🐈 **icron** is an **ultra-lightweight** personal AI assistant inspired by [Clawdbot](https://github.com/openclaw/openclaw) 

⚡️ Delivers core agent functionality in just **~4,000** lines of code — **99% smaller** than Clawdbot's 430k+ lines.

## 🏗️ Architecture

<p align="center">
  <img src="icron_arch.png" alt="icron architecture" width="800">
</p>

## ✨ Features

<table align="center">
  <tr align="center">
    <th><p align="center">📈 24/7 Real-Time Market Analysis</p></th>
    <th><p align="center">🚀 Full-Stack Software Engineer</p></th>
    <th><p align="center">📅 Smart Daily Routine Manager</p></th>
    <th><p align="center">📚 Personal Knowledge Assistant</p></th>
  </tr>
  <tr>
    <td align="center"><p align="center"><img src="case/search.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/code.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/scedule.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/memory.gif" width="180" height="400"></p></td>
  </tr>
  <tr>
    <td align="center">Discovery • Insights • Trends</td>
    <td align="center">Develop • Deploy • Scale</td>
    <td align="center">Schedule • Automate • Organize</td>
    <td align="center">Learn • Memory • Reasoning</td>
  </tr>
</table>

## 📦 Install

**Install from source** (latest features, recommended for development)

```bash
git clone https://github.com/zebbern/icron.git
cd icron
pip install -e .
```

**Install with [uv](https://github.com/astral-sh/uv)** (stable, fast)

```bash
uv tool install icron
```

**Install from PyPI** (stable)

```bash
pip install icron
```

## 🚀 Quick Start

> [!TIP]
> Set your API key in `~/.icron/config.json`.
> Get API keys: [OpenRouter](https://openrouter.ai/keys) or [Together AI](https://api.together.xyz/settings/api-keys) (LLM) · [Brave Search](https://brave.com/search/api/) (optional, for web search)
> You can also change the model to `minimax/minimax-m2` for lower cost.

**1. Initialize**

```bash
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
      "model": "anthropic/claude-opus-4-5"
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA-xxx"
      }
    }
  }
}
```

**Together AI alternative** (`~/.icron/config.json`)

```json
{
  "providers": {
    "together": {
      "apiKey": "together-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    }
  }
}
```


**3. Chat**

```bash
icron agent -m "What is 2+2?"
```

That's it! You have a working AI assistant in 2 minutes.

## 🖥️ Local Models (vLLM)

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

> [!TIP]
> The `apiKey` can be any non-empty string for local servers that don't require authentication.

## Railway (Docker)

Railway can build from the included `Dockerfile` and uses `railway.json` to force Docker builds.

**Required environment variables**
- `TOGETHER_API_KEY` (or `TOGETHERAI_API_KEY`)
- `MODEL` (Together model name, e.g. `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo`)
- `icron_WRITE_CONFIG=1`

**Optional environment variables**
- `OPENROUTER_API_KEY` (if you prefer OpenRouter)
- `WEBSEARCH_API_KEY` (Brave Search)
- `TELEGRAM_TOKEN`, `TELEGRAM_ALLOW_FROM` (comma-separated), `TELEGRAM_ENABLED`
- `WHATSAPP_ENABLED`

Railway injects `PORT`, and the gateway binds to it automatically. Health checks respond on `/health`.

## Web UI (Settings)

The gateway exposes a lightweight web UI for configuring keys and basic settings.

- Open `http://<host>:<port>/` to view and update settings.
- Advanced GUI (Svelte): build with `cd ui && npm install && npm run build`, then open `http://<host>:<port>/app`.
- After saving, restart the service to apply changes.
- If `icron_WRITE_CONFIG=1`, your changes will be overwritten on restart. Set it to `0` after the first save.
- Disable the UI with `icron_HTTP_ENABLED=0`.

## 💬 Chat Apps

Talk to your icron through Telegram, WhatsApp, or Discord — anytime, anywhere.

| Channel | Setup |
|---------|-------|
| **Telegram** | Easy (just a token) |
| **WhatsApp** | Medium (scan QR) |
| **Discord** | Easy (just a token) |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

**1. Create a bot**
- Open Telegram, search `@BotFather`
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

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires **Node.js ≥18**.

**1. Link device**

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
# Terminal 1
icron channels login

# Terminal 2
icron gateway
```

</details>

<details>
<summary><b>Discord</b></summary>

**1. Create a Discord Application and Bot**

1. Go to [Discord Developer Portal](https://discord.com/developers/applications) and log in
2. Click **"New Application"** (top-right button)
3. Enter a name (e.g., "icron") and click **Create**
4. In the left sidebar, click **"Bot"**
5. Click **"Reset Token"** (or "Add Bot" if you haven't created one yet)
6. **Copy the token** — this is your bot token (you won't be able to see it again!)
   - The token looks like: `XXX11Xx1x11X11x111Xxx.XxXxX.XXXXXXxXxXxXXXXXxXxXXXXXXX`
   - ⚠️ Keep this secret and never share it publicly
7. Under **Privileged Gateway Intents**, enable:
   - ✅ **Message Content Intent** (required to read message content)
   - ✅ **Server Members Intent** (optional, for user info)
8. Click **"Save Changes"** at the bottom

**2. Invite bot to your server**

1. In the Developer Portal, go to **OAuth2** → **URL Generator**
2. Under **Scopes**, select: `bot`
3. Under **Bot Permissions**, select:
   - ✅ Send Messages
   - ✅ Read Messages/View Channels
   - ✅ Read Message History
4. Copy the generated URL from the bottom
5. Open the URL in your browser and select your server to invite the bot

**3. Configure**

Edit `~/.icron/config.json`:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN_HERE",
      "allow_from": [YOUR_USER_ID_HERE],
      "allowed_channels": []
    }
  }
}
```

> **Configuration Options:**
> - `token`: Your Discord bot token (required)
> - `allow_from`: List of user IDs allowed to interact with the bot (use integers, not strings)
> - `allowed_channels`: List of channel IDs where bot will respond (empty = all channels)
>
> **Get your Discord User ID:**
> 1. Enable Developer Mode: Discord → User Settings → Advanced → toggle Developer Mode
> 2. Right-click your name in any server
> 3. Select "Copy User ID"
>
> **Get a Channel ID:**
> 1. Right-click the channel name
> 2. Select "Copy Channel ID"
>
> **Tips:**
> - Leave `allow_from` as `[]` to allow all users (not recommended for production)
> - Leave `allowed_channels` as `[]` to respond in all channels
> - Use `allowed_channels` to restrict the bot to specific channels
>
> **Image Support:**
> - ✅ **Receiving images**: Bot downloads attachments to `~/.icron/media/`
> - ✅ **Vision/analysis**: Claude can analyze images sent to the bot
> - ✅ **Sending images**: Agent can send images via tool results

**4. Run**

```bash
icron gateway
```

Your bot is now ready! Send it a message in any server it's invited to, or DM it directly.

</details>

## ⚙️ Configuration

Config file: `~/.icron/config.json`

### Providers

> [!NOTE]
> Groq provides free voice transcription via Whisper. If configured, Telegram voice messages will be automatically transcribed.

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `openrouter` | LLM (recommended, access to all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM (Claude direct) | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM (GPT direct) | [platform.openai.com](https://platform.openai.com) |
| `groq` | LLM + **Voice transcription** (Whisper) | [console.groq.com](https://console.groq.com) |
| `gemini` | LLM (Gemini direct) | [aistudio.google.com](https://aistudio.google.com) |


<details>
<summary><b>Full config example</b></summary>

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
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
    "telegram": {
      "enabled": true,
      "token": "123456:ABC...",
      "allowFrom": ["123456789"]
    },
    "whatsapp": {
      "enabled": false
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA..."
      }
    }
  }
}
```

</details>

## CLI Reference

| Command | Description |
|---------|-------------|
| `icron onboard` | Initialize config & workspace |
| `icron agent -m "..."` | Chat with the agent |
| `icron agent` | Interactive chat mode |
| `icron gateway` | Start the gateway (connects to Telegram/WhatsApp/Discord) |
| `icron status` | Show status |
| `icron channels login` | Link WhatsApp (scan QR) |
| `icron channels status` | Show channel status |

<details>
<summary><b>Scheduled Tasks (Cron)</b></summary>

```bash
# Add a job
icron cron add --name "daily" --message "Good morning!" --cron "0 9 * * *"
icron cron add --name "hourly" --message "Check status" --every 3600

# List jobs
icron cron list

# Remove a job
icron cron remove <job_id>
```

</details>

## 🐳 Docker

> [!TIP]
> The `-v ~/.icron:/root/.icron` flag mounts your local config directory into the container, so your config and workspace persist across container restarts.

Build and run icron in a container:

```bash
# Build the image
docker build -t icron .

# Initialize config (first time only)
docker run -v ~/.icron:/root/.icron --rm icron onboard

# Edit config on host to add API keys
vim ~/.icron/config.json

# Run gateway (connects to Telegram/WhatsApp/Discord)
docker run -v ~/.icron:/root/.icron -p 18790:18790 icron gateway

# Or run a single command
docker run -v ~/.icron:/root/.icron --rm icron agent -m "Hello!"
docker run -v ~/.icron:/root/.icron --rm icron status
```

## 📁 Project Structure

```
icron/
├── agent/          # 🧠 Core agent logic
│   ├── loop.py     #    Agent loop (LLM ↔ tool execution)
│   ├── context.py  #    Prompt builder
│   ├── memory.py   #    Persistent memory
│   ├── skills.py   #    Skills loader
│   ├── subagent.py #    Background task execution
│   └── tools/      #    Built-in tools (incl. spawn)
├── skills/         # 🎯 Bundled skills (github, weather, tmux...)
├── channels/       # 📱 WhatsApp integration
├── bus/            # 🚌 Message routing
├── cron/           # ⏰ Scheduled tasks
├── heartbeat/      # 💓 Proactive wake-up
├── providers/      # 🤖 LLM providers (OpenRouter, etc.)
├── session/        # 💬 Conversation sessions
├── config/         # ⚙️ Configuration
└── cli/            # 🖥️ Commands
```

## 🤝 Contribute & Roadmap

PRs welcome! The codebase is intentionally small and readable. 🤗

**Roadmap** — Pick an item and [open a PR](https://github.com/zebbern/icron/pulls)!

- [x] **Voice Transcription** — Support for Groq Whisper (Issue #13)
- [ ] **Multi-modal** — See and hear (images, voice, video)
- [ ] **Long-term memory** — Never forget important context
- [ ] **Better reasoning** — Multi-step planning and reflection
- [ ] **More integrations** — Discord, Slack, email, calendar
- [ ] **Self-improvement** — Learn from feedback and mistakes

### Contributors

<a href="https://github.com/zebbern/icron/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=zebbern/icron" />
</a>


## ⭐ Star History

<div align="center">
  <a href="https://star-history.com/#zebbern/icron&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=zebbern/icron&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=zebbern/icron&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=zebbern/icron&type=Date" style="border-radius: 15px; box-shadow: 0 0 30px rgba(0, 217, 255, 0.3);" />
    </picture>
  </a>
</div>

<p align="center">
  <em> Thanks for visiting ✨ icron!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=zebbern.icron&style=for-the-badge&color=00d4ff" alt="Views">
</p>


<p align="center">
  <sub>icron is for educational, research, and technical exchange purposes only</sub>
</p>
