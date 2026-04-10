export type TaskStatus = "queued" | "running" | "succeeded" | "failed";

export type TaskRecord = {
  taskId: string;
  sessionId: string;
  input: string;
  status: TaskStatus;
  createdAt: string;
};

export interface PersistenceStore {
  saveTask(task: TaskRecord): Promise<void>;
  getTask(taskId: string): Promise<TaskRecord | undefined>;
  getTasksByStatus(status: TaskStatus): Promise<TaskRecord[]>;
}

export class InMemoryPersistenceStore implements PersistenceStore {
  private tasks = new Map<string, TaskRecord>();

  async saveTask(task: TaskRecord): Promise<void> {
    this.tasks.set(task.taskId, task);
  }

  async getTask(taskId: string): Promise<TaskRecord | undefined> {
    return this.tasks.get(taskId);
  }

  async getTasksByStatus(status: TaskStatus): Promise<TaskRecord[]> {
    return [...this.tasks.values()].filter((task) => task.status === status);
  }
}

export const sqlServerNotes = {
  dialect: "mssql",
  readiness: "MVP scaffolding with SQL bootstrap scripts in infra/sql"
};
