# Available Tools

This document describes the tools available to icron.

## File Operations

### read_file
Read the contents of a file.
```
read_file(path: str) -> str
```

### write_file
Write content to a file (creates parent directories if needed).
```
write_file(path: str, content: str) -> str
```

### edit_file
Edit a file by replacing specific text.
```
edit_file(path: str, old_text: str, new_text: str) -> str
```

### list_dir
List contents of a directory.
```
list_dir(path: str) -> str
```

## Shell Execution

### exec
Execute a shell command and return output.
```
exec(command: str, working_dir: str = None) -> str
```

**Safety Notes:**
- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- Optional `restrictToWorkspace` config to limit paths

## Web Access

### web_search
Search the web using Brave Search API.
```
web_search(query: str, count: int = 5) -> str
```

Returns search results with titles, URLs, and snippets. Requires `tools.web.search.apiKey` in config.

### web_fetch
Fetch and extract main content from a URL.
```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**Notes:**
- Content is extracted using readability
- Supports markdown or plain text extraction
- Output is truncated at 50,000 characters by default

## Communication

### message
Send a message to the user.
```
message(content: str, media: list[str] = None, channel: str = None, chat_id: str = None) -> str
```

**Parameters:**
- `content`: The message text to send
- `media`: Optional list of file paths to attach (images, screenshots, etc.)
- `channel`: Optional target channel override
- `chat_id`: Optional target chat ID override

**Example with attachment:**
```python
message(content="Here's the screenshot", media=["/path/to/screenshot.png"])
```

## Screenshots

### screenshot
Capture a screenshot of a web page.
```
screenshot(url: str, full_page: bool = False, width: int = 1280, height: int = 720) -> str
```

**Parameters:**
- `url`: URL to capture (must be http/https)
- `full_page`: Capture full scrollable page (default: False)
- `width`: Viewport width in pixels (default: 1280)
- `height`: Viewport height in pixels (default: 720)

**IMPORTANT:** After taking a screenshot, you must use the `message` tool with the `media` parameter to send it to the user.

**Example workflow:**
```python
# Step 1: Take screenshot
result = screenshot(url="https://github.com/user")
# Returns: "Screenshot captured... Path: /workspace/media/screenshots/screenshot_xxx.png..."

# Step 2: Send to user with media parameter
message(content="Here's the screenshot!", media=["/workspace/media/screenshots/screenshot_xxx.png"])
```

## Background Tasks

### spawn
Spawn a subagent to handle a task in the background.
```
spawn(task: str, label: str = None) -> str
```

Use for complex or time-consuming tasks that can run independently. The subagent will complete the task and report back when done.

## Scheduled Reminders (Cron)

Use the `exec` tool to create scheduled reminders with `icron cron add`:

### Set a recurring reminder
```bash
# Every day at 9am
icron cron add --name "morning" --message "Good morning! ☀️" --cron "0 9 * * *"

# Every 2 hours
icron cron add --name "water" --message "Drink water! 💧" --every 7200
```

### Set a one-time reminder
```bash
# At a specific time (ISO format)
icron cron add --name "meeting" --message "Meeting starts now!" --at "2025-01-31T15:00:00"
```

### Manage reminders
```bash
icron cron list              # List all jobs
icron cron remove <job_id>   # Remove a job
```

## Heartbeat Task Management

The `HEARTBEAT.md` file in the workspace is checked every 30 minutes.
Use file operations to manage periodic tasks:

### Add a heartbeat task
```python
# Append a new task
edit_file(
    path="HEARTBEAT.md",
    old_text="## Example Tasks",
    new_text="- [ ] New periodic task here\n\n## Example Tasks"
)
```

### Remove a heartbeat task
```python
# Remove a specific task
edit_file(
    path="HEARTBEAT.md",
    old_text="- [ ] Task to remove\n",
    new_text=""
)
```

### Rewrite all tasks
```python
# Replace the entire file
write_file(
    path="HEARTBEAT.md",
    content="# Heartbeat Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n"
)
```

---

## Slash Commands

Slash commands provide quick access to common operations without invoking the LLM.

### Help Commands
```
/help              # List all available commands
/help sessions     # Detailed help about sessions
/help memory       # Detailed help about memory
/help reminders    # Detailed help about reminders
/help search       # Detailed help about web search
/help commands     # List all slash commands
```

### Session Management
```
/sessions              # List all sessions
/session clear         # Clear current session history
/session new           # Start a fresh session
/session rename [name] # Rename the current session
/session switch [id]   # Switch to a different session
```

### Quick Actions
```
/remind [time] [message]  # Set a reminder
                          # Examples: /remind 30m check email
                          #           /remind 2h call john
/search [query]           # Quick web search
/memory                   # Access memory operations
```

**Note:** Slash commands bypass the LLM and are processed directly by icron for faster response times.

---

## Skills

Skills are reusable task modules that extend icron's capabilities:

### List available skills
```
/skills
```

### Run a skill
```
/skills run [name]
```

Skills are located in `icron/skills/` and include:
- `weather` - Weather lookups
- `summarize` - Content summarization
- `github` - GitHub operations
- `cron` - Scheduled task management

---

## Templates

Templates provide pre-built prompts for common development tasks:

### List templates
```
/templates
```

### Run a template
```
/template [name]
```

**Available templates:**
| Template | Description |
|----------|-------------|
| `morning` | 🌅 Morning briefing - weather, calendar, reminders, news |
| `daily` | 📊 Daily summary - accomplishments and pending tasks |
| `research` | 🔬 Research a topic and summarize findings |
| `recap` | 📝 Summarize the current conversation session |

**Example:**
```
/template morning
/template research AI trends
```
Templates provide structured workflows for common tasks.

---

## Weather

Quick weather lookup via slash command:

```
/weather [location]
```

**Examples:**
```
/weather London
/weather New York, NY
/weather Tokyo
```

Returns current conditions, temperature, humidity, and forecast.

---

## Adding Custom Tools

To add custom tools:
1. Create a class that extends `Tool` in `icron/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
