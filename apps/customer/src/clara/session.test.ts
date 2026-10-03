import { describe, expect, it, vi } from "vitest";

import { claimOf } from "./claims";
import { cardAt, purchase } from "./fixtures";
import { claimForTransaction, flaggedCharges, isBlocked, openClaims } from "./overlay";
import { createClaraSession, memoryStorage } from "./session";

const debit = cardAt("Tarjeta Débito");
const credit = cardAt("Tarjeta Crédito", Date.now(), { product_number: "**** 4821" });
const seeded = claimOf(purchase(debit, 10), "2026-08-23T15:00:00.000Z");

function opened(storage = memoryStorage(), customerId = "customer-a") {
  const session = createClaraSession(storage);
  session.open(customerId);
  return { session, storage };
}

describe("clara session", () => {
  it("survives a reload of the same customer and is separate per customer", () => {
    const { session, storage } = opened();
    session.resolveSeeded(seeded);

    expect(opened(storage).session.current().seeded).toEqual(seeded);
    expect(opened(storage, "customer-b").session.current().seeded).toBeUndefined();
  });

  it("remembers across a reload that no seeded claim exists", () => {
    const { session, storage } = opened();
    session.resolveSeeded(null);

    expect(opened(storage).session.current().seeded).toBeNull();
  });

  it("forgets every customer on sign-out", () => {
    const { session, storage } = opened();
    session.resolveSeeded(seeded);
    opened(storage, "customer-b").session.startTopic({ kind: "cards" });
    storage.setItem("clara.locale", "es");

    session.clear();

    expect(session.current().seeded).toBeUndefined();
    expect(Array.from({ length: storage.length }, (_, index) => storage.key(index))).toEqual(["clara.locale"]);
  });

  it("hands a started topic to the chat exactly once", () => {
    const { session } = opened();
    session.startTopic({ kind: "unrecognized" });

    expect(session.takeTopic()).toEqual({ kind: "unrecognized" });
    expect(session.takeTopic()).toBeNull();
  });

  it("notifies the screens on every change", () => {
    const { session } = opened();
    const listener = vi.fn();
    session.subscribe(listener);

    session.startTopic({ kind: "cards" });

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps working in memory when the browser refuses storage", () => {
    const storage = memoryStorage();
    storage.setItem = () => {
      throw new Error("quota");
    };
    const { session } = opened(storage);

    session.resolveSeeded(seeded);

    expect(session.current().seeded).toEqual(seeded);
  });
});

describe("bank overlay", () => {
  it("shows a card blocked only when the bank blocked it", () => {
    expect(isBlocked({ ...credit, product_status: "Blocked" })).toBe(true);
    expect(isBlocked(credit)).toBe(false);
  });

  it("marks the movement of the seeded claim", () => {
    const { session } = opened();
    session.resolveSeeded(seeded);

    expect(claimForTransaction(seeded.transaction_id, session.current())).toEqual(seeded);
    expect(openClaims(session.current())).toEqual([seeded]);
  });
});

describe("flagged charges", () => {
  const flagged = purchase(credit, -1, { fraud_score: "87.00", channel: "Web" });
  const older = purchase(credit, -0.5, { fraud_score: "31.00" });
  const low = purchase(credit, -2, { fraud_score: "30.00" });
  const unscored = purchase(credit, -2, { fraud_score: null });

  it("lists charges the bank scored above 30, newest first", () => {
    expect(flaggedCharges([older, low, flagged, unscored], [credit])).toEqual([flagged, older]);
  });

  it("drops every charge of a card the bank blocked", () => {
    expect(flaggedCharges([flagged, older], [{ ...credit, product_status: "Blocked" }])).toEqual([]);
  });
});
