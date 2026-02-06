"""Memory store for managing Markdown-based memory files (OpenClaw-style)."""

from datetime import datetime
from pathlib import Path


class MemoryStore:
    """
    Manages MEMORY.md and daily logs for persistent agent memory.

    File structure:
        - workspace/MEMORY.md - Long-term curated memory
        - workspace/memory/YYYY-MM-DD.md - Daily append-only notes
    """

    def __init__(self, workspace_path: Path) -> None:
        """
        Initialize the memory store.

        Args:
            workspace_path: Path to the workspace directory.
        """
        self.workspace = Path(workspace_path)
        self.memory_dir = self.workspace / "memory"
        self.memory_file = self.workspace / "MEMORY.md"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _get_daily_log_path(self, date: datetime | None = None) -> Path:
        """
        Get the path to a daily log file.

        Args:
            date: Date for the log file. Defaults to today.

        Returns:
            Path to the daily log file.
        """
        target_date = date or datetime.now()
        date_str = target_date.strftime("%Y-%m-%d")
        return self.memory_dir / f"{date_str}.md"

    def read_memory(self) -> str:
        """
        Read the long-term MEMORY.md content.

        Returns:
            Contents of MEMORY.md, or empty string if file doesn't exist.
        """
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_memory(self, content: str) -> None:
        """
        Write content to MEMORY.md (overwrites existing content).

        Args:
            content: Content to write to MEMORY.md.
        """
        self._ensure_directories()
        self.memory_file.write_text(content, encoding="utf-8")

    def append_memory(self, content: str) -> None:
        """
        Append content to MEMORY.md.

        Args:
            content: Content to append.
        """
        existing = self.read_memory()
        separator = "\n\n" if existing else ""
        self.write_memory(existing + separator + content)

    def read_daily_log(self, date: datetime | None = None) -> str:
        """
        Read a daily log file.

        Args:
            date: Date of the log to read. Defaults to today.

        Returns:
            Contents of the daily log, or empty string if file doesn't exist.
        """
        log_path = self._get_daily_log_path(date)
        if log_path.exists():
            return log_path.read_text(encoding="utf-8")
        return ""

    def append_daily_log(self, content: str, date: datetime | None = None) -> None:
        """
        Append content to a daily log file.

        Creates the file with a header if it doesn't exist.

        Args:
            content: Content to append.
            date: Date of the log. Defaults to today.
        """
        self._ensure_directories()
        log_path = self._get_daily_log_path(date)
        target_date = date or datetime.now()
        date_str = target_date.strftime("%Y-%m-%d")

        if log_path.exists():
            existing = log_path.read_text(encoding="utf-8")
            new_content = existing.rstrip() + "\n\n" + content
        else:
            header = f"# {date_str}\n\n"
            new_content = header + content

        log_path.write_text(new_content, encoding="utf-8")

    def list_memory_files(self) -> list[Path]:
        """
        List all memory files (MEMORY.md and daily logs).

        Returns:
            List of paths to memory files, sorted by name (newest daily logs first).
        """
        files: list[Path] = []

        if self.memory_file.exists():
            files.append(self.memory_file)

        if self.memory_dir.exists():
            daily_logs = sorted(
                self.memory_dir.glob("????-??-??.md"),
                reverse=True,
            )
            files.extend(daily_logs)

        return files

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 400,
        overlap: int = 80,
        file_name: str = "",
    ) -> list[dict]:
        """
        Split text into overlapping chunks for embedding.

        Args:
            text: Text to chunk.
            chunk_size: Target tokens per chunk (approximated as ~4 chars/token).
            overlap: Overlap tokens between chunks.
            file_name: Source file name for metadata.

        Returns:
            List of chunk dicts with keys: text, file, start_line, end_line.
        """
        if not text.strip():
            return []

        # Approximate chars per token (~4 chars)
        chars_per_token = 4
        chunk_chars = chunk_size * chars_per_token
        overlap_chars = overlap * chars_per_token

        lines = text.splitlines(keepends=True)
        chunks: list[dict] = []

        current_chunk: list[str] = []
        current_chars = 0
        chunk_start_line = 1
        line_num = 1

        for line in lines:
            line_len = len(line)

            # If adding this line exceeds chunk size and we have content
            if current_chars + line_len > chunk_chars and current_chunk:
                chunk_text = "".join(current_chunk)
                chunks.append({
                    "text": chunk_text.strip(),
                    "file": file_name,
                    "start_line": chunk_start_line,
                    "end_line": line_num - 1,
                })

                # Calculate overlap: find lines to keep for overlap
                overlap_lines: list[str] = []
                overlap_len = 0
                for prev_line in reversed(current_chunk):
                    if overlap_len + len(prev_line) > overlap_chars:
                        break
                    overlap_lines.insert(0, prev_line)
                    overlap_len += len(prev_line)

                current_chunk = overlap_lines
                current_chars = overlap_len
                chunk_start_line = line_num - len(overlap_lines)

            current_chunk.append(line)
            current_chars += line_len
            line_num += 1

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunks.append({
                "text": chunk_text.strip(),
                "file": file_name,
                "start_line": chunk_start_line,
                "end_line": line_num - 1,
            })

        return chunks

    def chunk_file(self, file_path: Path, chunk_size: int = 400, overlap: int = 80) -> list[dict]:
        """
        Chunk a memory file for embedding.

        Args:
            file_path: Path to the file to chunk.
            chunk_size: Target tokens per chunk.
            overlap: Overlap tokens between chunks.

        Returns:
            List of chunk dicts with text, file, start_line, end_line.
        """
        if not file_path.exists():
            return []

        text = file_path.read_text(encoding="utf-8")
        return self.chunk_text(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
            file_name=str(file_path.relative_to(self.workspace)),
        )

    def chunk_all_memory(self, chunk_size: int = 400, overlap: int = 80) -> list[dict]:
        """
        Chunk all memory files for embedding.

        Args:
            chunk_size: Target tokens per chunk.
            overlap: Overlap tokens between chunks.

        Returns:
            Combined list of chunks from all memory files.
        """
        all_chunks: list[dict] = []
        for file_path in self.list_memory_files():
            chunks = self.chunk_file(file_path, chunk_size=chunk_size, overlap=overlap)
            all_chunks.extend(chunks)
        return all_chunks
