import type { Card, Profile, Transaction } from "../../bank/types";
import { isHighScore } from "../claims";
import { cardLock, claimForTransaction } from "../overlay";
import type { ClaraSessionState } from "../session";

export const DAY_MS = 86_400_000;
export const HISTORY_DAYS = 90;
const FRESH_HOLD_DAYS = 7;
const MIN_HOURS_SAMPLE = 5;

export interface Snapshot {
  profile: Pick<Profile, "country">;
  cards: Card[];
  entries: Transaction[];
}

export interface Context extends Snapshot {
  session: ClaraSessionState;
  now: number;
}

export function merchantKey(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("en")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function findEntry(ctx: Pick<Context, "entries">, transactionId: string): Transaction | undefined {
  return ctx.entries.find((entry) => entry.transaction_id === transactionId);
}

export function cardOf(ctx: Pick<Context, "cards">, productId: string): Card | undefined {
  return ctx.cards.find((card) => card.product_id === productId);
}

export function priorPurchases(tx: Transaction, ctx: Pick<Context, "entries">): Transaction[] {
  const key = merchantKey(tx.merchant_name);
  return ctx.entries
    .filter(
      (entry) =>
        entry.transaction_id !== tx.transaction_id &&
        entry.transaction_status === "Approved" &&
        entry.transaction_date < tx.transaction_date &&
        merchantKey(entry.merchant_name) === key,
    )
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}

export function pendingDays(tx: Transaction, now: number): number {
  return Math.floor((now - Date.parse(tx.transaction_date)) / DAY_MS);
}

export function isFreshHold(tx: Transaction, now: number): boolean {
  return tx.transaction_status === "Pending" && pendingDays(tx, now) <= FRESH_HOLD_DAYS;
}

export function isStalePending(tx: Transaction, now: number): boolean {
  return tx.transaction_status === "Pending" && !isFreshHold(tx, now);
}

function othersOf(tx: Transaction, ctx: Pick<Context, "entries">): Transaction[] {
  return ctx.entries.filter(
    (entry) => entry.transaction_id !== tx.transaction_id && entry.transaction_status === "Approved",
  );
}

export function isAbroad(tx: Transaction, ctx: Pick<Context, "profile">): boolean {
  return ctx.profile.country !== null && tx.transaction_country !== ctx.profile.country;
}

export function isUnusualChannel(tx: Transaction, ctx: Pick<Context, "entries">): boolean {
  const others = othersOf(tx, ctx);
  return tx.channel !== "POS" && others.length > 0 && others.every((entry) => entry.channel === "POS");
}

export type ProtectSignal = "score" | "country" | "channel";

export function protectSignals(tx: Transaction, ctx: Pick<Context, "entries" | "profile">): ProtectSignal[] {
  const signals: ProtectSignal[] = [];
  if (isHighScore(tx)) signals.push("score");
  if (isAbroad(tx, ctx)) signals.push("country");
  if (isUnusualChannel(tx, ctx)) signals.push("channel");
  return signals;
}

export interface HourBand {
  from: number;
  to: number;
  hours: number[];
}

export function hourOf(iso: string): number {
  const date = new Date(iso);
  return date.getHours() + date.getMinutes() / 60;
}

export function usualHours(tx: Transaction, ctx: Pick<Context, "entries">): HourBand | null {
  const hours = othersOf(tx, ctx)
    .map((entry) => hourOf(entry.transaction_date))
    .sort((a, b) => a - b);
  if (hours.length < MIN_HOURS_SAMPLE) return null;
  const at = (share: number) => hours[Math.min(hours.length - 1, Math.floor(share * hours.length))] ?? 0;
  return { from: Math.floor(at(0.05)), to: Math.ceil(at(0.95)), hours };
}

export function isUnusualHour(tx: Transaction, band: HourBand | null): boolean {
  if (!band) return false;
  const hour = hourOf(tx.transaction_date);
  return hour < band.from || hour > band.to;
}

export type Reason = ProtectSignal | "newMerchant" | "hour";

export function reasonsOf(tx: Transaction, ctx: Pick<Context, "entries" | "profile">): Reason[] {
  const reasons: Reason[] = [];
  if (priorPurchases(tx, ctx).length === 0) reasons.push("newMerchant");
  if (isAbroad(tx, ctx)) reasons.push("country");
  if (isUnusualHour(tx, usualHours(tx, ctx))) reasons.push("hour");
  if (isUnusualChannel(tx, ctx)) reasons.push("channel");
  if (isHighScore(tx)) reasons.push("score");
  return reasons;
}

export function homeShare(tx: Transaction, ctx: Pick<Context, "entries" | "profile">): { home: number; total: number } {
  const recent = othersOf(tx, ctx)
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))
    .slice(0, 12);
  return {
    home: recent.filter((entry) => entry.transaction_country === ctx.profile.country).length,
    total: recent.length,
  };
}

export function isRecognized(transactionId: string, session: ClaraSessionState): boolean {
  return session.recognized.includes(transactionId);
}

export function isBlockedCard(productId: string, ctx: Pick<Context, "cards" | "session">): boolean {
  const card = cardOf(ctx, productId);
  return card !== undefined && cardLock(card, ctx.session).blocked;
}

export function inClaim(transactionId: string, ctx: Pick<Context, "session">): boolean {
  return claimForTransaction(transactionId, ctx.session) !== undefined;
}
