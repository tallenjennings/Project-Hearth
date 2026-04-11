export type TaskStatus = "queued" | "running" | "succeeded" | "failed";

export type TaskRecord = {
  taskId: string;
  sessionId: string;
  input: string;
  status: TaskStatus;
  attemptCount: number;
  maxAttempts: number;
  createdAt: string;
  updatedAt: string;
};

export type TaskEvent = {
  eventId: string;
  taskId: string;
  eventType: string;
  payload?: Record<string, unknown>;
  createdAt: string;
};

export interface PersistenceStore {
  createTask(task: Omit<TaskRecord, "createdAt" | "updatedAt">): Promise<TaskRecord>;
  saveTask(task: TaskRecord): Promise<void>;
  getTask(taskId: string): Promise<TaskRecord | undefined>;
  getTasksByStatus(status: TaskStatus): Promise<TaskRecord[]>;
  updateTaskStatus(taskId: string, status: TaskStatus): Promise<TaskRecord | undefined>;
  appendTaskEvent(event: TaskEvent): Promise<void>;
  getTaskEvents(taskId: string): Promise<TaskEvent[]>;
}

export class InMemoryPersistenceStore implements PersistenceStore {
  private tasks = new Map<string, TaskRecord>();
  private taskEvents = new Map<string, TaskEvent[]>();

  async createTask(task: Omit<TaskRecord, "createdAt" | "updatedAt">): Promise<TaskRecord> {
    const now = new Date().toISOString();
    const full: TaskRecord = { ...task, createdAt: now, updatedAt: now };
    this.tasks.set(task.taskId, full);
    return full;
  }

  async saveTask(task: TaskRecord): Promise<void> {
    this.tasks.set(task.taskId, { ...task, updatedAt: new Date().toISOString() });
  }

  async getTask(taskId: string): Promise<TaskRecord | undefined> {
    return this.tasks.get(taskId);
  }

  async getTasksByStatus(status: TaskStatus): Promise<TaskRecord[]> {
    return [...this.tasks.values()].filter((task) => task.status === status);
  }

  async updateTaskStatus(taskId: string, status: TaskStatus): Promise<TaskRecord | undefined> {
    const task = this.tasks.get(taskId);
    if (!task) return undefined;
    const next = { ...task, status, updatedAt: new Date().toISOString() };
    this.tasks.set(taskId, next);
    return next;
  }

  async appendTaskEvent(event: TaskEvent): Promise<void> {
    const existing = this.taskEvents.get(event.taskId) ?? [];
    this.taskEvents.set(event.taskId, [...existing, event]);
  }

  async getTaskEvents(taskId: string): Promise<TaskEvent[]> {
    return this.taskEvents.get(taskId) ?? [];
  }
}

const BLOCKED_SQL_TOKENS = ["insert", "update", "delete", "drop", "alter", "truncate", "create", "exec"];

export const validateReadOnlySql = (query: string): { ok: boolean; reason?: string } => {
  const normalized = query.trim().toLowerCase();
  if (!normalized.startsWith("select")) {
    return { ok: false, reason: "Only SELECT statements are allowed." };
  }

  if (normalized.includes(";")) {
    return { ok: false, reason: "Multiple statements are not allowed." };
  }

  for (const token of BLOCKED_SQL_TOKENS) {
    if (normalized.includes(` ${token} `)) {
      return { ok: false, reason: `Keyword not allowed in read-only surface: ${token}` };
    }
  }

  return { ok: true };
};

export const sqlServerNotes = {
  dialect: "mssql",
  readiness: "MVP scaffolding with SQL bootstrap scripts in infra/sql"
};
