import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/http";
import { createQueryClient } from "../api/query-client";
import type { BankApi } from "../bank/api";
import { createBankQueries } from "../bank/queries";
import type { CardPage, Profile } from "../bank/types";
import { cardAt, purchase } from "./fixtures";
import { createSeededResolver } from "./seeded";
import { createClaraSession, memoryStorage } from "./session";

vi.hoisted(() => {
  Object.assign(globalThis, { window: {} });
});

const debit = cardAt("Tarjeta Débito");
const profile: Profile = { country: "MX", language: "es", setup_completed: true };

function page(transactions: CardPage["transactions"]): CardPage {
  return { card: debit, transactions, next_cursor: null, server_time: "2026-09-29T12:00:00.000Z" };
}

function world() {
  const api = {
    profile: vi.fn<BankApi["profile"]>(),
    setup: vi.fn<BankApi["setup"]>(),
    cards: vi.fn<BankApi["cards"]>().mockResolvedValue([debit]),
    card: vi.fn<BankApi["card"]>(),
    transaction: vi.fn<BankApi["transaction"]>(),
    add: vi.fn<BankApi["add"]>(),
  } satisfies BankApi;
  const session = createClaraSession(memoryStorage());
  session.open("customer-a");
  const resolve = createSeededResolver(createBankQueries(api, { now: Date.now, sync: vi.fn() }), session);
  return { api, session, resolve, client: createQueryClient() };
}

describe("resolveSeededClaim", () => {
  it("leaves the claim unresolved without failing when the ledger cannot be read, and retries next time", async () => {
    const { api, session, resolve, client } = world();
    const charge = purchase(debit, 10);
    api.card.mockRejectedValueOnce(new ApiError(503));

    await expect(resolve(client, profile)).resolves.toBeUndefined();
    expect(session.current().seeded).toBeUndefined();

    api.card.mockResolvedValue(page([charge]));
    await resolve(client, profile);
    expect(session.current().seeded?.transaction_id).toBe(charge.transaction_id);
  });

  it("remembers that no movement qualifies and does not read the ledger again", async () => {
    const { api, session, resolve, client } = world();
    api.card.mockResolvedValue(page([purchase(debit, 1)]));

    await resolve(client, profile);
    await resolve(createQueryClient(), profile);

    expect(session.current().seeded).toBeNull();
    expect(api.card).toHaveBeenCalledTimes(1);
  });
});
