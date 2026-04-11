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
   ```
3. Start API, MCP server, worker, and UI in separate terminals:
   ```powershell
   npm run dev:api
   npm run dev:mcp
   npm run dev:worker
   npm run dev:ui
   ```
4. Optional SQL container:
   ```powershell
   docker compose -f infra/docker/docker-compose.yml up -d
   ```
5. Apply SQL bootstrap script `infra/sql/001_bootstrap.sql` using sqlcmd or SSMS.

## Gemma 4 local integration

If you added personal Gemma setup instructions under `BaseProjects/gemma-personal`, map your local inference command into `.env`:

```env
MODEL_PROVIDER=gemma-cli
GEMMA_INFER_COMMAND=python C:/path/to/your/gemma_infer_script.py
```

ProjectHearthApp will call `GEMMA_INFER_COMMAND "<prompt>"` through the `GemmaCliProvider` adapter.

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

## Smoke test commands

```powershell
# 1) Health
curl http://localhost:4000/health

# 2) Create task
$task = Invoke-RestMethod -Method Post -Uri http://localhost:4000/tasks -ContentType "application/json" -Body '{"input":"hello"}'

# 3) Run task
Invoke-RestMethod -Method Post -Uri "http://localhost:4000/tasks/$($task.taskId)/run"

# 4) Inspect task + events
Invoke-RestMethod -Method Get -Uri "http://localhost:4000/tasks/$($task.taskId)"
```

## Important

`BaseProjects/*` is treated as **design reference only**. This app is intentionally rewritten with ProjectHearthApp conventions.
