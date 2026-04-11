import { InMemoryEventBus, type DomainEvent } from "@project-hearth/events";
import { loadConfig, logger, runtimeContainer } from "@project-hearth/shared";

const cfg = loadConfig();
const bus = new InMemoryEventBus();

bus.subscribe("job.queued", async (event: DomainEvent) => {
  const payload = event.payload as { taskId?: string } | undefined;
  const taskId = payload?.taskId;
  if (!taskId) return;

  const task = await runtimeContainer.persistence.getTask(taskId);
  if (!task || task.status !== "queued") return;

  logger.info("Worker routing queued task", { taskId });
  await runtimeContainer.orchestrator.routeTask(task);
});

setInterval(async () => {
  const queued = await runtimeContainer.persistence.getTasksByStatus("queued");
  for (const task of queued) {
    await bus.publish({
      type: "job.queued",
      timestamp: new Date().toISOString(),
      payload: { taskId: task.taskId }
    });
  }
}, cfg.workerPollMs);

logger.info("ProjectHearth worker started", { pollMs: cfg.workerPollMs });
