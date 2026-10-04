import { describe, expect, it } from "vitest";

import { ARRIVAL_MS, COMPOSING_AFTER_MS, MIN_WORKING_MS, nextPhase, phaseWake, startPhase, workingOf } from "./working";

describe("clara at work", () => {
  it("works while the turn runs and holds at least its minimum before the reply arrives", () => {
    const working = nextPhase(startPhase(false, 0), true, 1000);
    expect(working).toEqual({ kind: "working", since: 1000 });

    const early = nextPhase(working, false, 1000 + MIN_WORKING_MS - 1);
    expect(early).toBe(working);
    expect(phaseWake(early, false)).toBe(1000 + MIN_WORKING_MS);

    const arriving = nextPhase(early, false, 1000 + MIN_WORKING_MS);
    expect(arriving).toEqual({ kind: "arriving", until: 1000 + MIN_WORKING_MS + ARRIVAL_MS });
    expect(nextPhase(arriving, false, 1000 + MIN_WORKING_MS + ARRIVAL_MS)).toEqual({ kind: "idle" });
  });

  it("is already working when the chat reloads during a turn, and never plays an arrival on load", () => {
    expect(startPhase(true, 5)).toEqual({ kind: "working", since: 5 });
    expect(startPhase(false, 5)).toEqual({ kind: "idle" });
  });

  it("goes back to work when the customer asks again while the reply arrives", () => {
    expect(nextPhase({ kind: "arriving", until: 9000 }, true, 8000)).toEqual({ kind: "working", since: 8000 });
  });

  it("looks the way of the tool Clara reads, listens on memory and holds still while she composes", () => {
    expect(workingOf("movements", 0, 10)).toEqual({ face: "revisa", look: "sweep" });
    expect(workingOf("cards", 0, 10)).toEqual({ face: "revisa", look: "sweep" });
    expect(workingOf("cases", 0, 10)).toEqual({ face: "revisa", look: "warm" });
    expect(workingOf("policies", 0, 10)).toEqual({ face: "revisa", look: "read" });
    expect(workingOf("memory", 0, 10)).toEqual({ face: "escucha", look: undefined });
    expect(workingOf("movements", 0, COMPOSING_AFTER_MS)).toEqual({ face: "revisa", look: "still" });
    expect(workingOf(null, null, 10)).toEqual({ face: "revisa", look: "still" });
  });
});
