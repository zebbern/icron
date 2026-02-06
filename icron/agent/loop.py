"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

# Type hint for MCPManager - imported at runtime in initialize()
if TYPE_CHECKING:
    from icron.mcp.tool_adapter import MCPManager
    from icron.cron.service import CronService

from icron.bus.events import InboundMessage, OutboundMessage
from icron.bus.queue import MessageBus
from icron.providers.base import LLMProvider
from icron.agent.context import ContextBuilder
from icron.agent.tools.registry import ToolRegistry
from icron.agent.tools.filesystem import (
    ReadFileTool, WriteFileTool, EditFileTool, ListDirTool,
    RenameFileTool, MoveFileTool, CopyFileTool, CreateDirTool
)
from icron.agent.tools.search import GlobTool, GrepTool
from icron.agent.tools.shell import ExecTool
from icron.agent.tools.web import WebSearchTool, WebFetchTool
from icron.agent.tools.screenshot import ScreenshotTool
from icron.agent.tools.message import MessageTool
from icron.agent.tools.spawn import SpawnTool
from icron.agent.tools.memory_tools import RememberTool, RecallTool, NoteTodayTool
from icron.agent.tools.reminder_tools import ReminderTool, ListRemindersool, CancelReminderTool
from icron.agent.subagent import SubagentManager
from icron.agent.commands import CommandHandler
from icron.session.manager import SessionManager


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        cron_service: "CronService | None" = None,
    ):
        from icron.config.schema import ExecToolConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.mcp_servers = mcp_servers or {}
        self.cron_service = cron_service
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.commands = CommandHandler(session_manager=self.sessions)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
        )
        self.mcp_manager: "MCPManager | None" = None
        
        self._running = False
        self._initialized = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Use config setting for workspace restriction (default: False = no restriction)
        restrict = self.exec_config.restrict_to_workspace
        
        # File tools (with workspace security validation)
        self.tools.register(ReadFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(WriteFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(EditFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(ListDirTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        # Additional file tools with workspace security
        self.tools.register(RenameFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(MoveFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(CopyFileTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(CreateDirTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        
        # Shell tool
        import os
        shell_cwd = os.getenv("ICRON_SHELL_CWD")
        self.tools.register(ExecTool(
            working_dir=shell_cwd or str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=restrict,
        ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())

        # Screenshot tool
        self.tools.register(ScreenshotTool(
            workspace_path=str(self.workspace),
        ))

        # Search tools
        self.tools.register(GlobTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        self.tools.register(GrepTool(
            workspace=self.workspace,
            restrict_to_workspace=restrict,
        ))
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Memory tools
        self.tools.register(RememberTool(workspace=self.workspace))
        self.tools.register(RecallTool(workspace=self.workspace))
        self.tools.register(NoteTodayTool(workspace=self.workspace))
        
        # Reminder tools (cron-based)
        self._reminder_tool = ReminderTool(cron_service=self.cron_service)
        self._list_reminders_tool = ListRemindersool(cron_service=self.cron_service)
        self._cancel_reminder_tool = CancelReminderTool(cron_service=self.cron_service)
        self.tools.register(self._reminder_tool)
        self.tools.register(self._list_reminders_tool)
        self.tools.register(self._cancel_reminder_tool)
    
    async def initialize(self) -> None:
        """Initialize async components including MCP."""
        if self._initialized:
            return

        # Initialize MCP if configured
        if self.mcp_servers:
            try:
                # Import here to avoid circular imports and handle missing package
                from icron.mcp.tool_adapter import MCPManager

                self.mcp_manager = MCPManager()
                await self.mcp_manager.initialize(self.mcp_servers)

                # Register MCP tools
                for tool in self.mcp_manager.get_tools():
                    self.tools.register(tool)

                logger.info(f"MCP initialized with {len(self.mcp_manager.get_tools())} tools")
            except ImportError:
                logger.warning("MCP support not available. Install with: pip install icron-ai[mcp]")
            except Exception as e:
                logger.error(f"Failed to initialize MCP: {e}")
                # Continue without MCP

        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown async components including MCP."""
        if self.mcp_manager:
            try:
                await self.mcp_manager.close()
            except Exception as e:
                logger.error(f"Error closing MCP manager: {e}")
            self.mcp_manager = None
        self._initialized = False

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        # Initialize async components (MCP, etc.)
        await self.initialize()
        
        self._running = True
        logger.info("Agent loop started")
        
        try:
            while self._running:
                try:
                    # Wait for next message
                    msg = await asyncio.wait_for(
                        self.bus.consume_inbound(),
                        timeout=1.0
                    )
                    
                    # Process it
                    try:
                        response = await self._process_message(msg)
                        if response:
                            await self.bus.publish_outbound(response)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        # Send error response
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=f"Sorry, I encountered an error: {str(e)}"
                        ))
                except asyncio.TimeoutError:
                    continue
        finally:
            # Cleanup async components
            await self.shutdown()
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        # Handle slash commands
        if self.commands.is_command(msg.content):
            response, handled = await self.commands.handle(
                text=msg.content,
                session_key=msg.session_key,
                channel=msg.channel,
                chat_id=msg.chat_id
            )
            if handled:
                if response:
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=response
                    )
                return None
            # If not handled, continue with modified content (for delegation)
            if response:
                msg = InboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    sender_id=msg.sender_id,
                    content=response,
                    media=msg.media
                )

        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        # Update reminder tool context
        if hasattr(self, '_reminder_tool'):
            self._reminder_tool.set_context(msg.channel, msg.chat_id)
        
        # Build initial messages (use get_history for LLM-formatted messages with token trimming)
        max_tokens = self.exec_config.max_context_tokens if self.exec_config else 100000
        messages = self.context.build_messages(
            history=session.get_history(max_tokens=max_tokens),
            current_message=msg.content,
            media=msg.media if msg.media else None,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # DEBUG: Log messages before sending to provider
            logger.debug(f"[DEBUG] Iteration {iteration}: Messages BEFORE provider.chat():")
            for i, m in enumerate(messages):
                role = m.get('role', 'unknown')
                tool_calls = m.get('tool_calls', [])
                tool_call_id = m.get('tool_call_id', None)
                content_preview = str(m.get('content', ''))[:100]
                logger.debug(f"  [{i}] role={role}, tool_calls={len(tool_calls) if tool_calls else 0}, tool_call_id={tool_call_id}, content={content_preview}...")
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # DEBUG: Log messages after adding assistant message
                logger.debug(f"[DEBUG] Messages AFTER add_assistant_message:")
                for i, m in enumerate(messages):
                    role = m.get('role', 'unknown')
                    tool_calls = m.get('tool_calls', [])
                    tool_call_id = m.get('tool_call_id', None)
                    logger.debug(f"  [{i}] role={role}, tool_calls={len(tool_calls) if tool_calls else 0}, tool_call_id={tool_call_id}")
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
                    
                    # DEBUG: Log messages after adding tool result
                    logger.debug(f"[DEBUG] Messages AFTER add_tool_result for {tool_call.name} (id={tool_call.id}):")
                    for i, m in enumerate(messages):
                        role = m.get('role', 'unknown')
                        tool_calls = m.get('tool_calls', [])
                        tool_call_id = m.get('tool_call_id', None)
                        logger.debug(f"  [{i}] role={role}, tool_calls={len(tool_calls) if tool_calls else 0}, tool_call_id={tool_call_id}")
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        # Fallback for empty/whitespace-only responses (fixes "Message text is empty" error)
        if not final_content.strip():
            final_content = "Done."

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content (with token trimming)
        max_tokens = self.exec_config.max_context_tokens if self.exec_config else 100000
        messages = self.context.build_messages(
            history=session.get_history(max_tokens=max_tokens),
            current_message=msg.content
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."

        # Fallback for empty/whitespace-only responses (fixes "Message text is empty" error)
        if not final_content.strip():
            final_content = "Done."

        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        Process a message directly (for CLI usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
