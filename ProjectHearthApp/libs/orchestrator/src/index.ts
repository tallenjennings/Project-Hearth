import { type MemoryStore } from "@project-hearth/memory";
import { type ModelRuntime } from "@project-hearth/model-runtime";
import { type PersistenceStore, type TaskRecord } from "@project-hearth/persistence";

export class OrchestratorService {
  constructor(
    private readonly memory: MemoryStore,
    private readonly model: ModelRuntime,
    private readonly persistence: PersistenceStore
  ) {}

  async routeTask(task: TaskRecord): Promise<{ output: string }> {
    await this.persistence.appendTaskEvent({
      eventId: crypto.randomUUID(),
      taskId: task.taskId,
      eventType: "task.started",
      createdAt: new Date().toISOString()
    });
    await this.persistence.updateTaskStatus(task.taskId, "running");

    try {
      const memoryContext = await this.memory.search(task.input);
      const prompt = `Task Input: ${task.input}\nRelevant Memory Count: ${memoryContext.length}`;
      const response = await this.model.generate({
        prompt,
        system: "You are Project Hearth orchestrator runtime."
      });

      await this.persistence.updateTaskStatus(task.taskId, "succeeded");
      await this.persistence.appendTaskEvent({
        eventId: crypto.randomUUID(),
        taskId: task.taskId,
        eventType: "task.succeeded",
        payload: { toolCalls: response.toolCalls?.length ?? 0 },
        createdAt: new Date().toISOString()
      });
      return { output: response.text };
    } catch (error) {
      await this.persistence.updateTaskStatus(task.taskId, "failed");
      await this.persistence.appendTaskEvent({
        eventId: crypto.randomUUID(),
        taskId: task.taskId,
        eventType: "task.failed",
        payload: { reason: String(error) },
        createdAt: new Date().toISOString()
      });
      throw error;
    }
  }
}
