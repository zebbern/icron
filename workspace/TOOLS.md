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

### rename_file
Rename a file or directory to a new name in the same location.
```
rename_file(old_path: str, new_name: str) -> str
```

**Parameters:**
- `old_path`: The current path of the file or directory
- `new_name`: The new name (not full path, just the name)

### move_file
Move a file or directory to a new location.
```
move_file(source: str, destination: str) -> str
```

### copy_file
Copy a file to a new location.
```
copy_file(source: str, destination: str) -> str
```

### create_dir
Create a new directory (including parent directories if needed).
```
create_dir(path: str) -> str
```

## Code Search

### glob
Find files matching a glob pattern.
```
glob(pattern: str, path: str = ".") -> str
```

**Examples:**
```
glob("**/*.py")           # All Python files recursively
glob("src/**/*.ts")       # TypeScript files in src/
glob("*.md", "docs")      # Markdown files in docs/
```

### grep
Search for text patterns in files.
```
grep(pattern: str, path: str = ".", include: str = None) -> str
```

**Parameters:**
- `pattern`: Text or regex pattern to search for
- `path`: Directory to search in (default: current directory)
- `include`: Optional file pattern filter (e.g., "*.py")

**Examples:**
```
grep("TODO")              # Find all TODOs
grep("def main", ".", "*.py")  # Find main functions in Python files
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

## Memory

Icron provides semantic memory tools for persistent knowledge storage. Memories are stored as Markdown files and indexed for semantic search.

### memory_search
Semantic search across all memories using hybrid BM25 + vector search.
```
memory_search(query: str, limit: int = 5) -> str
```

**Parameters:**
- `query`: Natural language search query
- `limit`: Maximum number of results to return (default: 5)

**Example:**
```python
memory_search(query="user preferences for code style")
```

### memory_write
Save content to MEMORY.md or today's daily log.
```
memory_write(content: str, to_daily: bool = False) -> str
```

**Parameters:**
- `content`: The content to save (Markdown supported)
- `to_daily`: If True, append to daily log (memory/YYYY-MM-DD.md); if False, append to MEMORY.md

**Example:**
```python
# Save to curated long-term memory
memory_write(content="User prefers TypeScript over JavaScript")

# Save to daily log
memory_write(content="Discussed project architecture", to_daily=True)
```

### memory_get
Read a specific memory file.
```
memory_get(filename: str = "MEMORY.md") -> str
```

**Parameters:**
- `filename`: Name of file to read (default: MEMORY.md)

**Example:**
```python
memory_get()  # Read MEMORY.md
memory_get(filename="2026-02-06.md")  # Read specific daily log
```

### memory_list
List all memory files in the workspace.
```
memory_list() -> str
```

Returns a list of all memory files including MEMORY.md and daily logs.

---

## Background Tasks

### spawn
Spawn a subagent to handle a task in the background.
```
spawn(task: str, label: str = None) -> str
```

Use for complex or time-consuming tasks that can run independently. The subagent will complete the task and report back when done.

## Reminder Tools

Direct tool APIs for setting and managing reminders programmatically.

### set_reminder
Set a reminder to be delivered after a delay.
```
set_reminder(message: str, delay: str) -> str
```

**Parameters:**
- `message`: The reminder message to deliver
- `delay`: Time delay (e.g., "5m", "2h", "1d", or natural language like "in 30 minutes")

**Examples:**
```
set_reminder("Check the build status", "15m")
set_reminder("Call John back", "2h")
set_reminder("Submit weekly report", "1d")
```

### list_reminders
List all active reminders.
```
list_reminders() -> str
```

Returns a formatted list of pending reminders with their IDs, messages, and scheduled times.

### cancel_reminder
Cancel a specific reminder by ID.
```
cancel_reminder(reminder_id: str) -> str
```

**Example:**
```
cancel_reminder("abc123")
```

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

## MCP (Model Context Protocol) Tools

MCP servers extend icron with additional tools dynamically loaded at runtime.

### How It Works

1. MCP servers are configured in `config.json` under `mcp.servers`
2. On startup, icron connects to configured servers and discovers their tools
3. Tools become available with an `mcp_<server>_` prefix

### Currently Configured Servers

Check runtime status via `/api/mcp/status` or the MCP tab in the Control Room UI.

**Common MCP servers:**
| Server | Tools | Description |
|--------|-------|-------------|
| time | 2 | Get current time, convert timezones |
| filesystem | 14 | File operations (read, write, list, search) |
| fetch | 4 | HTTP requests (get, post JSON, fetch) |
| sequential-thinking | 1 | Step-by-step reasoning |

### Tool Examples

MCP tools are called like any other tool:

```python
# Time server tools
mcp_time_get_current_time(timezone="America/New_York")

# Filesystem server tools  
mcp_filesystem_read_file(path="/path/to/file")
mcp_filesystem_search_files(pattern="*.py")

# Fetch server tools
mcp_fetch_fetch(url="https://api.example.com/data")
```

### Adding MCP Servers

Via Control Room UI:
1. Go to MCP tab
2. Enable presets or add custom servers

Via config.json:
```json
{
  "mcp": {
    "enabled": true,
    "servers": {
      "your-server": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@server/package"]
      }
    }
  }
}
```

---

## Adding Custom Tools

To add custom tools:
1. Create a class that extends `Tool` in `icron/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
