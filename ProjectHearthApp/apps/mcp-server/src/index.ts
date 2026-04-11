import express from "express";
import { validateReadOnlySql } from "@project-hearth/persistence";
import { loadConfig, logger, runtimeContainer } from "@project-hearth/shared";
import { baseToolCatalog } from "@project-hearth/tooling";
import path from "node:path";
import fs from "node:fs/promises";

const app = express();
app.use(express.json());
const cfg = loadConfig();

app.get("/mcp/tools", (_req, res) => res.json({ tools: baseToolCatalog }));
app.get("/mcp/health", (_req, res) => res.json({ status: "ok", service: "mcp-server" }));

app.post("/mcp/memory/search", async (req, res) => {
  const q = String(req.body?.query ?? "");
  const rows = await runtimeContainer.memory.search(q);
  res.json({ records: rows });
});

app.post("/mcp/memory/write", async (req, res) => {
  const saved = await runtimeContainer.memory.write({
    id: crypto.randomUUID(),
    type: req.body?.type ?? "episodic",
    content: String(req.body?.content ?? ""),
    tags: req.body?.tags ?? []
  });
  res.json(saved);
});

app.get("/mcp/jobs/:taskId", async (req, res) => {
  const task = await runtimeContainer.persistence.getTask(req.params.taskId);
  const events = task ? await runtimeContainer.persistence.getTaskEvents(task.taskId) : [];
  res.json({ task, events });
});

app.post("/mcp/sql/query-read", async (req, res) => {
  const query = String(req.body?.query ?? "");
  const validation = validateReadOnlySql(query);
  if (!validation.ok) {
    return res.status(400).json({ error: validation.reason });
  }

  return res.json({
    accepted: true,
    query,
    message: "Query validated as read-only. SQL Server execution adapter is the next integration step."
  });
});

app.get("/mcp/filesystem/read", async (req, res) => {
  const requested = String(req.query.path ?? "");
  const resolved = path.resolve(cfg.allowedFilesystemRoot, requested);
  const root = path.resolve(cfg.allowedFilesystemRoot);
  if (!resolved.startsWith(root)) {
    return res.status(403).json({ error: "Path outside allowed root" });
  }

  try {
    const content = await fs.readFile(resolved, "utf8");
    return res.json({ path: resolved, content });
  } catch {
    return res.status(404).json({ error: "File not found" });
  }
});

app.listen(cfg.mcpPort, () => logger.info(`ProjectHearth MCP server on ${cfg.mcpPort}`));
