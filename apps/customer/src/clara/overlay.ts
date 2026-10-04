import { caseOfTransaction } from "../bank/cases";
import { isPending, type LedgerEntry } from "../bank/ledger";
import type { Card, Case, Transaction } from "../bank/types";

const HIGH_SCORE = 30;

export function isBlocked(card: Pick<Card, "product_status">): boolean {
  return card.product_status === "Blocked";
}

export function isHighScore(transaction: Pick<Transaction, "fraud_score">): boolean {
  return transaction.fraud_score !== null && Number(transaction.fraud_score) > HIGH_SCORE;
}

export function flaggedCharges(
  entries: readonly LedgerEntry[],
  cards: readonly Card[],
  answered: ReadonlySet<string> = new Set(),
  cases: readonly Case[] = [],
): Transaction[] {
  const locked = new Set(cards.filter(isBlocked).map((card) => card.product_id));
  return entries
    .filter(
      (entry): entry is Transaction =>
        !isPending(entry) &&
        isHighScore(entry) &&
        !locked.has(entry.product_id) &&
        !answered.has(entry.transaction_id) &&
        caseOfTransaction(cases, entry.transaction_id) === undefined,
    )
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}
