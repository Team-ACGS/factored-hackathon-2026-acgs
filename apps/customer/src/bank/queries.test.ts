import { InfiniteQueryObserver, MutationObserver, QueryObserver, type QueryKey } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/http";
import { createQueryClient, minutes } from "../api/query-client";
import { mintId, type Clock } from "../chat/clock";
import type { BankApi } from "./api";
import type { Ledger } from "./ledger";
import { bankKeys, createBankQueries, ensureLedgerUntil } from "./queries";
import type { Card, CardPage, Setup, Transaction } from "./types";

vi.hoisted(() => {
  Object.assign(globalThis, { window: {} });
});

const now = Date.parse("2026-09-29T12:00:00.000Z");
const card = { product_id: "card-1" } as Card;

function row(id: string): Transaction {
  return { transaction_id: id, product_id: "card-1", transaction_date: "2026-09-28T10:00:00.000Z" } as Transaction;
}

function page(ids: string[], nextCursor: string | null): CardPage {
  return { card, transactions: ids.map(row), next_cursor: nextCursor, server_time: "2026-09-29T12:00:05.000Z" };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function world() {
  const api = {
    profile: vi.fn<BankApi["profile"]>(),
    setup: vi.fn<BankApi["setup"]>(),
    cards: vi.fn<BankApi["cards"]>(),
    card: vi.fn<BankApi["card"]>(),
    transaction: vi.fn<BankApi["transaction"]>(),
    add: vi.fn<BankApi["add"]>(),
  } satisfies BankApi;
  const clock = { now: () => now, sync: vi.fn<Clock["sync"]>() };
  const client = createQueryClient();
  const queries = createBankQueries(api, clock);
  const ledger = () => client.getQueryData<Ledger>(bankKeys.ledger("card-1"));
  const ids = () => (ledger()?.pages ?? []).flatMap((item) => item.transactions).map((entry) => entry.transaction_id);
  const invalidated = (key: QueryKey) => client.getQueryState(key)?.isInvalidated;
  const settled = () =>
    vi.waitFor(() => {
      expect(client.isMutating()).toBe(0);
      expect(client.isFetching()).toBe(0);
    });

  async function watchLedger(pages: CardPage[]) {
    const cursors = [null, ...pages.map((item) => item.next_cursor)];
    api.card.mockImplementation((_, cursor) => Promise.resolve(pages[cursors.indexOf(cursor ?? null)] ?? page([], null)));
    const observer = new InfiniteQueryObserver(client, queries.ledger("card-1"));
    observer.subscribe(() => undefined);
    await vi.waitFor(() => expect(ledger()?.pages).toHaveLength(1));
    for (let loaded = 1; loaded < pages.length; loaded++) await observer.fetchNextPage();
    return observer;
  }

  function add() {
    const response = deferred<Transaction>();
    const transactionId = mintId(clock);
    api.add.mockImplementationOnce(() => response.promise);
    const done = new MutationObserver(client, queries.add(client, "card-1")).mutate({
      transaction_id: transactionId,
      type: "normal",
    });
    return { transactionId, response, done };
  }

  return { api, clock, client, queries, ledger, ids, invalidated, settled, watchLedger, add };
}

describe("bank queries", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("pages the ledger with each returned cursor and syncs the clock from every page", async () => {
    const { api, clock, ids, watchLedger } = world();

    const observer = await watchLedger([page(["a", "b"], "c1"), page(["c"], null)]);

    expect(api.card.mock.calls).toEqual([
      ["card-1", null],
      ["card-1", "c1"],
    ]);
    expect(ids()).toEqual(["a", "b", "c"]);
    expect(observer.getCurrentResult().hasNextPage).toBe(false);
    expect(clock.sync).toHaveBeenCalledTimes(2);
    expect(clock.sync.mock.calls[0]?.[0]).toBe("2026-09-29T12:00:05.000Z");
  });

  it("serves a screen visited half an hour ago from the cache without a request", async () => {
    vi.useFakeTimers();
    const { api, client, queries } = world();
    api.card.mockResolvedValue(page(["a"], null));
    api.cards.mockResolvedValue([card]);

    await client.ensureInfiniteQueryData(queries.ledger("card-1"));
    await client.ensureQueryData(queries.cards());
    vi.advanceTimersByTime(minutes(30));
    await client.ensureInfiniteQueryData(queries.ledger("card-1"));
    await client.ensureQueryData(queries.cards());

    expect(api.card).toHaveBeenCalledTimes(1);
    expect(api.cards).toHaveBeenCalledTimes(1);
  });

  it("asks once when a read fails, leaving retries to the http client", async () => {
    const { api, client, queries } = world();
    api.profile.mockRejectedValue(new ApiError(503));

    const observer = new QueryObserver(client, queries.profile());
    observer.subscribe(() => undefined);

    await vi.waitFor(() => expect(observer.getCurrentResult().status).toBe("error"));
    expect(api.profile).toHaveBeenCalledTimes(1);
  });

  it("shows an add at the top of the first page at once, dated by its id", async () => {
    const { ledger, ids, watchLedger, add } = world();
    await watchLedger([page(["a", "b"], "c1"), page(["c"], null)]);

    const { transactionId } = add();

    await vi.waitFor(() => expect(ids()).toEqual([transactionId, "a", "b", "c"]));
    expect(ledger()?.pages[0]?.transactions[0]).toEqual({
      transaction_id: transactionId,
      transaction_date: "2026-09-29T12:00:00.000Z",
      pending: true,
    });
    expect(ledger()?.pages[1]?.transactions.map((entry) => entry.transaction_id)).toEqual(["c"]);
  });

  it("keeps an add's placeholder when a ledger refetch started before it answers late", async () => {
    const { api, client, ids, settled, watchLedger, add } = world();
    await watchLedger([page(["a"], null)]);
    const late = deferred<CardPage>();
    api.card.mockImplementationOnce(() => late.promise);
    void client.invalidateQueries({ queryKey: bankKeys.ledger("card-1") });
    await vi.waitFor(() => expect(api.card).toHaveBeenCalledTimes(2));

    const added = add();
    await vi.waitFor(() => expect(ids()).toEqual([added.transactionId, "a"]));
    late.resolve(page(["a"], null));
    await vi.waitFor(() => expect(client.isFetching()).toBe(0));

    expect(ids()).toEqual([added.transactionId, "a"]);
    added.response.resolve(row(added.transactionId));
    await settled();
  });

  it("removes only the failed add's placeholder and keeps the other add in flight", async () => {
    const { ids, watchLedger, add } = world();
    await watchLedger([page(["a", "b"], "c1"), page(["c"], null)]);
    const failing = add();
    const pending = add();
    await vi.waitFor(() => expect(ids()).toHaveLength(5));

    failing.response.reject(new ApiError(400));

    await expect(failing.done).rejects.toEqual(new ApiError(400));
    expect(ids()).toEqual([pending.transactionId, "a", "b", "c"]);
  });

  it("swaps the placeholder for the stored row and does not repeat it once the refetch returns it", async () => {
    const { api, ledger, ids, settled, watchLedger, add } = world();
    await watchLedger([page(["a", "b"], "c1"), page(["c"], null)]);
    const added = add();
    await vi.waitFor(() => expect(ids()).toHaveLength(4));
    api.card.mockClear();
    api.card.mockImplementation((_productId, cursor) =>
      Promise.resolve(cursor === null ? page([added.transactionId, "a"], "c2") : page(["b", "c"], null)),
    );

    added.response.resolve(row(added.transactionId));
    await added.done;
    await settled();

    expect(ids()).toEqual([added.transactionId, "a", "b", "c"]);
    expect(ledger()?.pages[0]?.transactions[0]).toEqual(row(added.transactionId));
    expect(api.card.mock.calls).toEqual([
      ["card-1", null],
      ["card-1", "c2"],
    ]);
  });

  it("invalidates only that card's ledger and the card list after an add", async () => {
    const { api, client, invalidated, settled, add } = world();
    client.setQueryData(bankKeys.ledger("card-1"), { pages: [page(["a"], null)], pageParams: [null] });
    client.setQueryData(bankKeys.ledger("card-2"), { pages: [page(["z"], null)], pageParams: [null] });
    client.setQueryData(bankKeys.profile(), { country: "MX", language: "es", setup_completed: true });
    client.setQueryData(bankKeys.cards(), [card]);
    client.setQueryData(bankKeys.transaction("card-1", "a"), row("a"));
    const added = add();

    added.response.resolve(row(added.transactionId));
    await added.done;
    await settled();

    expect(invalidated(bankKeys.ledger("card-1"))).toBe(true);
    expect(invalidated(bankKeys.ledger("card-2"))).toBe(false);
    expect(invalidated(bankKeys.profile())).toBe(false);
    expect(invalidated(bankKeys.cards())).toBe(true);
    expect(invalidated(bankKeys.transaction("card-1", "a"))).toBe(false);
    expect(api.card).not.toHaveBeenCalled();
  });

  it("waits for the last add in flight on the card before refetching its ledger", async () => {
    const { api, ledger, ids, settled, watchLedger, add } = world();
    await watchLedger([page(["a"], null)]);
    const first = add();
    const second = add();
    await vi.waitFor(() => expect(ids()).toHaveLength(3));
    api.card.mockClear();

    first.response.resolve(row(first.transactionId));
    await first.done;

    expect(api.card).not.toHaveBeenCalled();
    expect(ids()).toEqual([second.transactionId, first.transactionId, "a"]);
    expect(ledger()?.pages[0]?.transactions[1]).toEqual(row(first.transactionId));

    api.card.mockResolvedValue(page([second.transactionId, first.transactionId, "a"], null));
    second.response.resolve(row(second.transactionId));
    await second.done;
    await settled();

    expect(api.card).toHaveBeenCalledTimes(1);
    expect(ids()).toEqual([second.transactionId, first.transactionId, "a"]);
  });

  describe("setup", () => {
    const before = { country: null, language: null, setup_completed: false };
    const done = { country: "MX", language: "pt-BR", setup_completed: true } as const;

    function setupWorld() {
      const test = world();
      test.client.setQueryData(bankKeys.profile(), before);
      test.client.setQueryData(bankKeys.cards(), []);
      test.client.setQueryData(bankKeys.ledger("card-1"), { pages: [page(["a"], null)], pageParams: [null] });
      const observer = new MutationObserver(test.client, test.queries.setup(test.client));
      const run = () => observer.mutate({ country: "MX", language: "es" });
      return { ...test, observer, run };
    }

    it("stores the created profile at once and refreshes the cards, nothing else", async () => {
      const { api, client, invalidated, run } = setupWorld();
      const cases = [{ kind: "fresh_hold", transaction: row("a") }] as Setup["cases"];
      api.setup.mockResolvedValue({ profile: done, cases });

      await expect(run()).resolves.toEqual({ profile: done, cases });

      expect(client.getQueryData(bankKeys.profile())).toEqual(done);
      expect(api.profile).not.toHaveBeenCalled();
      expect(invalidated(bankKeys.cards())).toBe(true);
      expect(invalidated(bankKeys.ledger("card-1"))).toBe(false);
    });

    it("reads the stored profile when setup was already done, with no cases to guide", async () => {
      const { api, client, invalidated, run } = setupWorld();
      api.setup.mockRejectedValue(new ApiError(409));
      api.profile.mockResolvedValue(done);

      await expect(run()).resolves.toEqual({ profile: done, cases: null });

      expect(client.getQueryData(bankKeys.profile())).toEqual(done);
      expect(invalidated(bankKeys.cards())).toBe(true);
    });

    it("ends in an error, not pending, when the profile cannot be read after a conflict", async () => {
      const { api, client, observer, run } = setupWorld();
      api.setup.mockRejectedValue(new ApiError(409));
      api.profile.mockRejectedValue(new ApiError(503));

      await expect(run()).rejects.toEqual(new ApiError(503));

      expect(observer.getCurrentResult().status).toBe("error");
      expect(client.getQueryData(bankKeys.profile())).toEqual(before);
    });

    it("changes nothing when setup fails", async () => {
      const { api, client, invalidated, run } = setupWorld();
      api.setup.mockRejectedValue(new ApiError(500));

      await expect(run()).rejects.toEqual(new ApiError(500));

      expect(api.profile).not.toHaveBeenCalled();
      expect(client.getQueryData(bankKeys.profile())).toEqual(before);
      expect(invalidated(bankKeys.cards())).toBe(false);
    });
  });
});

