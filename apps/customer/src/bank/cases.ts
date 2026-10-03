import type { Case, CaseStage } from "./types";

export const caseSteps = ["opened", "assigned", "review", "resolved"] as const;
export type CaseStep = (typeof caseSteps)[number];
export type StepState = "done" | "now" | "todo";

const reached: Record<CaseStage, number> = { opened: 0, assigned: 1, in_review: 2, resolved: 3, closed: 3 };

export function isOpen(item: Pick<Case, "stage">): boolean {
  return reached[item.stage] < reached.resolved;
}

export function stepOf(item: Pick<Case, "stage">): CaseStep {
  return caseSteps[reached[item.stage]] ?? "opened";
}

export function stepsOf(item: Case): { step: CaseStep; state: StepState; at: string | null }[] {
  const current = reached[item.stage];
  const dates = [item.creation_date, item.assignment_date, item.first_response_date, item.resolution_date ?? item.closing_date];
  return caseSteps.map((step, index) => ({
    step,
    state: index < current || current === reached.resolved ? "done" : index === current ? "now" : "todo",
    at: index <= current ? (dates[index] ?? null) : null,
  }));
}

export function caseOfTransaction(cases: readonly Case[], transactionId: string): Case | undefined {
  return cases.find((item) => item.transaction_id === transactionId && isOpen(item));
}
