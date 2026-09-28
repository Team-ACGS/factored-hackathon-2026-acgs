import { v7 } from "uuid";

export interface Clock {
  now(): number;
  sync(serverTime: string, requestedAt: number, receivedAt: number): void;
}

export function createClock(local: () => number = Date.now): Clock {
  let offset = 0;
  return {
    now: () => local() + offset,
    sync(serverTime, requestedAt, receivedAt) {
      const server = Date.parse(serverTime);
      if (!Number.isNaN(server)) {
        offset = server - (requestedAt + receivedAt) / 2;
      }
    },
  };
}

export function mintId(clock: Clock): string {
  return v7({ msecs: Math.round(clock.now()) });
}

export function idTime(id: string): number {
  return parseInt(id.replace(/-/g, "").slice(0, 12), 16);
}
