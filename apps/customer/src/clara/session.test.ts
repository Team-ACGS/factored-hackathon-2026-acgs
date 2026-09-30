import { describe, expect, it, vi } from "vitest";

import { claimOf } from "./claims";
import { cardAt, purchase } from "./fixtures";
import { cardLock, claimForTransaction, flaggedCharges, openClaims } from "./overlay";
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
    session.block(credit.product_id, "2026-09-29T10:31:00.000Z");

    const reloaded = opened(storage).session;
    const other = opened(storage, "customer-b").session;

    expect(reloaded.current().blocks).toEqual({ [credit.product_id]: "2026-09-29T10:31:00.000Z" });
    expect(other.current().blocks).toEqual({});
  });

  it("resets the demo without losing the seeded claim", () => {
    const { session } = opened();
    session.resolveSeeded(seeded);
    session.block(credit.product_id, "2026-09-29T10:31:00.000Z");
    session.addClaim(claimOf(purchase(credit, 1), "2026-09-29T10:40:00.000Z"));
    session.markReviewed("t-1");
    session.startTopic({ kind: "cards" });

    session.resetDemo();

    expect(session.current()).toEqual({ seeded, claims: [], blocks: {}, reviewed: [], topic: null });
  });

  it("forgets every customer on sign-out", () => {
    const { session, storage } = opened();
    session.resolveSeeded(seeded);
    opened(storage, "customer-b").session.markReviewed("t-1");
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

    session.markReviewed("t-1");

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps working in memory when the browser refuses storage", () => {
    const storage = memoryStorage();
    storage.setItem = () => {
      throw new Error("quota");
    };
    const { session } = opened(storage);

    session.block(credit.product_id, "2026-09-29T10:31:00.000Z");

    expect(cardLock(credit, session.current()).blocked).toBe(true);
  });
});

describe("bank overlay", () => {
  it("shows a block made in the chat on the card, with its time", () => {
    const { session } = opened();

    session.block(credit.product_id, "2026-09-29T10:31:00.000Z");

    expect(cardLock(credit, session.current())).toEqual({ blocked: true, since: "2026-09-29T10:31:00.000Z" });
    expect(cardLock(debit, session.current())).toEqual({ blocked: false, since: null });
  });

  it("shows a card the bank already blocked, without a time", () => {
    expect(cardLock({ ...credit, product_status: "Blocked" }, opened().session.current())).toEqual({
      blocked: true,
      since: null,
    });
  });

  it("marks the movement of a claim made in the chat and lists it before the seeded one", () => {
    const { session } = opened();
    const charge = purchase(credit, 1);
    const claim = claimOf(charge, "2026-09-29T10:40:00.000Z");
    session.resolveSeeded(seeded);

    session.addClaim(claim);

    expect(claimForTransaction(charge.transaction_id, session.current())).toEqual(claim);
    expect(claimForTransaction(seeded.transaction_id, session.current())).toEqual(seeded);
    expect(openClaims(session.current())).toEqual([claim, seeded]);
  });
});

describe("flagged charges", () => {
  const flagged = purchase(credit, -1, { fraud_score: "87.00", channel: "Web" });
  const older = purchase(credit, -0.5, { fraud_score: "31.00" });
  const low = purchase(credit, -2, { fraud_score: "30.00" });
  const unscored = purchase(credit, -2, { fraud_score: null });

  it("lists charges the bank scored above 30, newest first", () => {
    const { session } = opened();
    expect(flaggedCharges([older, low, flagged, unscored], [credit], session.current())).toEqual([flagged, older]);
  });

  it("drops a charge once reviewed and every charge of a blocked card", () => {
    const { session } = opened();
    session.markReviewed(flagged.transaction_id);
    expect(flaggedCharges([flagged, older], [credit], session.current())).toEqual([older]);

    session.block(credit.product_id, "2026-09-29T10:31:00.000Z");
    expect(flaggedCharges([flagged, older], [credit], session.current())).toEqual([]);
  });
});
