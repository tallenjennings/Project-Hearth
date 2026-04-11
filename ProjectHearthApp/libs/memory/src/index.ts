export type MemoryType = "episodic" | "semantic" | "working" | "procedural";

export type MemoryRecord = {
  id: string;
  type: MemoryType;
  content: string;
  tags?: string[];
  createdAt: string;
};

export interface MemoryStore {
  write(record: Omit<MemoryRecord, "createdAt">): Promise<MemoryRecord>;
  search(query: string, type?: MemoryType): Promise<MemoryRecord[]>;
}

export class LocalMemoryStore implements MemoryStore {
  private records: MemoryRecord[] = [];

  async write(record: Omit<MemoryRecord, "createdAt">): Promise<MemoryRecord> {
    const full: MemoryRecord = { ...record, createdAt: new Date().toISOString() };
    this.records.push(full);
    return full;
  }

  async search(query: string, type?: MemoryType): Promise<MemoryRecord[]> {
    return this.records.filter((record) => {
      const matchesType = type ? record.type === type : true;
      const matchesText = record.content.toLowerCase().includes(query.toLowerCase());
      return matchesType && matchesText;
    });
  }
}

// TODO: Add MemPalace-inspired vector + graph indexing implementation behind this interface.
