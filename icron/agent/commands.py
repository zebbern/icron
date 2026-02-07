"""Slash command handler for icron chat commands.

This module provides a CommandHandler class that processes slash commands
from users, handling session management and delegating certain tasks to the agent.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from loguru import logger

if TYPE_CHECKING:
    from icron.session.manager import SessionManager


# Command prefix
COMMAND_PREFIX = "/"

# Message templates for common workflows
TEMPLATES: dict[str, dict[str, str]] = {
    "morning": {
        "name": "Morning Briefing",
        "emoji": "🌅",
        "description": "Weather, calendar, reminders, and news summary",
        "instruction": """Provide a comprehensive morning briefing:
1. Get the current weather for the user's location
2. Check for any calendar events or meetings today
3. List any pending reminders or tasks
4. Summarize the top 3-5 news headlines relevant to the user
Format the response in a clear, scannable way with sections.""",
    },
    "daily": {
        "name": "Daily Summary",
        "emoji": "📊",
        "description": "What was accomplished and pending tasks",
        "instruction": """Provide a daily summary:
1. Summarize what was discussed and accomplished in today's conversations
2. List any tasks that were mentioned but not completed
3. Highlight any follow-ups or action items
4. Suggest priorities for tomorrow
Be concise but comprehensive.""",
    },
    "research": {
        "name": "Research Task",
        "emoji": "🔬",
        "description": "Research a topic and summarize findings",
        "instruction": """Conduct thorough research on the specified topic:
1. Search the web for authoritative sources
2. Gather key facts, statistics, and expert opinions
3. Identify multiple perspectives if applicable
4. Synthesize findings into a clear summary
5. Include sources and links for reference
Provide a well-structured research report.""",
    },
    "recap": {
        "name": "Conversation Recap",
        "emoji": "📝",
        "description": "Summarize the current session",
        "instruction": """Summarize the current conversation session:
1. List the main topics discussed
2. Highlight key decisions or conclusions made
3. Note any unanswered questions or pending items
4. Summarize any code, files, or artifacts created
Keep it concise but capture all important points.""",
    },
}

# Help topics with detailed information
HELP_TOPICS: dict[str, str] = {
    "sessions": """**Session Management**

Sessions store your conversation history. Each channel/chat has its own session.

Commands:
• `/sessions` - List all sessions with IDs
• `/session clear` - Clear current session history
• `/session new` - Start a fresh session (alias: `/new`)
• `/session rename [name]` - Rename current session
• `/session switch [id]` - Switch to another session

Sessions are automatically saved and persist across restarts.""",

    "memory": """**Memory System**

icron maintains long-term memory about your preferences and context.

Commands:
• `/memory` - Show current memory information

Memory is stored separately from sessions and persists permanently.""",

    "reminders": """**Reminders**

Set quick reminders using natural language time expressions.

Usage:
• `/remind 5m Check the build` - Remind in 5 minutes
• `/remind 2h Review PR` - Remind in 2 hours
• `/remind tomorrow 9am Team meeting` - Remind tomorrow at 9am

The agent will process and schedule the reminder for you.""",

    "search": """**Quick Search**

Perform web searches directly from chat.

Usage:
• `/search python asyncio tutorial` - Search the web
• `/search latest news on AI` - Find recent information

The agent will search and summarize results for you.""",

    "collab": """**Multi-Model Collaboration**

Have multiple AI providers collaborate to solve a task together.

Usage:
• `/collab Design a REST API authentication system`
• `/collab What's the best architecture for a chat app?`

**Requirements:**
At least 2 providers must be configured with API keys (e.g., Anthropic + OpenAI).

**How It Works:**
1. **Phase 1 - Analysis**: Each model analyzes the task independently
2. **Phase 2 - Critique**: Models review each other's proposals
3. **Phase 3 - Synthesis**: Best model creates final answer

This produces better results than any single model by combining their strengths.""",

    "commands": """**All Commands**

Session Management:
• `/sessions` - List all sessions
• `/session clear` - Clear history
• `/session new` or `/new` - New session
• `/session rename [name]` - Rename session
• `/session switch [id]` - Switch session

