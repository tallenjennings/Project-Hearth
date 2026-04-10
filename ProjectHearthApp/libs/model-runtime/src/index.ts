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
