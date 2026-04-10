import express from "express";
import { LocalMemoryStore } from "@project-hearth/memory";
import { InMemoryPersistenceStore } from "@project-hearth/persistence";
import { loadConfig, logger } from "@project-hearth/shared";
import { baseToolCatalog } from "@project-hearth/tooling";
import path from "node:path";
import fs from "node:fs/promises";

const app = express();
app.use(express.json());
const cfg = loadConfig();
const memory = new LocalMemoryStore();
const persistence = new InMemoryPersistenceStore();

app.get("/mcp/tools", (_req, res) => res.json({ tools: baseToolCatalog }));
app.get("/mcp/health", (_req, res) => res.json({ status: "ok", service: "mcp-server" }));

app.post("/mcp/memory/search", async (req, res) => {
  const q = String(req.body?.query ?? "");
  const rows = await memory.search(q);
  res.json({ records: rows });
});

app.post("/mcp/memory/write", async (req, res) => {
  const saved = await memory.write({
    id: crypto.randomUUID(),
    type: req.body?.type ?? "episodic",
    content: String(req.body?.content ?? ""),
    tags: req.body?.tags ?? []
  });
  res.json(saved);
});

app.get("/mcp/jobs/:taskId", async (req, res) => {
  res.json({ task: await persistence.getTask(req.params.taskId) });
});

app.post("/mcp/sql/query-read", async (_req, res) => {
  res.json({ message: "Read-only SQL surface placeholder. Wire to SQL Server repository next." });
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
