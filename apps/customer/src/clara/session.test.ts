import { describe, expect, it, vi } from "vitest";

import { cardAt, purchase } from "./fixtures";
import { flaggedCharges, isBlocked } from "./overlay";
import { createClaraSession, memoryStorage } from "./session";

const credit = cardAt("Tarjeta Crédito", Date.now(), { product_number: "**** 4821" });

function opened(storage = memoryStorage(), customerId = "customer-a") {
  const session = createClaraSession(storage);
  session.open(customerId);
  return { session, storage };
}

describe("clara session", () => {
  it("survives a reload of the same customer and is separate per customer", () => {
    const { session, storage } = opened();
    session.startTopic({ kind: "cards" });

    expect(opened(storage).session.current().topic).toEqual({ kind: "cards" });
    expect(opened(storage, "customer-b").session.current().topic).toBeNull();
  });

  it("forgets every customer on sign-out", () => {
    const { session, storage } = opened();
    session.startTopic({ kind: "unrecognized" });
    opened(storage, "customer-b").session.startTopic({ kind: "cards" });
    storage.setItem("clara.locale", "es");

    session.clear();

    expect(session.current().topic).toBeNull();
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

    session.startTopic({ kind: "cards" });

    expect(session.current().topic).toEqual({ kind: "cards" });
  });
});

describe("bank overlay", () => {
  it("shows a card blocked only when the bank blocked it", () => {
    expect(isBlocked({ ...credit, product_status: "Blocked" })).toBe(true);
    expect(isBlocked(credit)).toBe(false);
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
