# Implementation Plan

## Phase 1 — Discovery (completed)
- Reviewed source snapshots in `BaseProjects`.
- Extracted architecture ideas only; no runtime reuse.
- Produced design brief and module plan.

## Phase 2 — Architecture (completed)
- Defined monorepo structure with app/lib/infra separation.
- Wrote architecture and implementation docs.

## Phase 3 — Scaffolding (completed)
- Created API, MCP server, worker, and UI shell apps.
- Created orchestrator, memory, model, persistence, events, shared, tooling libraries.
- Added env template, SQL bootstrap script, docker compose, and startup scripts.

## Phase 4 — MVP first implementation (in progress)
- API health endpoint and `/tasks` route implemented.
- Orchestrator stub routes task through memory + model interfaces.
- Gemma provider placeholder implemented.
- Memory interfaces + local store implemented.
- SQL schema bootstrap script implemented.
- MCP tool catalog and first endpoints implemented.
- Worker queue polling scaffold implemented.

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
2. Implement durable queue and retry policies for worker.
3. Add typed MCP protocol envelope and auth/permissions hooks.
4. Integrate local Gemma runtime process adapter.
5. Upgrade UI shell to show task list + statuses + memory inspector.
