import type { InfiniteData } from "@tanstack/react-query";

import type { Card, Transaction } from "./types";

export interface PendingTransaction {
  transaction_id: string;
  transaction_date: string;
  pending: true;
}

export type LedgerEntry = Transaction | PendingTransaction;

export interface LedgerPage {
  card: Card;
  transactions: LedgerEntry[];
  next_cursor: string | null;
  server_time: string;
}

export type Ledger = InfiniteData<LedgerPage, string | null>;

export function isPending(entry: LedgerEntry): entry is PendingTransaction {
  return "pending" in entry;
}

function mapFirstPage(ledger: Ledger, change: (page: LedgerPage) => LedgerPage): Ledger {
  const [first, ...rest] = ledger.pages;
  return first ? { ...ledger, pages: [change(first), ...rest] } : ledger;
}

export function withPlaceholder(ledger: Ledger | undefined, placeholder: PendingTransaction): Ledger | undefined {
  return (
    ledger &&
    mapFirstPage(ledger, (page) => ({ ...page, transactions: [placeholder, ...page.transactions] }))
  );
}

export function withoutPlaceholder(ledger: Ledger | undefined, transactionId: string): Ledger | undefined {
  return (
    ledger && {
      ...ledger,
      pages: ledger.pages.map((page) => ({
        ...page,
        transactions: page.transactions.filter(
          (entry) => !(isPending(entry) && entry.transaction_id === transactionId),
        ),
      })),
    }
  );
}

export function withAdded(ledger: Ledger | undefined, added: Transaction): Ledger | undefined {
  if (!ledger) return ledger;
  const listed = ledger.pages.some((page) =>
    page.transactions.some((entry) => entry.transaction_id === added.transaction_id),
  );
  if (!listed) return mapFirstPage(ledger, (page) => ({ ...page, transactions: [added, ...page.transactions] }));
  return {
    ...ledger,
    pages: ledger.pages.map((page) => ({
      ...page,
      transactions: page.transactions.map((entry) => (entry.transaction_id === added.transaction_id ? added : entry)),
    })),
  };
}
