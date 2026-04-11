# ProjectHearthApp Architecture

## Purpose
ProjectHearthApp is a Windows-11-first local AI runtime that coordinates orchestration, memory, model generation, MCP tools, SQL persistence, and background jobs.

## How this differs from BaseProjects
- Not a fork of any upstream snapshot.
- No runtime import of `BaseProjects/*`.
- One cohesive naming and module system.
- Focused MVP scope (health, routing, tool catalog, SQL schema, worker loop).

## Subsystems
- **Orchestrator (`libs/orchestrator`)**: task state transitions, context assembly, model invocation.
- **Memory (`libs/memory`)**: episodic/semantic/working/procedural memory interfaces.
- **Model Runtime (`libs/model-runtime`)**: provider abstraction with Gemma placeholder adapter.
- **Persistence (`libs/persistence`)**: task/session storage contracts; SQL-ready roadmap.
- **Events (`libs/events`)**: internal event bus abstraction.
- **Tooling (`libs/tooling`)**: tool catalog and read/write mode separation.
- **API (`apps/api`)**: external app endpoint + orchestrator entry.
- **MCP Server (`apps/mcp-server`)**: MCP-style tool endpoints.
- **Worker (`apps/worker`)**: async job polling and processing.
- **UI (`apps/ui`)**: minimal local shell.

## Data flow
1. Client submits a task to API.
2. API calls orchestrator.
3. Orchestrator queries memory and persistence, then calls model runtime.
4. Result is returned and task state can be updated.
5. Worker handles queued background tasks.
6. MCP server exposes tool-based access for internal/external agent clients.

## Concurrency model
- API and MCP server are stateless HTTP services.
- Worker loop polls queued tasks on an interval and emits events.
- Event bus abstraction allows future swap to persistent queue.

## MCP usage model
- Initial tools: health, memory search/write, SQL read placeholder, job status, filesystem read.
- Tool definitions include access mode (`read` vs `write`) for policy checks.
- Contracts designed to align with MCP-style tool invocation patterns.

## Memory model
- Memory types: episodic, semantic, working, procedural.
- MVP uses in-memory store.
- Planned extension: vector + graph-backed retrieval with indexing metadata in SQL Server.

## SQL Server role
- System of record for sessions/messages/tasks/events/tools/entities/settings.
- Bootstrap script created under `infra/sql`.
- Repository interfaces in code enable adapter swap from in-memory to SQL Server.

## Windows 11 deployment approach
- PowerShell-first scripts in `infra/scripts`.
- Docker Desktop compose file for local SQL Server.
- WSL2 optional; native Windows workflow supported.
