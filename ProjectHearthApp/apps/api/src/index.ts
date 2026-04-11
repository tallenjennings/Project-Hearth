import express from "express";
import { loadConfig, logger, runtimeContainer } from "@project-hearth/shared";

const config = loadConfig();
const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "api", timestamp: new Date().toISOString() });
});

app.post("/tasks", async (req, res) => {
  const task = await runtimeContainer.persistence.createTask({
    taskId: crypto.randomUUID(),
    sessionId: String(req.body?.sessionId ?? "local-session"),
    input: String(req.body?.input ?? ""),
    status: "queued",
    attemptCount: 0,
    maxAttempts: 3
  });
  await runtimeContainer.persistence.appendTaskEvent({
    eventId: crypto.randomUUID(),
    taskId: task.taskId,
    eventType: "task.queued",
    createdAt: new Date().toISOString()
  });
  res.status(202).json({ taskId: task.taskId, status: task.status });
});

app.post("/tasks/:taskId/run", async (req, res) => {
  const task = await runtimeContainer.persistence.getTask(req.params.taskId);
  if (!task) return res.status(404).json({ error: "Task not found" });

  const result = await runtimeContainer.orchestrator.routeTask(task);
  res.json({ taskId: task.taskId, output: result.output });
});

app.get("/tasks/:taskId", async (req, res) => {
  const task = await runtimeContainer.persistence.getTask(req.params.taskId);
  if (!task) return res.status(404).json({ error: "Task not found" });
  const events = await runtimeContainer.persistence.getTaskEvents(task.taskId);
  res.json({ task, events });
});

app.listen(config.appPort, () => {
  logger.info(`ProjectHearth API listening on port ${config.appPort}`);
});
