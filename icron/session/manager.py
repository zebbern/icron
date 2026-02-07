"""Session management for conversation history."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from icron.utils.helpers import ensure_dir, safe_filename
from icron.utils.tokens import count_message_tokens


@dataclass
class Session:
    """
    A conversation session.
    
    Stores messages in JSONL format for easy reading and persistence.
    """
    
    key: str  # channel:chat_id
    name: str | None = None  # Human-readable display name
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        """Get the display name for this session."""
        return self.name or self.key
    
    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()
    
    def get_history(self, max_messages: int = 50, max_tokens: int | None = None) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.
        
        Args:
            max_messages: Maximum messages to return.
            max_tokens: Optional token limit. If set, trims oldest messages
                       to stay within budget while keeping recent context.
        
        Returns:
            List of messages in LLM format.
        """
        # Get recent messages (by count limit first)
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        # Convert to LLM format
        formatted = [{"role": m["role"], "content": m["content"]} for m in recent]
        
        # If no token limit, return all
        if max_tokens is None:
            return formatted
        
        # Trim by tokens (keep newest messages, remove oldest)
        result = []
        total_tokens = 0
        trimmed_count = 0
        
        for msg in reversed(formatted):
            tokens = count_message_tokens(msg)
            if total_tokens + tokens > max_tokens and result:
                # Would exceed budget, stop here
                trimmed_count = len(formatted) - len(result)
                break
            result.append(msg)
            total_tokens += tokens
        
        # Log if trimming occurred
        if trimmed_count > 0:
            logger.debug(f"Trimmed {trimmed_count} old messages from history ({total_tokens} tokens kept)")
        
        # Restore chronological order
        return list(reversed(result))
    
    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.
    
    Sessions are stored as JSONL files in the sessions directory.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".icron" / "sessions")
        self._cache: dict[str, Session] = {}
    
    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"
    
    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.
        
        Args:
            key: Session key (usually channel:chat_id).
        
        Returns:
            The session.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = Session(key=key)
        
        self._cache[key] = session
        return session
    
    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)
        
        if not path.exists():
            return None
        
        try:
            messages = []
            metadata = {}
            created_at = None
            
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)
            
            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None
    
    def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)
        
        with open(path, "w", encoding="utf-8") as f:
            # Write metadata first
            metadata_line = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata
            }
            f.write(json.dumps(metadata_line) + "\n")
            
            # Write messages
            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")
        
        self._cache[session.key] = session
    
    def delete(self, key: str) -> bool:
        """
        Delete a session.
        
        Args:
            key: Session key.
        
        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)
        
        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions with metadata.
        
        Returns:
            List of session info dicts with key, created_at, updated_at, message_count.
        """
        sessions = []
        
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                message_count = 0
                metadata_info = {}
                
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("_type") == "metadata":
                            metadata_info = data
                        else:
                            message_count += 1
                
                if metadata_info:
                    sessions.append({
                        "key": path.stem.replace("_", ":", 1),
                        "name": metadata_info.get("metadata", {}).get("name"),
                        "created_at": metadata_info.get("created_at"),
                        "updated_at": metadata_info.get("updated_at"),
                        "message_count": message_count,
                        "path": str(path)
                    })
            except Exception:
                continue
        
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def rename_session(self, old_key: str, new_key: str) -> bool:
        """
        Rename a session by changing its key.
        
        Args:
            old_key: Current session key.
            new_key: New session key.
        
        Returns:
            True if renamed successfully, False otherwise.
        """
        old_path = self._get_session_path(old_key)
        new_path = self._get_session_path(new_key)
        
        if not old_path.exists():
            logger.warning(f"Session {old_key} not found for rename")
            return False
        
        if new_path.exists():
            logger.warning(f"Cannot rename: session {new_key} already exists")
            return False
        
        try:
            # Load the session
            session = self.get_or_create(old_key)
            
            # Update the key
            session.key = new_key
            session.updated_at = datetime.now()
            
            # Save to new path
            self.save(session)
            
            # Delete old file
            old_path.unlink()
            
            # Update cache
            self._cache.pop(old_key, None)
            self._cache[new_key] = session
            
            logger.info(f"Renamed session {old_key} to {new_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename session {old_key} to {new_key}: {e}")
            return False
    
    def delete_session(self, key: str) -> bool:
        """
        Delete a session from disk and cache.
        
        Args:
            key: Session key.
        
        Returns:
            True if deleted, False if not found.
        """
        return self.delete(key)
    
    def get_session_info(self, key: str) -> dict[str, Any] | None:
        """
        Get metadata about a session without loading all messages.
        
        Args:
            key: Session key.
        
        Returns:
            Dict with session info or None if not found.
        """
        path = self._get_session_path(key)
        
        if not path.exists():
            return None
        
        try:
            message_count = 0
            metadata_info = {}
            first_message_at = None
            last_message_at = None
            
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata_info = data
                    else:
                        message_count += 1
                        timestamp = data.get("timestamp")
                        if timestamp:
                            if first_message_at is None:
                                first_message_at = timestamp
                            last_message_at = timestamp
            
            return {
                "key": key,
                "name": metadata_info.get("metadata", {}).get("name"),
                "created_at": metadata_info.get("created_at"),
                "updated_at": metadata_info.get("updated_at"),
                "message_count": message_count,
                "first_message_at": first_message_at,
                "last_message_at": last_message_at,
                "metadata": metadata_info.get("metadata", {}),
                "path": str(path)
            }
        except Exception as e:
            logger.warning(f"Failed to get session info for {key}: {e}")
            return None
