import { cn } from "@clara/ui/lib/cn";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { useI18n } from "../i18n";
import { formatMoney } from "./format";
import { isPending, type LedgerEntry } from "./ledger";
import { MovementPill } from "./movement-pill";

export const movementRowClass =
  "grid w-full grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 px-3 py-[13px] text-left outline-none transition-colors hover:bg-muted focus-visible:bg-muted sm:grid-cols-[40px_minmax(0,1fr)_auto] sm:gap-3.5 sm:px-4 sm:py-3.5 [&+&]:border-t [&+&]:border-line";

function initialOf(merchant: string): string {
  const letters = merchant
    .replace(/^[A-Z]+\*/, "")
    .replace(/[^\p{L} ]/gu, " ")
    .trim();
  return (letters[0] ?? "·").toLocaleUpperCase();
}

interface MovementContentProps {
  entry: LedgerEntry;
  meta: string;
  inClaim: boolean;
  tag?: ReactNode;
}

export function MovementContent({ entry, meta, inClaim, tag }: MovementContentProps) {
  const { locale, t } = useI18n();
  const icon = "grid size-9 place-items-center rounded-xl bg-muted text-[15px] font-semibold text-ink-2 sm:size-10";

  if (isPending(entry)) {
    return (
      <>
        <span className={icon} aria-hidden>
          <Loader2 className="size-4 animate-spin" />
        </span>
        <span className="min-w-0 text-ink-3">
          <span className="block truncate font-semibold">{t("card.adding")}</span>
          <span className="text-[13px]">{meta}</span>
        </span>
        <span className="h-[22px] w-16 rounded-md bg-muted" aria-hidden />
      </>
    );
  }

  const struck = entry.transaction_status === "Declined" || entry.transaction_status === "Reversed";
  return (
    <>
      <span className={icon} aria-hidden>
        {initialOf(entry.merchant_name)}
      </span>
      <span className="min-w-0">
        <span className="block truncate font-semibold">{entry.merchant_name}</span>
        <span className="text-[13px] text-ink-3">{meta}</span>
        {tag}
      </span>
      <span className="flex flex-col items-end gap-1">
        <span className={cn("font-semibold whitespace-nowrap tabular-nums", struck && "font-medium text-ink-3 line-through")}>
          {formatMoney(entry.amount, entry.currency, locale)}
        </span>
        <MovementPill status={entry.transaction_status} inClaim={inClaim} />
      </span>
    </>
  );
}
