import { useEffect, useState } from "react";

import { clock } from "../../chat/services";
import { COMPOSING_AFTER_MS, nextPhase, phaseWake, startPhase, workingOf, type Phase, type Working } from "./working";

function useWakeAt(at: number | null) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (at === null) return;
    const timer = setTimeout(() => tick((count) => count + 1), Math.max(0, at - clock.now()));
    return () => clearTimeout(timer);
  }, [at]);
}

export function useWorkingPhase(thinking: boolean): Phase {
  const [phase, setPhase] = useState<Phase>(() => startPhase(thinking, clock.now()));
  const next = nextPhase(phase, thinking, clock.now());
  if (next !== phase) setPhase(next);
  useWakeAt(phaseWake(next, thinking));
  return next;
}

export function useWorking(status: string | null, statusAt: number | null): Working {
  useWakeAt(statusAt === null ? null : statusAt + COMPOSING_AFTER_MS);
  return workingOf(status, statusAt, clock.now());
}
