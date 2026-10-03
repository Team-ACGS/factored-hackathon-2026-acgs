import type { Topic } from "./topics";

export interface ClaraSessionState {
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
    return { topic: stored.topic ?? null };
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
    startTopic(topic: Topic) {
      update((current) => ({ ...current, topic }));
    },
    takeTopic(): Topic | null {
      const { topic } = state;
      if (topic) update((current) => ({ ...current, topic: null }));
      return topic;
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
