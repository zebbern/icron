# Architectural Decision Records

## ADR-001: Tool-based Architecture

**Decision**: Implement all agent capabilities as discrete tools rather than hardcoded behaviors.

**Context**: Needed flexibility for agents to self-modify and extend capabilities.

**Rationale**:
- Enables runtime tool registration
- Supports MCP server integration
- Allows security filtering per-tool
- Makes capabilities discoverable to LLM

**Consequences**:
- (+) Easy to add new tools
- (+) Clear separation of concerns
- (-) Tool overhead for simple operations

---

## ADR-002: Workspace Restriction Security Model

**Decision**: Optionally restrict file operations to a configured workspace directory.

**Context**: Prevent agents from accessing sensitive files outside project scope.

**Rationale**:
- Defense in depth
- Configurable per-session
- Path traversal prevention
- Symlink resolution

**Consequences**:
- (+) Safe for untrusted prompts
- (+) Clear security boundary
- (-) Must whitelist additional paths if needed

---

## ADR-003: Token-based Context Management

**Decision**: Trim conversation history based on token count, newest-first.

**Context**: Long conversations exceed context windows, causing failures.

**Rationale**:
- Keep most recent context (most relevant)
- ~4 chars/token heuristic (fast, accurate enough)
- Configurable budget per provider

**Consequences**:
- (+) Never exceed context limits
- (+) Graceful degradation
- (-) May lose early context in long sessions

---

## ADR-004: Flask for Gateway

**Decision**: Use Flask (sync) rather than FastAPI (async) for the gateway.

**Context**: Needed a simple HTTP server for agent execution.

**Rationale**:
- Simpler debugging
- Agent loop is inherently sequential
- Adequate performance for local use
- Easy Svelte UI integration

**Consequences**:
- (+) Simple codebase
- (-) Not optimal for high-concurrency

---

## ADR-005: JSON File Storage for Memory

**Decision**: Store memory and reminders in JSON files rather than a database.

**Context**: Need persistence without requiring database setup.

**Rationale**:
- Zero dependencies
- Human-readable
- Easy backup/versioning
- Adequate for local agent use

**Consequences**:
- (+) No DB setup required
- (+) Portable
- (-) Not suitable for multi-user production

---

## ADR-006: Subagent via SpawnTool

**Decision**: Implement background task delegation through SpawnTool with async execution.

**Context**: Need ability to run long tasks without blocking main conversation.

**Rationale**:
- Async task execution
- Iteration limits for safety
- Status tracking
- Clean separation from main loop

**Consequences**:
- (+) Non-blocking long tasks
- (+) Controllable execution
- (-) Limited to 15 iterations per subagent
