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
    await this.persistence.saveTask(task);
    const memoryContext = await this.memory.search(task.input);
    const prompt = `Task Input: ${task.input}\nRelevant Memory Count: ${memoryContext.length}`;
    const response = await this.model.generate({ prompt, system: "You are Project Hearth orchestrator runtime." });
    return { output: response.text };
  }
}
