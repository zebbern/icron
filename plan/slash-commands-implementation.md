# Slash Commands & Session Management Implementation

## Overview

Implement user-friendly slash commands and session management for icron.

## Tasks

- [ ] Task 1: Create `/help` command - Show all capabilities
- [ ] Task 2: Create slash command handler/dispatcher
- [ ] Task 3: Add `/remind` command - Quick reminder setting
- [ ] Task 4: Add `/search` command - Quick web search
- [ ] Task 5: Add session management commands:
  - `/sessions` - List all sessions
  - `/session clear` - Clear current session
  - `/session new` - Start fresh session
  - `/session rename [name]` - Rename current session
  - `/session switch [id]` - Switch to another session
- [ ] Task 6: Update AGENTS.md and TOOLS.md
- [ ] Task 7: Test and document

## Technical Design

### Slash Command Handler

Location: `icron/agent/commands.py`

```python
class CommandHandler:
    """Handle slash commands before passing to agent."""
    
    def __init__(self, session_manager, bus):
        self.session_manager = session_manager
        self.bus = bus
        self.commands = self._register_commands()
    
    def is_command(self, text: str) -> bool:
        return text.startswith('/')
    
    async def handle(self, text: str, context: dict) -> str | None:
        """Handle command, return response or None for agent."""
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.commands:
            return await self.commands[cmd](args, context)
        return None  # Not a command, send to agent
```

### Session Management

Extend `SessionManager` with:
- `list_sessions()` - Return all session keys
- `rename_session(old_key, new_key)` - Rename session
- `delete_session(key)` - Delete session data
- `get_session_info(key)` - Get metadata (created, messages, etc.)

## Status

Created: 2026-02-06
Status: In Progress
