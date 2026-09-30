import { isDebit } from "../bank/labels";
import { isPending, type LedgerEntry } from "../bank/ledger";
import type { Card, Transaction } from "../bank/types";
import { idTime } from "../chat/clock";

const DAY_MS = 86_400_000;
const SEEDED_MIN_AGE_DAYS = 7;
const HIGH_SCORE = 30;
export const stageOffsetsDays = { opened: 0, assigned: 2, review: 6 } as const;

export type ClaimStage = keyof typeof stageOffsetsDays;
export const claimStages = ["opened", "assigned", "review"] as const satisfies readonly ClaimStage[];

export interface Claim {
  claim_id: string;
  product_id: string;
  transaction_id: string;
  merchant_name: string;
  amount: string;
  currency: string;
  opened_at: string;
}

export function claimId(transactionId: string, openedAt: string): string {
  let hash = 0x811c9dc5;
  for (const char of transactionId) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return `CLR-${openedAt.slice(0, 4)}-${String(hash % 1_000_000).padStart(6, "0")}`;
}

export function claimOf(transaction: Transaction, openedAt: string): Claim {
  return {
    claim_id: claimId(transaction.transaction_id, openedAt),
    product_id: transaction.product_id,
    transaction_id: transaction.transaction_id,
    merchant_name: transaction.merchant_name,
    amount: transaction.amount,
    currency: transaction.currency,
    opened_at: openedAt,
  };
}

export function seededCard(cards: readonly Card[]): Card | undefined {
  return cards.find(isDebit) ?? cards[0];
}

export function isHighScore(transaction: Pick<Transaction, "fraud_score">): boolean {
  return transaction.fraud_score !== null && Number(transaction.fraud_score) > HIGH_SCORE;
}

export function hasSignals(transaction: Transaction, country: string | null): boolean {
  return isHighScore(transaction) || (country !== null && transaction.transaction_country !== country);
}

function seededCandidate(card: Card, country: string | null) {
  const cutoff = idTime(card.product_id) - SEEDED_MIN_AGE_DAYS * DAY_MS;
  return (entry: LedgerEntry): entry is Transaction =>
    !isPending(entry) &&
    entry.transaction_status === "Approved" &&
    entry.channel === "POS" &&
    !hasSignals(entry, country) &&
    Date.parse(entry.transaction_date) <= cutoff;
}

export function findSeededClaim(card: Card, entries: readonly LedgerEntry[], country: string | null): Claim | null {
  const transaction = entries.find(seededCandidate(card, country));
  if (!transaction) return null;
  return claimOf(transaction, new Date(Date.parse(transaction.transaction_date) + DAY_MS).toISOString());
}

export type StepState = "done" | "now" | "todo";

export interface ClaimStep {
  stage: ClaimStage;
  state: StepState;
  at: string;
}

function stageAt(claim: Claim, stage: ClaimStage): number {
  return Date.parse(claim.opened_at) + stageOffsetsDays[stage] * DAY_MS;
}

export function claimStage(claim: Claim, now: number): ClaimStage {
  return [...claimStages].reverse().find((stage) => now >= stageAt(claim, stage)) ?? "opened";
}

export function claimSteps(claim: Claim, now: number): ClaimStep[] {
  const current = claimStages.indexOf(claimStage(claim, now));
  return claimStages.map((stage, index) => ({
    stage,
    state: index < current ? "done" : index === current ? "now" : "todo",
    at: new Date(stageAt(claim, stage)).toISOString(),
  }));
}
