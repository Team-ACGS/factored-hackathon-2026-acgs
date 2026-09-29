import type { Transaction } from "./types";

export interface Ledger {
  transactions: readonly Transaction[];
  nextCursor: string | null;
}

export function appendPage(ledger: Ledger, page: readonly Transaction[], nextCursor: string | null): Ledger {
  const known = new Set(ledger.transactions.map((transaction) => transaction.transaction_id));
  return {
    transactions: [...ledger.transactions, ...page.filter((transaction) => !known.has(transaction.transaction_id))],
    nextCursor,
  };
}

export function prepend(ledger: Ledger, added: Transaction): Ledger {
  return {
    ...ledger,
    transactions: [
      added,
      ...ledger.transactions.filter((transaction) => transaction.transaction_id !== added.transaction_id),
    ],
  };
}
