"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

# Default max context tokens when exec_config is not available
DEFAULT_MAX_CONTEXT_TOKENS = 100_000

# Type hint for MCPManager - imported at runtime in initialize()
if TYPE_CHECKING:
    from icron.mcp.tool_adapter import MCPManager
    from icron.cron.service import CronService

# Memory system imports
from icron.memory.store import MemoryStore
from icron.memory.index import VectorIndex
from icron.memory.embeddings import get_embedding_provider, EmbeddingProvider

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
from icron.agent.tools.memory_tools import (
    MemorySearchTool,
    MemoryWriteTool,
    MemoryGetTool,
    MemoryListTool,
)
from icron.agent.tools.reminder_tools import ReminderTool, ListRemindersTool, CancelReminderTool
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
        config: "Config | None" = None,
    ):
        from icron.config.schema import ExecToolConfig, Config
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.mcp_servers = mcp_servers or {}
        self.cron_service = cron_service
        self.config = config  # Full config for collaboration
        
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
        
        # Memory system components (initialized async in initialize())
        self.memory_store: MemoryStore | None = None
        self.memory_index: VectorIndex | None = None
        self.embedding_provider: EmbeddingProvider | None = None
        
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
        
        # Semantic memory tools
        self.tools.register(MemorySearchTool(workspace=self.workspace))
        self.tools.register(MemoryWriteTool(workspace=self.workspace))
        self.tools.register(MemoryGetTool(workspace=self.workspace))
        self.tools.register(MemoryListTool(workspace=self.workspace))
        
        # Reminder tools (cron-based)
        self._reminder_tool = ReminderTool(cron_service=self.cron_service)
        self._list_reminders_tool = ListRemindersTool(cron_service=self.cron_service)
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

        # Initialize memory system
        await self._init_memory()

        self._initialized = True

    async def _init_memory(self) -> None:
        """Initialize the memory system components."""
        try:
            # Check if memory is enabled (default: True)
            memory_enabled = getattr(self.exec_config, 'memory_enabled', True)
            if not memory_enabled:
                logger.info("Memory system disabled by config")
                return

            # Create MemoryStore
            self.memory_store = MemoryStore(self.workspace)
            logger.debug(f"MemoryStore initialized at {self.workspace}")

            # Get embedding provider
            try:
                self.embedding_provider = await get_embedding_provider()
                logger.debug(f"Embedding provider initialized (dimension={self.embedding_provider.dimension})")
            except ValueError as e:
                logger.warning(f"Could not initialize embedding provider: {e}")
                logger.info("Memory system will work without semantic search")
                return

            # Create VectorIndex
            db_path = self.workspace / "memory" / ".vector_index.db"
            self.memory_index = VectorIndex(db_path, dimension=self.embedding_provider.dimension)
            logger.debug(f"VectorIndex initialized at {db_path}")

            # Index existing memory files in background
            asyncio.create_task(self._index_memory_files())
            logger.info("Memory system initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize memory system: {e}")
            # Continue without memory - tools will handle gracefully

    async def _index_memory_files(self) -> None:
        """Index all memory markdown files for semantic search."""
        if not self.memory_index or not self.embedding_provider:
            return

        try:
            memory_dir = self.workspace / "memory"
            if not memory_dir.exists():
                return

            # Find all markdown files in memory directory
            md_files = list(memory_dir.glob("**/*.md"))
            
            # Also include MEMORY.md from workspace root
            root_memory = self.workspace / "MEMORY.md"
            if root_memory.exists():
                md_files.append(root_memory)

            indexed_count = 0
            for md_file in md_files:
                # Skip hidden files and index database
                if md_file.name.startswith("."):
                    continue

                try:
                    content = md_file.read_text(encoding="utf-8")
                    if not content.strip():
                        continue

                    # Split content into chunks (by paragraphs or sections)
                    chunks = self._chunk_content(content, str(md_file))
                    
                    for chunk_text, start_line, end_line in chunks:
                        # Generate embedding
                        embedding = await self.embedding_provider.embed(chunk_text)
                        
                        # Store in index
                        self.memory_index.add_chunk(
                            file_path=str(md_file.relative_to(self.workspace)),
                            text=chunk_text,
                            embedding=embedding,
                            start_line=start_line,
                            end_line=end_line,
                        )
                        indexed_count += 1

                except Exception as e:
                    logger.warning(f"Failed to index {md_file}: {e}")

            logger.info(f"Indexed {indexed_count} chunks from {len(md_files)} memory files")

        except Exception as e:
            logger.error(f"Error during memory indexing: {e}")

    def _chunk_content(self, content: str, file_path: str) -> list[tuple[str, int, int]]:
        """Split content into indexable chunks.
        
        Args:
            content: The text content to chunk.
            file_path: Path to the file (for logging).
            
        Returns:
            List of (chunk_text, start_line, end_line) tuples.
        """
        chunks = []
        lines = content.split("\n")
        
        # Simple chunking: split by double newlines (paragraphs) or headers
        current_chunk = []
        chunk_start = 1
        
        for i, line in enumerate(lines, start=1):
            # Start new chunk on headers or after empty lines following content
            if line.startswith("#") and current_chunk:
                chunk_text = "\n".join(current_chunk).strip()
                if chunk_text and len(chunk_text) > 20:  # Skip tiny chunks
                    chunks.append((chunk_text, chunk_start, i - 1))
                current_chunk = [line]
                chunk_start = i
            else:
                current_chunk.append(line)
            
            # Also chunk if current chunk gets too large (>500 chars)
            chunk_text = "\n".join(current_chunk)
            if len(chunk_text) > 500:
                if chunk_text.strip() and len(chunk_text.strip()) > 20:
                    chunks.append((chunk_text.strip(), chunk_start, i))
                current_chunk = []
                chunk_start = i + 1
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk).strip()
            if chunk_text and len(chunk_text) > 20:
                chunks.append((chunk_text, chunk_start, len(lines)))
        
        return chunks

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

        # Handle /collab command - multi-model collaboration
        if msg.content.strip().lower().startswith("/collab"):
            return await self._handle_collab(msg)

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
        max_tokens = self.exec_config.max_context_tokens if self.exec_config else DEFAULT_MAX_CONTEXT_TOKENS
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
                logger.debug("[DEBUG] Messages AFTER add_assistant_message:")
                for i, m in enumerate(messages):
                    role = m.get('role', 'unknown')
                    tool_calls = m.get('tool_calls', [])
                    tool_call_id = m.get('tool_call_id', None)
                    logger.debug(f"  [{i}] role={role}, tool_calls={len(tool_calls) if tool_calls else 0}, tool_call_id={tool_call_id}")
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    # Pass memory components to tools that need them
                    tool_kwargs = dict(tool_call.arguments)
                    tool_kwargs["vector_index"] = self.memory_index
                    tool_kwargs["embedding_provider"] = self.embedding_provider
                    result = await self.tools.execute(tool_call.name, tool_kwargs)
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
        max_tokens = self.exec_config.max_context_tokens if self.exec_config else DEFAULT_MAX_CONTEXT_TOKENS
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
                    # Pass memory components to tools that need them
                    tool_kwargs = dict(tool_call.arguments)
                    tool_kwargs["vector_index"] = self.memory_index
                    tool_kwargs["embedding_provider"] = self.embedding_provider
                    result = await self.tools.execute(tool_call.name, tool_kwargs)
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

    async def _handle_collab(self, msg: InboundMessage) -> OutboundMessage:
        """
        Handle /collab command - multi-model collaboration.
        
        Uses configured LLM providers to have an iterative dialogue,
        questioning and building on each other's ideas until consensus.
        """
        from icron.agent.collaborate import CollaborationService
        
        # Extract task from command
        content = msg.content.strip()
        if content.lower() == "/collab":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="**Multi-Model Collaboration**\n\n"
                        "Usage: `/collab <task>`\n\n"
                        "Example: `/collab Design a REST API authentication system`\n\n"
                        "Models will discuss back-and-forth until they agree on the best solution."
            )
        
        # Get task (everything after /collab)
        task = content[7:].strip()  # Remove "/collab " prefix
        
        if not self.config:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="❌ Collaboration requires config. This is a bug - please report it."
            )
        
        # Create collaboration service
        collab_service = CollaborationService(self.config)
        provider_count = collab_service.get_provider_count()
        
        if provider_count < 2:
            providers = collab_service.get_configured_providers()
            provider_names = [p.name for p in providers] if providers else ["none"]
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"❌ **Not Enough Providers**\n\n"
                        f"Multi-model collaboration requires at least 2 configured providers.\n\n"
                        f"Currently configured: {', '.join(provider_names)}\n\n"
                        f"Add more API keys in your config to enable collaboration."
            )
        
        # Send initial message
        providers = collab_service.get_configured_providers()
        provider_list = ", ".join([f"{p.emoji} {p.name}" for p in providers[:2]])
        
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"🤝 **Starting Collaborative Dialogue**\n\n"
                    f"**Task:** {task}\n\n"
                    f"**Participants:** {provider_list}\n\n"
                    f"*Models will discuss until reaching consensus...*"
        ))
        
        # Callback for progress updates
        async def progress_callback(provider_name: str, phase: str, content: str) -> None:
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content
            ))
        
        # Run collaboration
        result = await collab_service.collaborate(task, callback=progress_callback)
        
        if not result.success:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"❌ **Collaboration Failed**\n\n{result.error}"
            )
        
        # Return summary
        consensus_text = "✅ Consensus reached!" if result.consensus_reached else f"⏱️ Max rounds ({result.rounds_completed}) completed"
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"🏁 **Collaboration Complete**\n\n"
                    f"**Rounds:** {result.rounds_completed}\n"
                    f"**Status:** {consensus_text}\n"
                    f"**Models:** {', '.join(result.providers_used)}"
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
