"""Semantic memory tools for the agent to save and recall information."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from icron.agent.tools.base import Tool
from icron.memory.store import MemoryStore
from icron.memory.index import VectorIndex, SearchResult
from icron.memory.embeddings import get_embedding_provider, EmbeddingProvider

logger = logging.getLogger(__name__)


class MemorySearchTool(Tool):
    """
    Semantic search through memories.
    
    Uses vector embeddings to find relevant snippets from MEMORY.md
    and daily logs based on semantic similarity.
    """
    
    def __init__(
        self,
        workspace: Path,
        vector_index: VectorIndex | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize the memory search tool.
        
        Args:
            workspace: Path to the workspace directory.
            vector_index: Optional pre-configured VectorIndex instance.
            embedding_provider: Optional pre-configured embedding provider.
        """
        self.workspace = workspace
        self._vector_index = vector_index
        self._embedding_provider = embedding_provider
    
    @property
    def name(self) -> str:
        return "memory_search"
    
    @property
    def description(self) -> str:
        return (
            "Search your memories semantically. Returns relevant snippets from "
            "MEMORY.md and daily logs based on meaning, not just keywords."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant memories"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Search memories semantically."""
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 5)
        
        if not query:
            return "Error: 'query' is required"
        
        # Get vector index and embedding provider from context or instance
        vector_index = kwargs.get("vector_index") or self._vector_index
        embedding_provider = kwargs.get("embedding_provider") or self._embedding_provider
        
        if not vector_index:
            # Initialize with default path if not provided
            db_path = self.workspace / "memory" / ".vector_index.db"
            vector_index = VectorIndex(db_path)
        
        if not embedding_provider:
            try:
                embedding_provider = await get_embedding_provider()
            except ValueError as e:
                logger.warning("Could not initialize embedding provider: %s", e)
                return f"Error: No embedding provider available - {e}"
        
        try:
            # Generate embedding for the query
            query_embedding = await embedding_provider.embed(query)
            
            # Search the vector index
            results: list[SearchResult] = vector_index.search(
                query_embedding=query_embedding,
                limit=limit,
            )
            
            if not results:
                return "📭 No relevant memories found for your query."
            
            # Format results
            output_lines = [f"🔍 **Found {len(results)} relevant memories:**\n"]
            
            for i, result in enumerate(results, 1):
                file_display = Path(result.file_path).name
                line_info = ""
                if result.start_line and result.end_line:
                    line_info = f" (lines {result.start_line}-{result.end_line})"
                
                # Truncate long text for display
                text_preview = result.text[:300]
                if len(result.text) > 300:
                    text_preview += "..."
                
                output_lines.append(
                    f"**{i}. {file_display}{line_info}** (score: {result.score:.2f})\n"
                    f"{text_preview}\n"
                )
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.exception("Error during memory search")
            return f"Error searching memories: {e}"