describe("ensureLedgerUntil", () => {
  function pagedWorld() {
    const shared = world();
    const pages = [page(["a", "b"], "c1"), page(["c", "d"], "c2"), page(["e"], null)];
    const cursors = [null, "c1", "c2"];
    shared.api.card.mockImplementation((_, cursor) => Promise.resolve(pages[cursors.indexOf(cursor ?? null)] ?? page([], null)));
    return shared;
  }

  it("fetches pages only until the wanted row is loaded", async () => {
    const { api, client, queries, ids } = pagedWorld();

    const entries = await ensureLedgerUntil(client, queries.ledger("card-1"), (rows) =>
      rows.some((entry) => entry.transaction_id === "c"),
    );

    expect(entries.map((entry) => entry.transaction_id)).toEqual(["a", "b", "c", "d"]);
    expect(api.card).toHaveBeenCalledTimes(2);
    expect(ids()).toEqual(["a", "b", "c", "d"]);
  });

  it("stops at the last page when nothing matches", async () => {
    const { api, client, queries } = pagedWorld();

    const entries = await ensureLedgerUntil(client, queries.ledger("card-1"), () => false);

    expect(entries).toHaveLength(5);
    expect(api.card).toHaveBeenCalledTimes(3);
  });

  it("reads nothing more when the cached pages already hold the row", async () => {
    const { api, client, queries } = pagedWorld();
    await client.ensureInfiniteQueryData(queries.ledger("card-1"));

    await ensureLedgerUntil(client, queries.ledger("card-1"), (rows) => rows.length > 0);

    expect(api.card).toHaveBeenCalledTimes(1);
  });

  it("fails when a later page cannot be read", async () => {
    const { api, client, queries } = pagedWorld();
    api.card.mockImplementation((_, cursor) =>
      cursor ? Promise.reject(new ApiError(503)) : Promise.resolve(page(["a"], "c1")),
    );

    await expect(ensureLedgerUntil(client, queries.ledger("card-1"), () => false)).rejects.toEqual(new ApiError(503));
  });
});
