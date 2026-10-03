import { describe, expect, it } from "vitest";

import { caseOfTransaction, isOpen, stepOf, stepsOf } from "./cases";
import type { Case } from "./types";

const claim: Case = {
  complaint_id: "c1",
  case_id: "CLR-2026-182061",
  type: "claim",
  stage: "in_review",
  creation_date: "2026-09-14T15:00:00.000Z",
  assignment_date: "2026-09-16T15:00:00.000Z",
  first_response_date: "2026-09-20T15:00:00.000Z",
  transaction_id: "t1",
  product_id: "p1",
};

describe("cases from the bank", () => {
  it("walks the steps the bank recorded and marks the current one", () => {
    expect(stepsOf(claim)).toEqual([
      { step: "opened", state: "done", at: claim.creation_date },
      { step: "assigned", state: "done", at: claim.assignment_date },
      { step: "review", state: "now", at: claim.first_response_date },
      { step: "resolved", state: "todo", at: null },
    ]);
    expect(stepOf(claim)).toBe("review");
  });

  it("marks every step done once the case is resolved or closed", () => {
    const closed = { ...claim, stage: "closed" as const, closing_date: "2026-09-28T15:00:00.000Z" };

    expect(stepsOf(closed).map((step) => step.state)).toEqual(["done", "done", "done", "done"]);
    expect(stepsOf(closed).at(-1)?.at).toBe(closed.closing_date);
    expect(isOpen(closed)).toBe(false);
  });

  it("finds the open case of a movement and ignores closed ones", () => {
    expect(caseOfTransaction([claim], "t1")).toBe(claim);
    expect(caseOfTransaction([{ ...claim, stage: "resolved" }], "t1")).toBeUndefined();
    expect(caseOfTransaction([claim], "t2")).toBeUndefined();
  });
});
