import { describe, expect, it } from "vitest";

import { claimSteps, findSeededClaim, seededCard } from "./claims";
import { cardAt, DAY, purchase } from "./fixtures";

const debit = cardAt("Tarjeta Débito");
const credit = cardAt("Tarjeta Crédito");

describe("seeded claim", () => {
  it("sits on the debit card when there is one, else on the first card", () => {
    expect(seededCard([credit, debit])).toBe(debit);
    expect(seededCard([credit])).toBe(credit);
    expect(seededCard([])).toBeUndefined();
  });

  it("takes the newest plain approved in-store purchase at least a week older than the account", () => {
    const tooRecent = purchase(debit, 3);
    const chosen = purchase(debit, 10);
    const older = purchase(debit, 20);

    const claim = findSeededClaim(debit, [tooRecent, chosen, older], "MX");

    expect(claim?.transaction_id).toBe(chosen.transaction_id);
    expect(claim?.merchant_name).toBe(chosen.merchant_name);
    expect(claim?.amount).toBe(chosen.amount);
  });

  it.each([
    ["pending", { transaction_status: "Pending" as const }],
    ["reversed", { transaction_status: "Reversed" as const }],
    ["declined", { transaction_status: "Declined" as const }],
    ["scored high by the bank", { fraud_score: "30.01" }],
    ["abroad", { transaction_country: "US" }],
    ["online", { channel: "Web" }],
  ])("never picks a movement that is %s", (_, overrides) => {
    const skipped = purchase(debit, 10, overrides);
    const plain = purchase(debit, 15);

    expect(findSeededClaim(debit, [skipped, plain], "MX")?.transaction_id).toBe(plain.transaction_id);
  });

  it("keeps the same id and dates across reloads and as new purchases arrive", () => {
    const chosen = purchase(debit, 12);
    const first = findSeededClaim(debit, [chosen], "MX");
    const added = purchase(debit, -30);

    const later = findSeededClaim(debit, [added, chosen], "MX");

    expect(later).toEqual(first);
    expect(first?.claim_id).toMatch(/^CLR-\d{4}-\d{6}$/);
  });

  it("is absent when no movement qualifies", () => {
    expect(findSeededClaim(debit, [purchase(debit, 2)], "MX")).toBeNull();
  });
});

describe("claim steps", () => {
  const claim = findSeededClaim(debit, [purchase(debit, 20)], "MX");
  if (!claim) throw new Error("no claim");
  const openedAt = Date.parse(claim.opened_at);

  it("is under review once six days have passed since it opened", () => {
    expect(claimSteps(claim, openedAt + 6 * DAY).map((step) => step.state)).toEqual(["done", "done", "now"]);
  });

  it("shows a claim opened today as just opened", () => {
    expect(claimSteps(claim, openedAt + 1000).map((step) => step.state)).toEqual(["now", "todo", "todo"]);
  });

  it("dates each step from the opening", () => {
    const [opened, assigned, review] = claimSteps(claim, openedAt + 7 * DAY);
    expect(opened?.at).toBe(claim.opened_at);
    expect(Date.parse(assigned?.at ?? "") - openedAt).toBe(2 * DAY);
    expect(Date.parse(review?.at ?? "") - openedAt).toBe(6 * DAY);
  });
});
