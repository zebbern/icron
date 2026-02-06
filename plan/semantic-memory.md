# Semantic Memory Implementation Plan

## Overview
Implement OpenClaw-style semantic memory for icron with auto-detect embedding provider.

## Architecture

### File Structure
```
workspace/
  MEMORY.md          # Long-term curated memory (never auto-summarized)
  memory/
    YYYY-MM-DD.md    # Daily notes (append-only)
    index.sqlite     # Vector index (sqlite-vec)
```

### Components

1. **MemoryStore** (`icron/memory/store.py`)
   - Read/write MEMORY.md and daily logs
   - File watching for changes
   - Chunking text for embedding

2. **EmbeddingProvider** (`icron/memory/embeddings.py`)
   - Auto-detect from user's LLM provider
   - OpenAI: text-embedding-3-small
   - Gemini: embedding-001
   - Ollama: nomic-embed-text
   - Local fallback: sentence-transformers

3. **VectorIndex** (`icron/memory/index.py`)
   - sqlite-vec storage
   - Cosine similarity search
   - Hybrid search (BM25 + vector)

4. **Memory Tools** (`icron/agent/tools/memory_tools.py`)
   - memory_search: Semantic search
   - memory_write: Save to MEMORY.md or daily log
   - memory_get: Read specific file

5. **Config Schema** (`icron/config/schema.py`)
   - memory.enabled
   - memory.embedding_provider (auto/openai/gemini/ollama/local)
   - memory.search.hybrid_enabled
   - memory.search.max_results

## Tasks

### Task 1: Memory Store
- [ ] Create `icron/memory/__init__.py`
- [ ] Create `icron/memory/store.py`
  - MemoryStore class
  - read_memory(), write_memory(), list_memories()
  - chunk_text() for embedding-sized chunks
- [ ] Create daily log management (YYYY-MM-DD.md)

### Task 2: Embedding Providers
- [ ] Create `icron/memory/embeddings.py`
  - EmbeddingProvider base class
  - OpenAIEmbedding, GeminiEmbedding, OllamaEmbedding
  - LocalEmbedding (sentence-transformers)
- [ ] Create `icron/memory/provider_factory.py`
  - auto_detect_provider()
  - get_embedding_provider()

### Task 3: Vector Index
- [ ] Create `icron/memory/index.py`
  - VectorIndex class
  - sqlite-vec setup
  - index_chunk(), search(), delete_chunk()
  - Hybrid search (BM25 + vector)
- [ ] Add sqlite-vec to pyproject.toml

### Task 4: Memory Tools
- [ ] Update `icron/agent/tools/memory_tools.py`
  - MemorySearchTool (semantic search)
  - MemoryWriteTool (save to markdown)
  - MemoryGetTool (read file)
- [ ] Register tools in registry

### Task 5: Config Schema
- [ ] Update `icron/config/schema.py`
  - Add MemoryConfig dataclass
  - Add to IcronConfig
- [ ] Update config.example.json

### Task 6: Integration
- [ ] Update `icron/agent/loop.py`
  - Initialize memory system on startup
  - Background indexing
- [ ] Update `icron/agent/context.py`
  - Add memory context to agent

### Task 7: Tests & Docs
- [ ] Create `tests/test_memory.py`
- [ ] Create `tests/test_embeddings.py`
- [ ] Update docs/architecture.md
- [ ] Update workspace/TOOLS.md

### Task 8: Review & Validation
- [ ] Run all tests
- [ ] Manual testing
- [ ] Git commit and push

## Dependencies
```toml
sqlite-vec = "^0.1.1"
sentence-transformers = { version = "^2.2.0", optional = true }
```

## Config Example
```json
{
  "memory": {
    "enabled": true,
    "embedding_provider": "auto",
    "search": {
      "hybrid_enabled": true,
      "max_results": 10
    }
  }
}
```

## Embedding Provider Auto-Detection Logic
```
1. Check user's primary provider from config
2. Map provider to embedding service:
   - openai -> OpenAI embeddings
   - anthropic -> Local (no embeddings)
   - gemini -> Gemini embeddings
   - ollama -> Ollama embeddings
   - openrouter -> OpenAI embeddings
3. If provider unavailable -> fallback to local
```

## Notes
- Never auto-summarize MEMORY.md
- Daily logs are append-only
- Vector index is for search only, not storage
- Markdown files are source of truth