Quick Actions:
• `/remind [time] [message]` - Set reminder
• `/search [query]` - Web search
• `/memory` - Memory info
• `/weather [location]` - Get weather
• `/skills` - List available skills
• `/skills run [name]` - Run a skill
• `/collab [task]` - Multi-model collaboration

Help:
• `/help` - Show all commands
• `/help [topic]` - Detailed help (sessions, memory, reminders, search, skills, weather)""",

    "skills": """**Skills System**

Skills are reusable capabilities that extend icron's abilities.

Commands:
• `/skills` - List all available skills
• `/skills run [name]` - Execute a skill by name

Built-in skills include:
• `github` - Interact with GitHub using gh CLI
• `weather` - Get weather info (no API key needed)
• `summarize` - Summarize URLs, files, and videos
• `tmux` - Remote-control tmux sessions
• `skill-creator` - Create new skills

Skills are defined in SKILL.md files with instructions for the agent.""",

    "weather": """**Weather Lookup**

Get current weather and forecasts without any API key.

Usage:
• `/weather` - Get weather for default location
• `/weather London` - Weather for London
• `/weather New York` - Weather for New York
• `/weather JFK` - Weather by airport code

Powered by wttr.in and Open-Meteo (free services)."""
}


class CommandHandler:
    """
    Handles slash commands from user input.

    Slash commands provide quick access to session management and common actions
    without requiring the agent to process them.

    Attributes:
        session_manager: Reference to the session manager for session operations.

    Example:
        >>> handler = CommandHandler(session_manager)
        >>> if handler.is_command("/help"):
        ...     response, handled = await handler.handle("/help", key, "discord", "123")
        ...     if handled:
        ...         print(response)
    """

    def __init__(self, session_manager: "SessionManager") -> None:
        """
        Initialize the command handler.

        Args:
            session_manager: The session manager instance for session operations.
        """
        self.session_manager = session_manager
        self._command_pattern = re.compile(r"^/([a-zA-Z]+)(?:\s+(.*))?$", re.DOTALL)

    def is_command(self, text: str) -> bool:
        """
        Check if the given text is a slash command.

        Args:
            text: The input text to check.

        Returns:
            True if the text starts with a slash command, False otherwise.

        Example:
            >>> handler.is_command("/help")
            True
            >>> handler.is_command("hello")
            False
        """
        if not text or not isinstance(text, str):
            return False
        text = text.strip()
        return text.startswith(COMMAND_PREFIX) and len(text) > 1

    async def handle(
        self,
        text: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle a slash command.

        Processes the command and returns an appropriate response. Some commands
        are handled directly (session management), while others are delegated
        to the agent (remind, search, memory).

        Args:
            text: The full command text including the slash prefix.
            session_key: The session key (channel:chat_id format).
            channel: The channel name (discord, telegram, etc.).
            chat_id: The chat/conversation ID.

        Returns:
            A tuple of (response, handled) where:
            - response: The response message, or None for delegated commands.
            - handled: True if the command was fully handled, False if it should
                      be delegated to the agent.

        Example:
            >>> response, handled = await handler.handle("/help", "discord:123", "discord", "123")
            >>> if handled:
            ...     send_message(response)
            ... else:
            ...     agent.process(text)
        """
        if not self.is_command(text):
            return None, False

        text = text.strip()
        match = self._command_pattern.match(text)

        if not match:
            return None, False

        command = match.group(1).lower()
        args = match.group(2).strip() if match.group(2) else ""

        logger.debug(f"Processing command: /{command} with args: {args!r}")

        # Route to appropriate handler
        handlers = {
            "help": self._handle_help,
            "sessions": self._handle_sessions,
            "session": self._handle_session,
            "new": self._handle_new,
            "remind": self._handle_remind,
            "search": self._handle_search,
            "memory": self._handle_memory,
            "skills": self._handle_skills,
            "weather": self._handle_weather,
            "templates": self._handle_templates,
            "template": self._handle_template,
        }

        handler = handlers.get(command)
        if handler:
            return await handler(args, session_key, channel, chat_id)

        # Unknown command
        return (
            f"❓ Unknown command: `/{command}`\n\n"
            f"Type `/help` to see available commands.",
            True
        )

    async def _handle_help(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """
        Handle /help command.

        Args:
            args: Optional topic name for detailed help.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (help text, True).
        """
        if args:
            topic = args.lower().strip()
            if topic in HELP_TOPICS:
                return HELP_TOPICS[topic], True
            available = ", ".join(sorted(HELP_TOPICS.keys()))
            return (
                f"❓ Unknown help topic: `{topic}`\n\n"
                f"Available topics: {available}",
                True
            )

        # General help
        example_prompts = self._get_example_prompts()
        help_text = """**icron Commands** 🤖

**Session Management**
• `/sessions` - List all sessions
• `/session clear` - Clear current session history
• `/session new` - Start fresh session (or `/new`)
• `/session rename [name]` - Rename current session
• `/session switch [id]` - Switch to another session

**Quick Actions**
• `/remind [time] [message]` - Set a reminder
• `/search [query]` - Quick web search
• `/memory` - Show memory information
• `/weather [location]` - Get current weather
• `/skills` - List available skills
• `/skills run [name]` - Execute a skill
• `/collab [task]` - Multi-model collaboration
• `/templates` - List message templates
• `/template [name]` - Run a template
**Help**
• `/help [topic]` - Detailed help for: sessions, memory, reminders, search, skills, weather, collab, commands

💡 Tip: You can also just chat naturally - I'll understand!

""" + example_prompts
        return help_text, True

    async def _handle_sessions(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """
        Handle /sessions command - list all sessions.

        Args:
            args: Unused.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (sessions list, True).
        """
        sessions = self.session_manager.list_sessions()

        if not sessions:
            return "📭 No sessions found.", True

        lines = ["**Your Sessions** 📋\n"]
        for i, sess in enumerate(sessions[:20], 1):  # Limit to 20
            key = sess.get("key", "unknown")
            updated = sess.get("updated_at", "unknown")
            if isinstance(updated, str) and len(updated) > 16:
                updated = updated[:16].replace("T", " ")

            marker = " ← current" if key == session_key else ""
            lines.append(f"{i}. `{key}`{marker}")
            lines.append(f"   Last updated: {updated}")

        if len(sessions) > 20:
            lines.append(f"\n*...and {len(sessions) - 20} more sessions*")

        return "\n".join(lines), True

    async def _handle_session(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """
        Handle /session subcommands.

        Args:
            args: The subcommand and its arguments.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (response, True).
        """
        if not args:
            return (
                "**Session Commands**\n\n"
                "• `/session clear` - Clear history\n"
                "• `/session new` - Start fresh\n"
                "• `/session rename [name]` - Rename\n"
                "• `/session switch [id]` - Switch session",
                True
            )

        parts = args.split(maxsplit=1)
        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcommand == "clear":
            return await self._session_clear(session_key)
        elif subcommand == "new":
            return await self._session_new(session_key, channel, chat_id)
        elif subcommand == "rename":
            return await self._session_rename(session_key, subargs)
        elif subcommand == "switch":
            return await self._session_switch(subargs, channel, chat_id)
        else:
            return (
                f"❓ Unknown session subcommand: `{subcommand}`\n\n"
                "Available: clear, new, rename, switch",
                True
            )

    async def _session_clear(self, session_key: str) -> tuple[str, bool]:
        """Clear the current session history."""
        session = self.session_manager.get_or_create(session_key)
        msg_count = len(session.messages)
        session.clear()
        self.session_manager.save(session)
        return f"🗑️ Cleared {msg_count} messages from session.", True

    async def _session_new(
        self,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """Start a new session (clears current)."""
        session = self.session_manager.get_or_create(session_key)
        session.clear()
        session.metadata["started_fresh"] = True
        self.session_manager.save(session)
        return "✨ Started fresh session. Previous history cleared.", True

    async def _session_rename(self, session_key: str, name: str) -> tuple[str, bool]:
        """Rename the current session."""
        if not name:
            return "❌ Please provide a name: `/session rename My Project`", True

        session = self.session_manager.get_or_create(session_key)
        old_name = session.metadata.get("name", session_key)
        session.metadata["name"] = name.strip()
        self.session_manager.save(session)
        return f"✅ Session renamed from `{old_name}` to `{name.strip()}`", True

    async def _session_switch(
        self,
        target: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """Switch to another session."""
        if not target:
            return "❌ Please provide a session ID: `/session switch discord:123`", True

        # Check if session exists
        sessions = self.session_manager.list_sessions()
        session_keys = [s.get("key", "") for s in sessions]

        # Try to match by key or index
        target = target.strip()
        matched_key = None

        if target in session_keys:
            matched_key = target
        elif target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(sessions):
                matched_key = sessions[idx].get("key")

        if not matched_key:
            return (
                f"❌ Session not found: `{target}`\n\n"
                "Use `/sessions` to see available sessions.",
                True
            )

        # Note: Actual session switching requires channel support
        # For now, just confirm the target exists
        return (
            f"🔄 To switch to session `{matched_key}`, you would need to "
            f"change channels or use a different chat ID.\n\n"
            f"Current session switching between chats is not yet supported.",
            True
        )

    async def _handle_new(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """
        Handle /new command (alias for /session new).

        Args:
            args: Unused.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (response, True).
        """
        return await self._session_new(session_key, channel, chat_id)

    async def _handle_remind(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /remind command - delegate to agent.

        Args:
            args: The reminder time and message.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (None, False) to delegate to agent.
        """
        if not args:
            return (
                "**Reminder Usage**\n\n"
                "• `/remind 5m Check the build`\n"
                "• `/remind 2h Review the PR`\n"
                "• `/remind tomorrow 9am Team standup`\n\n"
                "Time formats: Nm (minutes), Nh (hours), or natural language.",
                True
            )

        # Delegate to agent for processing
        logger.debug(f"Delegating /remind to agent: {args}")
        return None, False

    async def _handle_search(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /search command - delegate to agent.

        Args:
            args: The search query.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (None, False) to delegate to agent.
        """
        if not args:
            return (
                "**Search Usage**\n\n"
                "• `/search python asyncio best practices`\n"
                "• `/search latest AI news`\n"
                "• `/search how to deploy FastAPI`",
                True
            )

        # Delegate to agent for processing
        logger.debug(f"Delegating /search to agent: {args}")
        return None, False

    async def _handle_memory(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /memory command - delegate to agent.

        Args:
            args: Unused.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (None, False) to delegate to agent.
        """
        # Delegate to agent for processing
        logger.debug("Delegating /memory to agent")
        return None, False

    async def _handle_skills(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /skills command - list available skills or run a skill.

        Args:
            args: Optional subcommand (e.g., "run weather").
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (response, handled) or (None, False) to delegate.
        """
        if args:
            parts = args.split(maxsplit=1)
            subcommand = parts[0].lower()

            if subcommand == "run":
                if len(parts) < 2:
                    return (
                        "❌ Please specify a skill name: `/skills run weather`",
                        True
                    )
                skill_name = parts[1].strip()
                # Delegate to agent to execute the skill
                logger.debug(f"Delegating skill execution to agent: {skill_name}")
                return None, False

        # List all available skills
        skills = self._discover_skills()

        if not skills:
            return "📭 No skills found in the skills directory.", True

        lines = ["**Available Skills** 🛠️\n"]
        for skill in skills:
            emoji = skill.get("emoji", "📦")
            name = skill.get("name", "unknown")
            description = skill.get("description", "No description")
            lines.append(f"{emoji} **{name}** - {description}")

        lines.append("\n💡 Use `/skills run [name]` to execute a skill.")
        return "\n".join(lines), True

    def _discover_skills(self) -> list[dict]:
        """
        Discover available skills from the skills directory.

        Returns:
            List of skill metadata dictionaries.
        """
        skills = []
        # Check both built-in skills and workspace skills
        skills_dirs = [
            Path(__file__).parent.parent / "skills",  # icron/skills
            Path.cwd() / "workspace" / "skills",  # workspace/skills
        ]

        for skills_dir in skills_dirs:
            if not skills_dir.exists():
                continue

            for skill_path in skills_dir.iterdir():
                if not skill_path.is_dir():
                    continue

                skill_file = skill_path / "SKILL.md"
                if not skill_file.exists():
                    continue

                try:
                    skill_data = self._parse_skill_file(skill_file)
                    if skill_data:
                        skills.append(skill_data)
                except Exception as e:
                    logger.warning(f"Failed to parse skill {skill_path.name}: {e}")

        return sorted(skills, key=lambda s: s.get("name", ""))

    def _parse_skill_file(self, skill_file: Path) -> dict | None:
        """
        Parse a SKILL.md file and extract metadata.

        Args:
            skill_file: Path to the SKILL.md file.

        Returns:
            Dictionary with skill metadata, or None if parsing fails.
        """
        content = skill_file.read_text(encoding="utf-8")

        # Look for YAML frontmatter (between --- or ```skill)
        frontmatter = None

        # Try standard YAML frontmatter (---)
        yaml_match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
        if yaml_match:
            frontmatter = yaml_match.group(1)

        # Try skill block format (```skill)
        if not frontmatter:
            skill_match = re.match(r"^```skill\n---\n(.+?)\n---", content, re.DOTALL)
            if skill_match:
                frontmatter = skill_match.group(1)

        if not frontmatter:
            return None

        try:
            data = yaml.safe_load(frontmatter)
            if not isinstance(data, dict):
                return None

            # Extract emoji from metadata if present
            emoji = "📦"
            metadata = data.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}

            if isinstance(metadata, dict):
                icron_meta = metadata.get("icron", {})
                if isinstance(icron_meta, dict):
                    emoji = icron_meta.get("emoji", emoji)

            return {
                "name": data.get("name", skill_file.parent.name),
                "description": data.get("description", "No description"),
                "emoji": emoji,
                "path": str(skill_file.parent),
            }
        except yaml.YAMLError as e:
            logger.warning(f"YAML error in {skill_file}: {e}")
            return None

    async def _handle_weather(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /weather command - delegate to agent.

        Args:
            args: Optional location.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (None, False) to delegate to agent.
        """
        location = args.strip() if args else "local"
        logger.debug(f"Delegating /weather to agent for location: {location}")
        # Delegate to agent with instruction to fetch weather
        return None, False

    async def _handle_templates(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str, bool]:
        """
        Handle /templates command - list available message templates.

        Args:
            args: Unused.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (templates list, True).
        """
        lines = ["**Message Templates** 📋\n"]
        lines.append("Quick workflows for common tasks:\n")

        for key, template in TEMPLATES.items():
            emoji = template.get("emoji", "📦")
            name = template.get("name", key)
            description = template.get("description", "No description")
            lines.append(f"{emoji} **{key}** - {description}")

        lines.append("\n💡 Use `/template [name]` to run a template.")
        lines.append("   Example: `/template morning` or `/template research AI trends`")
        return "\n".join(lines), True

    async def _handle_template(
        self,
        args: str,
        session_key: str,
        channel: str,
        chat_id: str
    ) -> tuple[str | None, bool]:
        """
        Handle /template command - run a specific template.

        Args:
            args: Template name and optional additional args.
            session_key: The session key.
            channel: The channel name.
            chat_id: The chat ID.

        Returns:
            Tuple of (None, False) to delegate to agent with template instruction,
            or (error message, True) if template not found.
        """
        if not args:
            return (
                "**Template Usage**\n\n"
                "• `/template morning` - Run morning briefing\n"
                "• `/template daily` - Run daily summary\n"
                "• `/template research [topic]` - Research a topic\n"
                "• `/template recap` - Recap current conversation\n\n"
                "Use `/templates` to see all available templates.",
                True
            )

        parts = args.split(maxsplit=1)
        template_name = parts[0].lower()
        template_args = parts[1] if len(parts) > 1 else ""

        if template_name not in TEMPLATES:
            available = ", ".join(TEMPLATES.keys())
            return (
                f"❓ Unknown template: `{template_name}`\n\n"
                f"Available templates: {available}\n"
                f"Use `/templates` for details.",
                True
            )

        template = TEMPLATES[template_name]
        logger.debug(f"Delegating template '{template_name}' to agent with args: {template_args!r}")

        # Return None, False to delegate to agent
        # The agent will receive the original command text and process it
        return None, False

    def _get_example_prompts(self) -> str:
        """
        Get example prompts for new users.

        Returns:
            Formatted string with example prompts.
        """
        examples = [
            "What's the weather in London?",
            "Summarize this URL: https://example.com",
            "Help me write a Python function to parse JSON",
            "Search for the latest news on AI",
            "Set a reminder in 30 minutes to check my email",
        ]
        lines = ["**Try saying:**"]
        for example in examples:
            lines.append(f"• \"{example}\"")
        return "\n".join(lines)