class MemoryWriteTool(Tool):
    """
    Save information to memory.
    
    Writes content to either the permanent MEMORY.md file or
    the daily log for today.
    """
    
    def __init__(
        self,
        workspace: Path,
        memory_store: MemoryStore | None = None,
        vector_index: VectorIndex | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize the memory write tool.
        
        Args:
            workspace: Path to the workspace directory.
            memory_store: Optional pre-configured MemoryStore instance.
            vector_index: Optional pre-configured VectorIndex for indexing.
            embedding_provider: Optional pre-configured embedding provider.
        """
        self.workspace = workspace
        self._memory_store = memory_store
        self._vector_index = vector_index
        self._embedding_provider = embedding_provider
    
    @property
    def name(self) -> str:
        return "memory_write"
    
    @property
    def description(self) -> str:
        return (
            "Save important information to memory. Use for facts, preferences, "
            "and things to remember long-term. Write to 'daily' for temporal notes "
            "or 'permanent' for long-term memories."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to save to memory"
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["daily", "permanent"],
                    "description": "Type of memory: 'daily' for today's log, 'permanent' for MEMORY.md"
                }
            },
            "required": ["content"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Save content to memory."""
        content = kwargs.get("content", "")
        memory_type = kwargs.get("memory_type", "daily")
        
        if not content:
            return "Error: 'content' is required"
        
        if memory_type not in ("daily", "permanent"):
            return "Error: 'memory_type' must be 'daily' or 'permanent'"
        
        # Get memory store from context or create new one
        memory_store = kwargs.get("memory_store") or self._memory_store
        if not memory_store:
            memory_store = MemoryStore(self.workspace)
        
        try:
            timestamp = datetime.now().strftime("%H:%M")
            
            if memory_type == "daily":
                # Add timestamped entry to today's log
                entry = f"- [{timestamp}] {content}"
                memory_store.append_daily_log(entry)
                date_str = datetime.now().strftime("%Y-%m-%d")
                file_path = f"memory/{date_str}.md"
                result_msg = f"📓 Saved to today's log ({date_str})"
            else:
                # Add to permanent MEMORY.md
                date_str = datetime.now().strftime("%Y-%m-%d")
                entry = f"\n## {date_str}\n\n{content}\n"
                memory_store.append_memory(entry)
                file_path = "MEMORY.md"
                result_msg = "📝 Saved to permanent memory (MEMORY.md)"
            
            # Optionally index the content for semantic search
            vector_index = kwargs.get("vector_index") or self._vector_index
            embedding_provider = kwargs.get("embedding_provider") or self._embedding_provider
            
            if vector_index and embedding_provider:
                try:
                    embedding = await embedding_provider.embed(content)
                    vector_index.add_chunk(
                        file_path=file_path,
                        text=content,
                        embedding=embedding,
                    )
                    result_msg += " (indexed for search)"
                except Exception as e:
                    logger.warning("Failed to index memory content: %s", e)
            
            return result_msg
            
        except Exception as e:
            logger.exception("Error writing to memory")
            return f"Error saving to memory: {e}"


class MemoryGetTool(Tool):
    """
    Read content from a specific memory file.
    
    Retrieves content from MEMORY.md or dated daily log files.
    """
    
    def __init__(
        self,
        workspace: Path,
        memory_store: MemoryStore | None = None,
    ) -> None:
        """Initialize the memory get tool.
        
        Args:
            workspace: Path to the workspace directory.
            memory_store: Optional pre-configured MemoryStore instance.
        """
        self.workspace = workspace
        self._memory_store = memory_store
    
    @property
    def name(self) -> str:
        return "memory_get"
    
    @property
    def description(self) -> str:
        return (
            "Read content from a specific memory file. Provide a path like "
            "'MEMORY.md' or 'memory/2024-01-15.md' to read that file."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the memory file (e.g., 'MEMORY.md' or 'memory/2024-01-15.md')"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: start line number (1-indexed)",
                    "minimum": 1
                },
                "num_lines": {
                    "type": "integer",
                    "description": "Optional: number of lines to read",
                    "minimum": 1
                }
            },
            "required": ["file_path"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Read content from a memory file."""
        file_path_str = kwargs.get("file_path", "")
        start_line = kwargs.get("start_line")
        num_lines = kwargs.get("num_lines")
        
        if not file_path_str:
            return "Error: 'file_path' is required"
        
        # Resolve the file path relative to workspace
        file_path = self.workspace / file_path_str
        
        # Security check: ensure the path is within workspace
        try:
            file_path = file_path.resolve()
            workspace_resolved = self.workspace.resolve()
            if not file_path.is_relative_to(workspace_resolved):
                return "Error: File path must be within the workspace"
        except Exception:
            return "Error: Invalid file path"
        
        if not file_path.exists():
            return f"📭 File not found: {file_path_str}"
        
        if not file_path.is_file():
            return f"Error: '{file_path_str}' is not a file"
        
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            # Apply line filtering if specified
            if start_line is not None:
                start_idx = start_line - 1  # Convert to 0-indexed
                if num_lines is not None:
                    end_idx = start_idx + num_lines
                    lines = lines[start_idx:end_idx]
                else:
                    lines = lines[start_idx:]
                content = "\n".join(lines)
            
            if not content.strip():
                return f"📭 File is empty: {file_path_str}"
            
            # Add file info header
            total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
            header = f"📄 **{file_path_str}** ({total_lines} lines total)\n\n"
            
            return header + content
            
        except Exception as e:
            logger.exception("Error reading memory file")
            return f"Error reading file: {e}"


class MemoryListTool(Tool):
    """
    List all memory files.
    
    Returns a list of available memory files including MEMORY.md
    and all daily logs.
    """
    
    def __init__(
        self,
        workspace: Path,
        memory_store: MemoryStore | None = None,
    ) -> None:
        """Initialize the memory list tool.
        
        Args:
            workspace: Path to the workspace directory.
            memory_store: Optional pre-configured MemoryStore instance.
        """
        self.workspace = workspace
        self._memory_store = memory_store
    
    @property
    def name(self) -> str:
        return "memory_list"
    
    @property
    def description(self) -> str:
        return "List all memory files including MEMORY.md and daily logs."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """List all memory files."""
        memory_store = kwargs.get("memory_store") or self._memory_store
        if not memory_store:
            memory_store = MemoryStore(self.workspace)
        
        try:
            files = memory_store.list_memory_files()
            
            if not files:
                return "📭 No memory files found."
            
            output_lines = [f"📚 **Memory Files ({len(files)} total):**\n"]
            
            for file_path in files:
                # Get relative path from workspace
                try:
                    rel_path = file_path.relative_to(self.workspace)
                except ValueError:
                    rel_path = file_path.name
                
                # Get file size
                size = file_path.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                
                # Get modified time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
                
                output_lines.append(f"- **{rel_path}** ({size_str}, modified: {mtime_str})")
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.exception("Error listing memory files")
            return f"Error listing memory files: {e}"


# Export all tools
__all__ = [
    "MemorySearchTool",
    "MemoryWriteTool",
    "MemoryGetTool",
    "MemoryListTool",
]
