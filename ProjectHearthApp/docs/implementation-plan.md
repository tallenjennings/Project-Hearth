# Implementation Plan

## Phase 1 — Discovery (completed)

### Observed source patterns in `BaseProjects`
- `claw-code-main`: strong runtime orchestration boundaries and provider/tool lifecycle decomposition.
- `mempalace-main`: rich memory semantics and local-first storage/search mindset.
- `gemma-main`: model adapter focus around Gemma APIs, not full app composition.
- `modelcontextprotocol-main`: protocol contract discipline and schema-first interfaces.
- `servers-main`: security-aware reference tool implementations.

### Consolidation decisions
- Unified on TypeScript-first runtime contracts for API, MCP, worker, and core libs.
- Introduced adapter interfaces for model/memory/persistence so production backends are swappable.
- Avoided direct source reuse or folder mirroring from any upstream snapshot.

## Phase 2 — Architecture (completed)
- Defined monorepo structure with app/lib/infra separation.
- Wrote architecture and implementation docs.

## Phase 3 — Scaffolding (completed)
- Created API, MCP server, worker, and UI shell apps.
- Created orchestrator, memory, model, persistence, events, shared, tooling libraries.
- Added env template, SQL bootstrap script, docker compose, and startup scripts.

## Phase 4 — MVP first implementation (completed for starter pass)
- API endpoints: task enqueue, task run, task status + events, health.
- Orchestrator manages lifecycle state transitions and event recording.
- Memory interface and local placeholder store for episodic/semantic/working/procedural domains.
- Model runtime interface with Gemma local placeholder provider.
- MCP endpoints include health, memory search/write, SQL read-safe query gate, job status, filesystem read sandbox.
- Worker polls queued tasks and routes them through orchestrator.

- Added environment-driven Gemma CLI provider integration (`MODEL_PROVIDER=gemma-cli`, `GEMMA_INFER_COMMAND=...`) to map personal Win11 Gemma setups into runtime adapter configuration.

## Borrowed concepts by source
- `claw-code-main`: orchestration boundaries, provider/tool lifecycle separation.
- `mempalace-main`: memory category model + local-first retrieval mindset.
- `gemma-main`: model-provider abstraction target for Gemma adapters.
- `modelcontextprotocol-main`: MCP contract orientation and tool schema discipline.
- `servers-main`: reference patterns for server-side tools and security posture.

## Explicitly not copied
- Upstream folder structures or project wiring.
- Reference servers as production runtime.
- MCP spec repo code as runtime dependency.
- MemPalace/Claw implementation internals verbatim.

## Next steps
1. Replace in-memory persistence with SQL Server adapter + migrations runner.
2. Add task retry policy (`attemptCount`/`maxAttempts`) in worker execution loop.
3. Add typed MCP JSON-RPC envelope and role-based tool authorization.
4. Integrate local Gemma runtime process adapter and structured output parsing.
5. Expand UI shell into task/memory/job dashboard.
