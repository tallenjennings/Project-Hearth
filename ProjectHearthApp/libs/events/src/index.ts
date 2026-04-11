export type DomainEvent<TPayload = unknown> = {
  type: string;
  timestamp: string;
  payload: TPayload;
};

export interface EventBus {
  publish<TPayload>(event: DomainEvent<TPayload>): Promise<void>;
  subscribe(eventType: string, handler: (event: DomainEvent) => Promise<void>): void;
}

export class InMemoryEventBus implements EventBus {
  private handlers = new Map<string, Array<(event: DomainEvent) => Promise<void>>>();

  async publish<TPayload>(event: DomainEvent<TPayload>): Promise<void> {
    const targets = this.handlers.get(event.type) ?? [];
    await Promise.all(targets.map((handler) => handler(event)));
  }

  subscribe(eventType: string, handler: (event: DomainEvent) => Promise<void>): void {
    const existing = this.handlers.get(eventType) ?? [];
    this.handlers.set(eventType, [...existing, handler]);
  }
}
