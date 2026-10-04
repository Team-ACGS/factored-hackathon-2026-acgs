import type { EntityState, WorkingLook } from "@clara/ui/lib/entity";

export const MIN_WORKING_MS = 800;
export const ARRIVAL_MS = 1800;
export const COMPOSING_AFTER_MS = 1500;

export type Phase =
  | { kind: "idle" }
  | { kind: "working"; since: number }
  | { kind: "arriving"; until: number };

export function startPhase(thinking: boolean, now: number): Phase {
  return thinking ? { kind: "working", since: now } : { kind: "idle" };
}

export function nextPhase(phase: Phase, thinking: boolean, now: number): Phase {
  if (thinking) return phase.kind === "working" ? phase : { kind: "working", since: now };
  if (phase.kind === "working") {
    return now - phase.since < MIN_WORKING_MS ? phase : { kind: "arriving", until: now + ARRIVAL_MS };
  }
  if (phase.kind === "arriving" && now >= phase.until) return { kind: "idle" };
  return phase;
}

export function phaseWake(phase: Phase, thinking: boolean): number | null {
  if (phase.kind === "working" && !thinking) return phase.since + MIN_WORKING_MS;
  return phase.kind === "arriving" ? phase.until : null;
}

const looks: Record<string, WorkingLook> = {
  movements: "sweep",
  cards: "sweep",
  cases: "warm",
  policies: "read",
};

export interface Working {
  face: EntityState;
  look: WorkingLook | undefined;
}

export function workingOf(status: string | null, statusAt: number | null, now: number): Working {
  const fresh = status !== null && statusAt !== null && now - statusAt < COMPOSING_AFTER_MS;
  if (!fresh) return { face: "revisa", look: "still" };
  if (status === "memory") return { face: "escucha", look: undefined };
  return { face: "revisa", look: looks[status] ?? "still" };
}
