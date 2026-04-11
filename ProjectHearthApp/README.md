# ProjectHearthApp

ProjectHearthApp is a **new, local-first AI application** built from scratch for Windows 11 development workflows. It is inspired by design ideas in `BaseProjects/*` but does not depend on those folders at runtime.

## Design brief (pre-scaffold)

### Problem
Build one coherent system that unifies orchestration, memory, model runtime abstraction, MCP tools, SQL Server persistence, and worker jobs for local operation.

### MVP approach
- Use a TypeScript monorepo for consistent contracts and fast local iteration.
- Keep subsystem boundaries strict (apps vs libs vs infra).
- Start with in-memory adapters and SQL bootstrap scripts, then swap in production adapters.

### Build plan
1. Define contracts first (orchestrator, memory, model, persistence, event bus, tooling).
2. Stand up API/MCP/worker entry points with health and stub workflows.
3. Add SQL Server schema and Windows startup guidance.
4. Iterate from in-memory components toward SQL + local model + richer memory retrieval.

## Folder layout

- `apps/api`: HTTP API with health and task routing.
- `apps/mcp-server`: MCP-compatible internal tool surface.
- `apps/worker`: background queue processor.
- `apps/ui`: minimal local UI shell.
- `libs/*`: reusable core modules.
- `infra/sql`: SQL Server schema scripts.
- `infra/docker`: local SQL Server container setup.
- `infra/scripts`: PowerShell + shell startup scripts.
- `docs`: architecture and implementation roadmap.

## Quick start (Windows 11)

1. Install Node.js 20+, Docker Desktop, and SQL Server tools.
2. In PowerShell:
   ```powershell
   cd ProjectHearthApp
   Copy-Item .env.example .env
   npm install
   npm run dev:api
   ```
3. Optional SQL container:
   ```powershell
   docker compose -f infra/docker/docker-compose.yml up -d
   ```
4. Apply SQL bootstrap script `infra/sql/001_bootstrap.sql` using sqlcmd or SSMS.


## MVP service surfaces

- API:
  - `GET /health`
  - `POST /tasks` (enqueue)
  - `POST /tasks/:taskId/run` (execute through orchestrator)
  - `GET /tasks/:taskId` (status + events)
- MCP server:
  - `GET /mcp/tools`
  - `GET /mcp/health`
  - `POST /mcp/memory/search`
  - `POST /mcp/memory/write`
  - `POST /mcp/sql/query-read` (read-only query validation)
  - `GET /mcp/jobs/:taskId`
  - `GET /mcp/filesystem/read?path=...`

## Important

`BaseProjects/*` is treated as **design reference only**. This app is intentionally rewritten with ProjectHearthApp conventions.
