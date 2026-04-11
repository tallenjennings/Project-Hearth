import { LocalMemoryStore } from "@project-hearth/memory";
import { GemmaLocalProvider } from "@project-hearth/model-runtime";
import { OrchestratorService } from "@project-hearth/orchestrator";
import { InMemoryPersistenceStore } from "@project-hearth/persistence";

export const runtimeContainer = (() => {
  const persistence = new InMemoryPersistenceStore();
  const memory = new LocalMemoryStore();
  const model = new GemmaLocalProvider();
  const orchestrator = new OrchestratorService(memory, model, persistence);
  return { persistence, memory, model, orchestrator };
})();
