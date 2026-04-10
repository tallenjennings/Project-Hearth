export type ToolMode = "read" | "write";

export type ToolDefinition = {
  name: string;
  description: string;
  mode: ToolMode;
};

export const baseToolCatalog: ToolDefinition[] = [
  { name: "health.status", description: "Read app health", mode: "read" },
  { name: "memory.search", description: "Search memory entries", mode: "read" },
  { name: "memory.write", description: "Store memory entries", mode: "write" },
  { name: "sql.query.read", description: "Execute safe read-only SQL query", mode: "read" },
  { name: "jobs.status", description: "Get task/job status", mode: "read" },
  { name: "filesystem.read", description: "Read files under allowed root", mode: "read" }
];
