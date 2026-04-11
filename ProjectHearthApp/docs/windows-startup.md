# Windows 11 Startup Guide

## Prerequisites
- Node.js 20+
- Docker Desktop (optional but recommended)
- SQL Server Developer or Express (or SQL Server container)
- PowerShell 7+

## Start sequence
```powershell
cd ProjectHearthApp
Copy-Item .env.example .env
npm install
```

## Configure Gemma (optional but recommended)
If you have local Gemma instructions/scripts (for example in `BaseProjects/gemma-personal`), set:

```powershell
notepad .env
```

Then update:

```env
MODEL_PROVIDER=gemma-cli
GEMMA_INFER_COMMAND=python C:/path/to/your/gemma_infer_script.py
```

## Run services (separate terminals)
```powershell
npm run dev:api
npm run dev:mcp
npm run dev:worker
npm run dev:ui
```

## SQL via Docker
```powershell
docker compose -f infra/docker/docker-compose.yml up -d
```
Apply `infra/sql/001_bootstrap.sql` via SSMS or sqlcmd.

## Functional smoke test
```powershell
Invoke-RestMethod -Method Get -Uri http://localhost:4000/health
$task = Invoke-RestMethod -Method Post -Uri http://localhost:4000/tasks -ContentType "application/json" -Body '{"input":"hello from windows"}'
Invoke-RestMethod -Method Post -Uri "http://localhost:4000/tasks/$($task.taskId)/run"
Invoke-RestMethod -Method Get -Uri "http://localhost:4000/tasks/$($task.taskId)"
```
