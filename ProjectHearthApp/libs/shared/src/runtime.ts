import { LocalMemoryStore } from "@project-hearth/memory";
import { createModelRuntime } from "@project-hearth/model-runtime";
import { OrchestratorService } from "@project-hearth/orchestrator";
import { InMemoryPersistenceStore } from "@project-hearth/persistence";
import { loadConfig } from "./config.js";

export const runtimeContainer = (() => {
  const config = loadConfig();
  const persistence = new InMemoryPersistenceStore();
  const memory = new LocalMemoryStore();
  const model = createModelRuntime({
    provider: config.modelProvider,
    gemmaInferCommand: config.gemmaInferCommand
  });
  const orchestrator = new OrchestratorService(memory, model, persistence);
  return { persistence, memory, model, orchestrator };
})();
