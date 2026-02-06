"""Memory module for icron - OpenClaw-style semantic memory."""

from .store import MemoryStore
from .index import VectorIndex, SearchResult
from .embeddings import (
    EmbeddingProvider,
    OpenAIEmbedding,
    GeminiEmbedding,
    OllamaEmbedding,
    LocalEmbedding,
    get_embedding_provider,
)

__all__ = [
    "MemoryStore",
    "VectorIndex",
    "SearchResult",
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "GeminiEmbedding",
    "OllamaEmbedding",
    "LocalEmbedding",
    "get_embedding_provider",
]
