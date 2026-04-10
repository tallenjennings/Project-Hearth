import express from "express";
import { LocalMemoryStore } from "@project-hearth/memory";
import { GemmaLocalProvider } from "@project-hearth/model-runtime";
import { OrchestratorService } from "@project-hearth/orchestrator";
import { InMemoryPersistenceStore } from "@project-hearth/persistence";
import { loadConfig, logger } from "@project-hearth/shared";

const config = loadConfig();
const app = express();
app.use(express.json());

const persistence = new InMemoryPersistenceStore();
const memory = new LocalMemoryStore();
const model = new GemmaLocalProvider();
const orchestrator = new OrchestratorService(memory, model, persistence);

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "api", timestamp: new Date().toISOString() });
});

app.post("/tasks", async (req, res) => {
  const input = String(req.body?.input ?? "");
  const task = {
    taskId: crypto.randomUUID(),
    sessionId: String(req.body?.sessionId ?? "local-session"),
    input,
    status: "queued" as const,
    createdAt: new Date().toISOString()
  };

  const result = await orchestrator.routeTask(task);
  res.json({ taskId: task.taskId, output: result.output });
});

app.listen(config.appPort, () => {
  logger.info(`ProjectHearth API listening on port ${config.appPort}`);
});
