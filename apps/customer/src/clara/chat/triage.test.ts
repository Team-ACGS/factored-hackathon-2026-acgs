import { describe, expect, it } from "vitest";

import type { Transaction } from "../../bank/types";
import { claimOf } from "../claims";
import { cardAt, DAY, purchase, setupAt } from "../fixtures";
import { createClaraSession, memoryStorage } from "../session";
import type { Context } from "./insight";
import { afterHistory, flaggedCandidate, recentList, triage } from "./triage";

const credit = cardAt("Tarjeta Crédito");
const debit = cardAt("Tarjeta Débito", setupAt + 1);

function context(entries: Transaction[], change?: (session: ReturnType<typeof createClaraSession>) => void): Context {
  const session = createClaraSession(memoryStorage());
  session.open("customer-a");
  change?.(session);
  return { profile: { country: "MX" }, cards: [credit, debit], entries, session: session.current(), now: setupAt };
}

const outcomeOf = (tx: Transaction, entries: Transaction[] = [tx], change?: Parameters<typeof context>[1]) =>
  triage(tx, context(entries, change)).outcome;

describe("triage precedence", () => {
  it("explains a reversed charge as refunded and a declined one as never charged, whatever the signals", () => {
    expect(outcomeOf(purchase(credit, 3, { transaction_status: "Reversed", fraud_score: "90.00" }))).toBe("refunded");
    expect(outcomeOf(purchase(credit, 3, { transaction_status: "Declined", channel: "Web" }))).toBe("neverCharged");
  });

  it("calls a pending charge a hold only up to 7 days", () => {
    expect(outcomeOf(purchase(credit, 7, { transaction_status: "Pending" }))).toBe("hold");

    const stale = purchase(credit, 98, { transaction_status: "Pending" });
    const verdict = triage(stale, context([stale]));
    expect(verdict.outcome).toBe("question");
    expect(verdict.stale).toBe(true);
  });

  it("treats an old pending charge with merchant history as applied and shows the history", () => {
    const earlier = purchase(debit, 60, { merchant_name: "UBER EATS" });
    const stale = purchase(credit, 40, { merchant_name: "Uber Eats", transaction_status: "Pending" });

    const verdict = triage(stale, context([stale, earlier]));

    expect(verdict.outcome).toBe("history");
    expect(verdict.stale).toBe(true);
    expect(verdict.prior).toEqual([earlier]);
  });

  it("shows merchant history on any card before looking at signals", () => {
    const earlier = purchase(debit, 30, { merchant_name: "AMAZON MX" });
    const flagged = purchase(credit, 2, { merchant_name: "AMAZON MX", fraud_score: "80.00" });
    expect(outcomeOf(flagged, [flagged, earlier])).toBe("history");
    expect(afterHistory(flagged, context([flagged, earlier]))).toBe("protect");
  });

  it.each([
    ["a bank score above 30", { fraud_score: "30.01" }],
    ["a country other than the profile's", { transaction_country: "US" }],
    ["an online purchase when the customer only buys in store", { channel: "Web" }],
  ])("protects on %s", (_, overrides) => {
    const usual = purchase(credit, 20);
    const charge = purchase(credit, 1, overrides);
    expect(outcomeOf(charge, [charge, usual])).toBe("protect");
  });

  it("asks the one question when nothing explains the charge", () => {
    const charge = purchase(credit, 1, { fraud_score: "30.00" });
    expect(outcomeOf(charge, [charge, purchase(credit, 20)])).toBe("question");
    expect(afterHistory(charge, context([charge]))).toBe("question");
  });

  it("goes to the case of a blocked card instead of a second block, and to the claim of a claimed charge", () => {
    const charge = purchase(credit, 1, { fraud_score: "90.00" });
    expect(outcomeOf(charge, [charge], (session) => session.block(credit.product_id, "2026-09-01T10:00:00.000Z"))).toBe(
      "blocked",
    );
    expect(outcomeOf(charge, [charge], (session) => session.addClaim(claimOf(charge, "2026-09-01T10:00:00.000Z")))).toBe(
      "inClaim",
    );
  });

  it("remembers a charge the customer said was theirs", () => {
    const charge = purchase(credit, 1, { fraud_score: "90.00" });
    expect(outcomeOf(charge, [charge], (session) => session.recognize(charge.transaction_id))).toBe("recognized");
  });
});

describe("flagged candidate", () => {
  it("is the newest charge to protect within 90 days, and joins the recent list", () => {
    const old = purchase(credit, 100, { fraud_score: "95.00" });
    const flagged = purchase(credit, 12, { fraud_score: "70.00" });
    const newer = Array.from({ length: 6 }, (_, index) => purchase(debit, index + 1));
    const ctx = context([old, flagged, ...newer]);

    expect(flaggedCandidate(ctx)).toBe(flagged);
    const list = recentList(ctx, flagged, 6);
    expect(list).toHaveLength(6);
    expect(list).toContain(flagged);
    expect(list.map((entry) => entry.transaction_date)).toEqual(
      [...list].map((entry) => entry.transaction_date).sort().reverse(),
    );
  });

  it("is gone once the card is blocked", () => {
    const flagged = purchase(credit, 1, { fraud_score: "70.00" });
    expect(flaggedCandidate(context([flagged], (session) => session.block(credit.product_id, new Date(setupAt - DAY).toISOString())))).toBe(
      undefined,
    );
  });
});
