import { InMemoryEventBus, type DomainEvent } from "@project-hearth/events";
import { InMemoryPersistenceStore } from "@project-hearth/persistence";
import { loadConfig, logger } from "@project-hearth/shared";

const cfg = loadConfig();
const bus = new InMemoryEventBus();
const persistence = new InMemoryPersistenceStore();

bus.subscribe("job.queued", async (event: DomainEvent) => {
  logger.info("Worker processing queued job", event.payload);
  // TODO: add indexing/summarization/retry/cleanup pipelines.
});

setInterval(async () => {
  const queued = await persistence.getTasksByStatus("queued");
  for (const task of queued) {
    await bus.publish({ type: "job.queued", timestamp: new Date().toISOString(), payload: task });
  }
}, cfg.workerPollMs);

logger.info("ProjectHearth worker started", { pollMs: cfg.workerPollMs });
