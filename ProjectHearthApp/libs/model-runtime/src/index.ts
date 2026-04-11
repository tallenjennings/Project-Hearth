import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

export type ModelRequest = {
  prompt: string;
  system?: string;
  tools?: Array<{ name: string; description: string }>;
};

export type ModelResponse = {
  text: string;
  toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>;
};

export interface ModelRuntime {
  generate(request: ModelRequest): Promise<ModelResponse>;
}

export class GemmaLocalProvider implements ModelRuntime {
  async generate(request: ModelRequest): Promise<ModelResponse> {
    return {
      text: `Gemma placeholder response for prompt: ${request.prompt}`,
      toolCalls: []
    };
  }
}

export class GemmaCliProvider implements ModelRuntime {
  constructor(private readonly inferCommand: string) {}

  async generate(request: ModelRequest): Promise<ModelResponse> {
    const escapedPrompt = request.prompt.replaceAll('"', '\\"');
    const command = `${this.inferCommand} \"${escapedPrompt}\"`;
    const { stdout } = await execAsync(command, { maxBuffer: 1024 * 1024 * 8 });

    return {
      text: stdout.trim() || "",
      toolCalls: []
    };
  }
}

export type ModelRuntimeConfig = {
  provider: string;
  gemmaInferCommand?: string;
};

export const createModelRuntime = (config: ModelRuntimeConfig): ModelRuntime => {
  if (config.provider === "gemma-cli" && config.gemmaInferCommand) {
    return new GemmaCliProvider(config.gemmaInferCommand);
  }

  return new GemmaLocalProvider();
};
