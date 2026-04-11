import dotenv from "dotenv";

dotenv.config();

export type AppConfig = {
  appPort: number;
  mcpPort: number;
  workerPollMs: number;
  sql: {
    host: string;
    port: number;
    user: string;
    password: string;
    database: string;
  };
  allowedFilesystemRoot: string;
  modelProvider: string;
  memoryBackend: string;
  gemmaInferCommand: string;
};

export const loadConfig = (): AppConfig => ({
  appPort: Number(process.env.APP_PORT ?? 4000),
  mcpPort: Number(process.env.MCP_PORT ?? 4100),
  workerPollMs: Number(process.env.WORKER_POLL_MS ?? 1500),
  sql: {
    host: process.env.SQLSERVER_HOST ?? "localhost",
    port: Number(process.env.SQLSERVER_PORT ?? 1433),
    user: process.env.SQLSERVER_USER ?? "sa",
    password: process.env.SQLSERVER_PASSWORD ?? "",
    database: process.env.SQLSERVER_DATABASE ?? "ProjectHearth"
  },
  allowedFilesystemRoot: process.env.ALLOWED_FILESYSTEM_ROOT ?? "./data",
  modelProvider: process.env.MODEL_PROVIDER ?? "gemma-local",
  memoryBackend: process.env.MEMORY_BACKEND ?? "local",
  gemmaInferCommand: process.env.GEMMA_INFER_COMMAND ?? ""
});

export const logger = {
  info: (message: string, meta?: unknown) => console.log(`[INFO] ${message}`, meta ?? ""),
  warn: (message: string, meta?: unknown) => console.warn(`[WARN] ${message}`, meta ?? ""),
  error: (message: string, meta?: unknown) => console.error(`[ERROR] ${message}`, meta ?? "")
};
