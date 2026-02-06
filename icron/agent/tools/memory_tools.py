"""Memory tools for the agent to save and recall information."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from icron.agent.tools.base import Tool


class RememberTool(Tool):
    """
    Tool to save information to long-term memory.
    
    When the user asks to remember something, the agent should use this tool
    to persist the information across sessions.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_file = workspace / "memory" / "MEMORY.md"
    
    @property
    def name(self) -> str:
        return "remember"
    
    @property
    def description(self) -> str:
        return (
            "Save important information to long-term memory. Use this when the user asks you to "
            "'remember', 'note', 'save', or 'store' something. The information will persist across "
            "conversations and sessions. Examples: remembering names, preferences, facts, etc."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "A short label/category for what you're remembering (e.g., 'user:cat_name', 'preference:language', 'fact:birthday')"
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember"
                }
            },
            "required": ["key", "value"]
        }
    
    def _ensure_memory_file(self) -> None:
        """Ensure memory file and directory exist."""
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self.memory_file.write_text(
                "# Long-term Memory\n\n"
                "This file stores important information that should persist across sessions.\n\n"
                "## Memories\n\n",
                encoding="utf-8"
            )
    
    async def execute(self, **kwargs: Any) -> str:
        """Save information to memory."""
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        
        if not key or not value:
            return "Error: Both 'key' and 'value' are required"
        
        self._ensure_memory_file()
        
        # Read current content
        content = self.memory_file.read_text(encoding="utf-8")
        
        # Format the memory entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- **{key}**: {value} *(saved: {timestamp})*\n"
        
        # Check if key already exists and update it
        pattern = rf"- \*\*{re.escape(key)}\*\*:.*?\n"
        if re.search(pattern, content):
            # Update existing entry
            content = re.sub(pattern, entry, content)
        else:
            # Add new entry to Memories section
            if "## Memories" in content:
                # Add after the Memories heading
                content = content.replace(
                    "## Memories\n\n",
                    f"## Memories\n\n{entry}"
                )
            else:
                # Append to end
                content += f"\n{entry}"
        
        # Write back
        self.memory_file.write_text(content, encoding="utf-8")
        
        return f"✅ Remembered: {key} = {value}"


class RecallTool(Tool):
    """
    Tool to recall information from memory.
    
    When the user asks about something that was previously remembered,
    the agent can use this tool to retrieve it.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_file = workspace / "memory" / "MEMORY.md"
    
    @property
    def name(self) -> str:
        return "recall"
    
    @property
    def description(self) -> str:
        return (
            "Retrieve information from long-term memory. Use this when you need to recall "
            "something that was previously remembered, or when the user asks 'do you remember', "
            "'what is my', 'check your notes', etc. Returns all memories or filters by query."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search term to filter memories. Leave empty to get all memories."
                }
            },
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Recall information from memory."""
        query = kwargs.get("query", "")
        
        if not self.memory_file.exists():
            return "📭 No memories stored yet."
        
        content = self.memory_file.read_text(encoding="utf-8")
        
        # Extract memory entries (lines starting with "- **")
        memories = re.findall(r"- \*\*(.+?)\*\*: (.+?)(?:\*.*\*)?\n", content)
        
        if not memories:
            return "📭 No memories found."
        
        # Filter if query provided
        if query:
            query_lower = query.lower()
            memories = [
                (k, v) for k, v in memories
                if query_lower in k.lower() or query_lower in v.lower()
            ]
        
        if not memories:
            return f"📭 No memories matching '{query}'."
        
        # Format results
        results = ["📝 **Memories:**"]
        for key, value in memories:
            results.append(f"- **{key}**: {value}")
        
        return "\n".join(results)


class NoteTodayTool(Tool):
    """
    Tool to add notes for today.
    
    Creates daily note files for journaling or task tracking.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
    
    @property
    def name(self) -> str:
        return "note_today"
    
    @property
    def description(self) -> str:
        return (
            "Add a note to today's daily log. Use for journaling, task tracking, "
            "or recording events that happened today. Notes are stored in dated files."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "The note content to add"
                }
            },
            "required": ["note"]
        }
    
    def _get_today_file(self) -> Path:
        """Get path to today's note file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.memory_dir / f"{date_str}.md"
    
    async def execute(self, **kwargs: Any) -> str:
        """Add a note for today."""
        note = kwargs.get("note", "")
        
        if not note:
            return "Error: 'note' is required"
        
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        today_file = self._get_today_file()
        timestamp = datetime.now().strftime("%H:%M")
        
        if today_file.exists():
            content = today_file.read_text(encoding="utf-8")
            content += f"\n- [{timestamp}] {note}"
        else:
            date_str = datetime.now().strftime("%Y-%m-%d (%A)")
            content = f"# {date_str}\n\n- [{timestamp}] {note}"
        
        today_file.write_text(content, encoding="utf-8")
        
        return f"📓 Note added for today at {timestamp}"
