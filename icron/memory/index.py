"""Vector index module using sqlite-vec for semantic search.

Provides vector storage and hybrid search (vector + BM25) with automatic
fallback to pure Python cosine similarity if sqlite-vec is unavailable.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a vector or hybrid search query."""

    file_path: str
    text: str
    start_line: int
    end_line: int
    score: float


class VectorIndex:
    """Vector index using sqlite-vec for semantic search.

    Uses sqlite-vec extension for efficient vector operations when available,
    falling back to pure Python cosine similarity otherwise. Supports hybrid
    search combining vector similarity with BM25 full-text search.

    Attributes:
        db_path: Path to the SQLite database file.
        dimension: Dimensionality of embedding vectors.
        has_sqlite_vec: Whether sqlite-vec extension is available.
    """

    def __init__(self, db_path: Path, dimension: int = 1536) -> None:
        """Initialize the vector index.

        Args:
            db_path: Path to the SQLite database file.
            dimension: Dimensionality of embedding vectors (default: 1536 for OpenAI).
        """
        self.db_path = Path(db_path)
        self.dimension = dimension
        self.has_sqlite_vec = False

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database and check for sqlite-vec
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Yields:
            SQLite connection with row factory enabled.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Try to load sqlite-vec extension if we know it's available
        if self.has_sqlite_vec:
            try:
                conn.enable_load_extension(True)
                conn.load_extension("vec0")
            except (sqlite3.OperationalError, AttributeError):
                pass

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _try_load_sqlite_vec(self, conn: sqlite3.Connection) -> bool:
        """Attempt to load the sqlite-vec extension.

        Args:
            conn: Active SQLite connection.

        Returns:
            True if sqlite-vec was loaded successfully.
        """
        try:
            conn.enable_load_extension(True)
            conn.load_extension("vec0")
            logger.info("sqlite-vec extension loaded successfully")
            return True
        except (sqlite3.OperationalError, AttributeError) as e:
            logger.warning(
                "sqlite-vec not available, using Python fallback: %s", e
            )
            return False

    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            # Check for sqlite-vec availability
            self.has_sqlite_vec = self._try_load_sqlite_vec(conn)

            # Create main chunks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    text TEXT NOT NULL,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on file_path for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_file_path 
                ON chunks(file_path)
            """)

            # Create sqlite-vec virtual table if available
            if self.has_sqlite_vec:
                try:
                    conn.execute(f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                            id INTEGER PRIMARY KEY,
                            embedding FLOAT[{self.dimension}]
                        )
                    """)
                    logger.info(
                        "Created vec_chunks table with dimension %d",
                        self.dimension,
                    )
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to create vec_chunks table: %s", e)
                    self.has_sqlite_vec = False

            # Create FTS5 virtual table for BM25 search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                    text,
                    content='chunks',
                    content_rowid='id'
                )
            """)

            # Create triggers to keep FTS index in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO fts_chunks(rowid, text) VALUES (new.id, new.text);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO fts_chunks(fts_chunks, rowid, text) 
                    VALUES('delete', old.id, old.text);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                    INSERT INTO fts_chunks(fts_chunks, rowid, text) 
                    VALUES('delete', old.id, old.text);
                    INSERT INTO fts_chunks(rowid, text) VALUES (new.id, new.text);
                END
            """)

            conn.commit()
            mode = "sqlite-vec" if self.has_sqlite_vec else "Python fallback"
            logger.info("Vector index initialized with %s mode", mode)

        finally:
            conn.close()

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        """Serialize embedding to binary format.

        Args:
            embedding: List of float values.

        Returns:
            Binary representation of the embedding.
        """
        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, data: bytes) -> list[float]:
        """Deserialize embedding from binary format.

        Args:
            data: Binary embedding data.

        Returns:
            List of float values.
        """
        count = len(data) // 4  # 4 bytes per float
        return list(struct.unpack(f"{count}f", data))

    def _cosine_similarity(
        self, vec_a: list[float], vec_b: list[float]
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector.
            vec_b: Second vector.

        Returns:
            Cosine similarity score between 0 and 1.
        """
        if len(vec_a) != len(vec_b):
            raise ValueError(
                f"Vector dimensions don't match: {len(vec_a)} vs {len(vec_b)}"
            )

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def add_chunk(
        self,
        file_path: str,
        text: str,
        embedding: list[float],
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> int:
        """Add a text chunk with its embedding to the index.

        Args:
            file_path: Path to the source file.
            text: The text content of the chunk.
            embedding: Vector embedding of the text.
            start_line: Starting line number in the source file.
            end_line: Ending line number in the source file.

        Returns:
            The ID of the inserted chunk.

        Raises:
            ValueError: If embedding dimension doesn't match index dimension.
        """
        if len(embedding) != self.dimension:
            raise ValueError(
                f"Embedding dimension {len(embedding)} doesn't match "
                f"index dimension {self.dimension}"
            )

        embedding_blob = self._serialize_embedding(embedding)

        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chunks (file_path, start_line, end_line, text, embedding)
                VALUES (?, ?, ?, ?, ?)
                """,
                (file_path, start_line, end_line, text, embedding_blob),
            )
            chunk_id = cursor.lastrowid

            # Add to vector index if available
            if self.has_sqlite_vec and chunk_id is not None:
                try:
                    conn.execute(
                        "INSERT INTO vec_chunks (id, embedding) VALUES (?, ?)",
                        (chunk_id, embedding_blob),
                    )
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to insert into vec_chunks: %s", e)

            return chunk_id or 0

    def search(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[SearchResult]:
        """Search for similar chunks using vector similarity.

        Args:
            query_embedding: Query vector to search for.
            limit: Maximum number of results to return.

        Returns:
            List of SearchResult objects ordered by similarity.
        """
        if len(query_embedding) != self.dimension:
            raise ValueError(
                f"Query embedding dimension {len(query_embedding)} doesn't "
                f"match index dimension {self.dimension}"
            )

        with self._connection() as conn:
            if self.has_sqlite_vec:
                return self._search_sqlite_vec(conn, query_embedding, limit)
            else:
                return self._search_python_fallback(conn, query_embedding, limit)

    def _search_sqlite_vec(
        self,
        conn: sqlite3.Connection,
        query_embedding: list[float],
        limit: int,
    ) -> list[SearchResult]:
        """Search using sqlite-vec extension.

        Args:
            conn: Active database connection.
            query_embedding: Query vector.
            limit: Maximum results.

        Returns:
            List of SearchResult objects.
        """
        query_blob = self._serialize_embedding(query_embedding)

        try:
            rows = conn.execute(
                """
                SELECT c.file_path, c.text, c.start_line, c.end_line,
                       vec_distance_cosine(v.embedding, ?) as distance
                FROM vec_chunks v
                JOIN chunks c ON c.id = v.id
                ORDER BY distance ASC
                LIMIT ?
                """,
                (query_blob, limit),
            ).fetchall()

            return [
                SearchResult(
                    file_path=row["file_path"],
                    text=row["text"],
                    start_line=row["start_line"] or 0,
                    end_line=row["end_line"] or 0,
                    # Convert distance to similarity (1 - distance for cosine)
                    score=1.0 - (row["distance"] or 0.0),
                )
                for row in rows
            ]
        except sqlite3.OperationalError as e:
            logger.warning("sqlite-vec search failed, using fallback: %s", e)
            return self._search_python_fallback(conn, query_embedding, limit)

    def _search_python_fallback(
        self,
        conn: sqlite3.Connection,
        query_embedding: list[float],
        limit: int,
    ) -> list[SearchResult]:
        """Search using pure Python cosine similarity.

        Args:
            conn: Active database connection.
            query_embedding: Query vector.
            limit: Maximum results.

        Returns:
            List of SearchResult objects.
        """
        rows = conn.execute(
            """
            SELECT id, file_path, text, start_line, end_line, embedding
            FROM chunks
            WHERE embedding IS NOT NULL
            """
        ).fetchall()

        results: list[tuple[float, SearchResult]] = []

        for row in rows:
            embedding = self._deserialize_embedding(row["embedding"])
            score = self._cosine_similarity(query_embedding, embedding)

            results.append(
                (
                    score,
                    SearchResult(
                        file_path=row["file_path"],
                        text=row["text"],
                        start_line=row["start_line"] or 0,
                        end_line=row["end_line"] or 0,
                        score=score,
                    ),
                )
            )

        # Sort by score descending and take top results
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        limit: int = 10,
        vector_weight: float = 0.7,
    ) -> list[SearchResult]:
        """Perform hybrid search combining vector similarity and BM25.

        The final score is computed as:
            final_score = vector_weight * vector_score + (1 - vector_weight) * bm25_score

        Args:
            query_embedding: Query vector for semantic search.
            query_text: Query text for BM25 full-text search.
            limit: Maximum number of results to return.
            vector_weight: Weight for vector similarity (0-1), BM25 gets remainder.

        Returns:
            List of SearchResult objects ordered by combined score.
        """
        if not 0 <= vector_weight <= 1:
            raise ValueError("vector_weight must be between 0 and 1")

        with self._connection() as conn:
            # Get vector search results
            if self.has_sqlite_vec:
                vector_results = self._search_sqlite_vec(
                    conn, query_embedding, limit * 2
                )
            else:
                vector_results = self._search_python_fallback(
                    conn, query_embedding, limit * 2
                )

            # Get BM25 search results
            bm25_results = self._search_bm25(conn, query_text, limit * 2)

            # Combine results
            return self._combine_search_results(
                vector_results, bm25_results, vector_weight, limit
            )

    def _search_bm25(
        self, conn: sqlite3.Connection, query_text: str, limit: int
    ) -> list[SearchResult]:
        """Search using FTS5 BM25 ranking.

        Args:
            conn: Active database connection.
            query_text: Query text for full-text search.
            limit: Maximum results.

        Returns:
            List of SearchResult objects.
        """
        # Escape special FTS5 characters and prepare query
        # FTS5 uses double quotes for phrase matching
        safe_query = query_text.replace('"', '""')

        try:
            rows = conn.execute(
                """
                SELECT c.file_path, c.text, c.start_line, c.end_line,
                       bm25(fts_chunks) as rank
                FROM fts_chunks f
                JOIN chunks c ON c.id = f.rowid
                WHERE fts_chunks MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (f'"{safe_query}"', limit),
            ).fetchall()

            if not rows:
                # Try with individual words if phrase match fails
                words = query_text.split()
                if words:
                    word_query = " OR ".join(
                        f'"{w.replace(chr(34), chr(34)+chr(34))}"' for w in words
                    )
                    rows = conn.execute(
                        """
                        SELECT c.file_path, c.text, c.start_line, c.end_line,
                               bm25(fts_chunks) as rank
                        FROM fts_chunks f
                        JOIN chunks c ON c.id = f.rowid
                        WHERE fts_chunks MATCH ?
                        ORDER BY rank ASC
                        LIMIT ?
                        """,
                        (word_query, limit),
                    ).fetchall()

            # Normalize BM25 scores (they're negative, lower is better)
            if rows:
                min_rank = min(row["rank"] for row in rows)
                max_rank = max(row["rank"] for row in rows)
                rank_range = max_rank - min_rank if max_rank != min_rank else 1.0

                return [
                    SearchResult(
                        file_path=row["file_path"],
                        text=row["text"],
                        start_line=row["start_line"] or 0,
                        end_line=row["end_line"] or 0,
                        # Normalize to 0-1 range (inverted since lower rank is better)
                        score=1.0 - ((row["rank"] - min_rank) / rank_range),
                    )
                    for row in rows
                ]

            return []

        except sqlite3.OperationalError as e:
            logger.warning("BM25 search failed: %s", e)
            return []

    def _combine_search_results(
        self,
        vector_results: list[SearchResult],
        bm25_results: list[SearchResult],
        vector_weight: float,
        limit: int,
    ) -> list[SearchResult]:
        """Combine vector and BM25 search results.

        Args:
            vector_results: Results from vector search.
            bm25_results: Results from BM25 search.
            vector_weight: Weight for vector scores.
            limit: Maximum results to return.

        Returns:
            Combined and re-ranked results.
        """
        # Create lookup dictionaries keyed by (file_path, start_line, end_line)
        def make_key(r: SearchResult) -> tuple[str, int, int]:
            return (r.file_path, r.start_line, r.end_line)

        vector_scores: dict[tuple[str, int, int], float] = {
            make_key(r): r.score for r in vector_results
        }
        bm25_scores: dict[tuple[str, int, int], float] = {
            make_key(r): r.score for r in bm25_results
        }

        # Get all unique results
        all_results: dict[tuple[str, int, int], SearchResult] = {}
        for r in vector_results + bm25_results:
            key = make_key(r)
            if key not in all_results:
                all_results[key] = r

        # Calculate combined scores
        combined: list[tuple[float, SearchResult]] = []
        bm25_weight = 1.0 - vector_weight

        for key, result in all_results.items():
            v_score = vector_scores.get(key, 0.0)
            b_score = bm25_scores.get(key, 0.0)
            final_score = vector_weight * v_score + bm25_weight * b_score

            combined.append(
                (
                    final_score,
                    SearchResult(
                        file_path=result.file_path,
                        text=result.text,
                        start_line=result.start_line,
                        end_line=result.end_line,
                        score=final_score,
                    ),
                )
            )

        # Sort by combined score descending
        combined.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in combined[:limit]]

    def delete_by_file(self, file_path: str) -> int:
        """Remove all chunks for a specific file.

        Args:
            file_path: Path of the file to remove chunks for.

        Returns:
            Number of chunks deleted.
        """
        with self._connection() as conn:
            # Get IDs to delete from vec_chunks
            if self.has_sqlite_vec:
                ids = conn.execute(
                    "SELECT id FROM chunks WHERE file_path = ?", (file_path,)
                ).fetchall()

                for row in ids:
                    try:
                        conn.execute(
                            "DELETE FROM vec_chunks WHERE id = ?", (row["id"],)
                        )
                    except sqlite3.OperationalError:
                        pass

            # Delete from main table (triggers handle FTS cleanup)
            cursor = conn.execute(
                "DELETE FROM chunks WHERE file_path = ?", (file_path,)
            )

            deleted = cursor.rowcount
            logger.debug("Deleted %d chunks for file: %s", deleted, file_path)
            return deleted

    def get_indexed_files(self) -> list[str]:
        """Get list of all indexed files.

        Returns:
            List of unique file paths in the index.
        """
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT file_path FROM chunks ORDER BY file_path"
            ).fetchall()
            return [row["file_path"] for row in rows]

    def clear(self) -> None:
        """Clear all data from the index."""
        with self._connection() as conn:
            # Clear vec_chunks if available
            if self.has_sqlite_vec:
                try:
                    conn.execute("DELETE FROM vec_chunks")
                except sqlite3.OperationalError:
                    pass

            # Clear FTS index
            try:
                conn.execute("DELETE FROM fts_chunks")
            except sqlite3.OperationalError:
                pass

            # Clear main table
            conn.execute("DELETE FROM chunks")

            logger.info("Vector index cleared")

    def get_chunk_count(self) -> int:
        """Get the total number of chunks in the index.

        Returns:
            Total chunk count.
        """
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM chunks").fetchone()
            return row["count"] if row else 0

    def get_stats(self) -> dict[str, int | bool]:
        """Get statistics about the index.

        Returns:
            Dictionary with index statistics.
        """
        with self._connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as count FROM chunks"
            ).fetchone()
            files = conn.execute(
                "SELECT COUNT(DISTINCT file_path) as count FROM chunks"
            ).fetchone()

            return {
                "total_chunks": total["count"] if total else 0,
                "indexed_files": files["count"] if files else 0,
                "dimension": self.dimension,
                "has_sqlite_vec": self.has_sqlite_vec,
            }
