import { isPending, type LedgerEntry } from "./ledger";
import type { TransactionStatus } from "./types";

export const movementFilters = ["all", "Pending", "Reversed", "Declined"] as const;
export type MovementFilter = (typeof movementFilters)[number];

const DAY_MS = 86_400_000;

export function isFiltering(filter: MovementFilter, query: string): boolean {
  return filter !== "all" || query.trim() !== "";
}

export function matches(entry: LedgerEntry, filter: MovementFilter, query: string): boolean {
  const needle = query.trim().toLocaleLowerCase();
  if (isPending(entry)) return !isFiltering(filter, query);
  const status: TransactionStatus = entry.transaction_status;
  return (filter === "all" || status === filter) && (!needle || entry.merchant_name.toLocaleLowerCase().includes(needle));
}

export function dayKey(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

export interface DayGroup {
  day: string;
  entries: LedgerEntry[];
}

export function groupByDay(entries: readonly LedgerEntry[], timeZone?: string): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const entry of entries) {
    const day = dayKey(entry.transaction_date, timeZone);
    const last = groups[groups.length - 1];
    if (last?.day === day) last.entries.push(entry);
    else groups.push({ day, entries: [entry] });
  }
  return groups;
}

export function daysBetween(fromDay: string, toDay: string): number {
  return Math.round((Date.parse(`${toDay}T00:00:00Z`) - Date.parse(`${fromDay}T00:00:00Z`)) / DAY_MS);
}

export function recentMovements(ledgers: readonly (readonly LedgerEntry[])[], count: number): LedgerEntry[] {
  return ledgers
    .flat()
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))
    .slice(0, count);
}
