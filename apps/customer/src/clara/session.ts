import type { Claim } from "./claims";
import type { Topic } from "./topics";

export interface ClaraSessionState {
  seeded: Claim | null | undefined;
  claims: Claim[];
  blocks: Record<string, string>;
  reviewed: string[];
  topic: Topic | null;
}

export interface SessionStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
  key(index: number): string | null;
  readonly length: number;
}

const prefix = "clara.session.v1.";

export function memoryStorage(): SessionStorage {
  const data = new Map<string, string>();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
    key: (index) => [...data.keys()][index] ?? null,
    get length() {
      return data.size;
    },
  };
}

export const emptySession: ClaraSessionState = {
  seeded: undefined,
  claims: [],
  blocks: {},
  reviewed: [],
  topic: null,
};

function quietly(action: () => void) {
  try {
    action();
  } catch {
    return;
  }
}

function parse(raw: string | null): ClaraSessionState {
  if (!raw) return emptySession;
  try {
    const stored = JSON.parse(raw) as Partial<ClaraSessionState>;
    return {
      seeded: stored.seeded,
      claims: Array.isArray(stored.claims) ? stored.claims : [],
      blocks: stored.blocks && typeof stored.blocks === "object" ? stored.blocks : {},
      reviewed: Array.isArray(stored.reviewed) ? stored.reviewed : [],
      topic: stored.topic ?? null,
    };
  } catch {
    return emptySession;
  }
}

export function createClaraSession(storage: SessionStorage) {
  const listeners = new Set<() => void>();
  let key: string | null = null;
  let state = emptySession;

  function read(): ClaraSessionState {
    if (!key) return emptySession;
    try {
      return parse(storage.getItem(key));
    } catch {
      return emptySession;
    }
  }

  function update(change: (current: ClaraSessionState) => ClaraSessionState) {
    state = change(state);
    const stored = key;
    if (stored) quietly(() => storage.setItem(stored, JSON.stringify(state)));
    for (const listener of listeners) listener();
  }

  return {
    open(customerId: string) {
      const next = `${prefix}${customerId}`;
      if (next === key) return;
      key = next;
      state = read();
      for (const listener of listeners) listener();
    },
    current: () => state,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    resolveSeeded(claim: Claim | null) {
      update((current) => ({ ...current, seeded: claim }));
    },
    addClaim(claim: Claim) {
      update((current) => ({
        ...current,
        claims: [claim, ...current.claims.filter((item) => item.transaction_id !== claim.transaction_id)],
      }));
    },
    block(productId: string, at: string) {
      update((current) =>
        productId in current.blocks ? current : { ...current, blocks: { ...current.blocks, [productId]: at } },
      );
    },
    markReviewed(transactionId: string) {
      update((current) =>
        current.reviewed.includes(transactionId)
          ? current
          : { ...current, reviewed: [...current.reviewed, transactionId] },
      );
    },
    startTopic(topic: Topic) {
      update((current) => ({ ...current, topic }));
    },
    takeTopic(): Topic | null {
      const { topic } = state;
      if (topic) update((current) => ({ ...current, topic: null }));
      return topic;
    },
    resetDemo() {
      update((current) => ({ ...emptySession, seeded: current.seeded }));
    },
    clear() {
      quietly(() => {
        const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
        for (const stored of keys) if (stored?.startsWith(prefix)) storage.removeItem(stored);
      });
      key = null;
      state = emptySession;
      for (const listener of listeners) listener();
    },
  };
}

export type ClaraSession = ReturnType<typeof createClaraSession>;
