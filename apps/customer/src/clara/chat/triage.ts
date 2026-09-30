import type { Transaction } from "../../bank/types";
import {
  DAY_MS,
  HISTORY_DAYS,
  inClaim,
  isBlockedCard,
  isFreshHold,
  isRecognized,
  isStalePending,
  priorPurchases,
  protectSignals,
  type Context,
  type ProtectSignal,
} from "./insight";

export type Outcome =
  | "inClaim"
  | "blocked"
  | "refunded"
  | "neverCharged"
  | "hold"
  | "recognized"
  | "history"
  | "protect"
  | "question";

export interface Triage {
  outcome: Outcome;
  stale: boolean;
  prior: Transaction[];
  signals: ProtectSignal[];
}

export function triage(tx: Transaction, ctx: Context): Triage {
  const prior = priorPurchases(tx, ctx);
  const signals = protectSignals(tx, ctx);
  const stale = isStalePending(tx, ctx.now);
  const outcome = ((): Outcome => {
    if (inClaim(tx.transaction_id, ctx)) return "inClaim";
    if (isBlockedCard(tx.product_id, ctx)) return "blocked";
    if (tx.transaction_status === "Reversed") return "refunded";
    if (tx.transaction_status === "Declined") return "neverCharged";
    if (isFreshHold(tx, ctx.now)) return "hold";
    if (isRecognized(tx.transaction_id, ctx.session)) return "recognized";
    if (prior.length > 0) return "history";
    if (signals.length > 0) return "protect";
    return "question";
  })();
  return { outcome, stale, prior, signals };
}

export function afterHistory(tx: Transaction, ctx: Context): "protect" | "question" {
  return protectSignals(tx, ctx).length > 0 ? "protect" : "question";
}

export function flaggedCandidate(ctx: Context): Transaction | undefined {
  const since = new Date(ctx.now - HISTORY_DAYS * DAY_MS).toISOString();
  return [...ctx.entries]
    .filter((entry) => entry.transaction_date >= since)
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))
    .find((entry) => triage(entry, ctx).outcome === "protect");
}

export function recentList(ctx: Context, candidate: Transaction | undefined, count: number): Transaction[] {
  const newest = [...ctx.entries].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  const shown = newest.slice(0, count);
  if (candidate && !shown.includes(candidate)) shown.splice(count - 1, 1, candidate);
  return shown.sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}
