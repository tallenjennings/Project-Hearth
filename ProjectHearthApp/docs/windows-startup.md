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
npm run dev:api
```

### Optional services
```powershell
npm run dev:mcp
npm run dev:worker
npm run dev:ui
```

### SQL via Docker
```powershell
docker compose -f infra/docker/docker-compose.yml up -d
```
Apply `infra/sql/001_bootstrap.sql` via SSMS or sqlcmd.
