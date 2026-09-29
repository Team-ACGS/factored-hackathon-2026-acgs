import { describe, expect, it } from "vitest";

import { appendPage, prepend } from "./ledger";
import type { Transaction } from "./types";

function transaction(id: string): Transaction {
  return { transaction_id: id } as Transaction;
}

const ids = (items: readonly Transaction[]) => items.map((item) => item.transaction_id);

describe("ledger", () => {
  it("appends a page and keeps the cursor of the last one", () => {
    const ledger = appendPage({ transactions: [transaction("a")], nextCursor: "c1" }, [transaction("b")], null);

    expect(ids(ledger.transactions)).toEqual(["a", "b"]);
    expect(ledger.nextCursor).toBeNull();
  });

  it("does not repeat a transaction added before its page arrives", () => {
    const withAdded = prepend({ transactions: [transaction("a")], nextCursor: "c1" }, transaction("new"));

    const ledger = appendPage(withAdded, [transaction("new"), transaction("b")], null);

    expect(ids(ledger.transactions)).toEqual(["new", "a", "b"]);
  });

  it("puts an added transaction at the top once, even when retried", () => {
    const once = prepend({ transactions: [transaction("a")], nextCursor: null }, transaction("new"));

    expect(ids(prepend(once, transaction("new")).transactions)).toEqual(["new", "a"]);
  });
});
