import { isPending, type LedgerEntry } from "../bank/ledger";
import type { Card, Transaction } from "../bank/types";
import { isHighScore, type Claim } from "./claims";
import type { ClaraSessionState } from "./session";

export function isBlocked(card: Pick<Card, "product_status">): boolean {
  return card.product_status === "Blocked";
}

export function openClaims(session: ClaraSessionState): Claim[] {
  return session.seeded ? [session.seeded] : [];
}

export function claimForTransaction(transactionId: string, session: ClaraSessionState): Claim | undefined {
  return openClaims(session).find((claim) => claim.transaction_id === transactionId);
}

export function findClaim(claimId: string, session: ClaraSessionState): Claim | undefined {
  return openClaims(session).find((claim) => claim.claim_id === claimId);
}

export function flaggedCharges(entries: readonly LedgerEntry[], cards: readonly Card[]): Transaction[] {
  const locked = new Set(cards.filter(isBlocked).map((card) => card.product_id));
  return entries
    .filter((entry): entry is Transaction => !isPending(entry) && isHighScore(entry) && !locked.has(entry.product_id))
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}
