import { isPending, type LedgerEntry } from "../bank/ledger";
import type { Card, Transaction } from "../bank/types";
import { isHighScore, type Claim } from "./claims";
import type { ClaraSessionState } from "./session";

export interface CardLock {
  blocked: boolean;
  since: string | null;
}

export function cardLock(card: Pick<Card, "product_id" | "product_status">, session: ClaraSessionState): CardLock {
  const since = session.blocks[card.product_id] ?? null;
  return { blocked: since !== null || card.product_status === "Blocked", since };
}

export function openClaims(session: ClaraSessionState): Claim[] {
  return session.seeded ? [...session.claims, session.seeded] : session.claims;
}

export function claimForTransaction(transactionId: string, session: ClaraSessionState): Claim | undefined {
  return openClaims(session).find((claim) => claim.transaction_id === transactionId);
}

export function findClaim(claimId: string, session: ClaraSessionState): Claim | undefined {
  return openClaims(session).find((claim) => claim.claim_id === claimId);
}

export function flaggedCharges(
  entries: readonly LedgerEntry[],
  cards: readonly Card[],
  session: ClaraSessionState,
): Transaction[] {
  const locked = new Set(cards.filter((card) => cardLock(card, session).blocked).map((card) => card.product_id));
  return entries
    .filter(
      (entry): entry is Transaction =>
        !isPending(entry) &&
        isHighScore(entry) &&
        !locked.has(entry.product_id) &&
        !session.reviewed.includes(entry.transaction_id),
    )
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}
