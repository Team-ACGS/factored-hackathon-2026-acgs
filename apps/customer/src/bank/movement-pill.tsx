import { cn } from "@clara/ui/lib/cn";

import { useI18n } from "../i18n";
import type { TransactionStatus } from "./types";

const tones: Record<TransactionStatus | "claim", string> = {
  claim: "bg-info-soft text-info",
  Approved: "bg-ok-soft text-ok",
  Pending: "bg-warn-soft text-warn",
  Reversed: "bg-info-soft text-info",
  Declined: "bg-neutral-soft text-ink-2",
};

interface MovementPillProps {
  status: TransactionStatus;
  inClaim?: boolean;
  showApproved?: boolean;
}

export function MovementPill({ status, inClaim = false, showApproved = false }: MovementPillProps) {
  const { t } = useI18n();
  const tone = inClaim ? "claim" : status;
  if (tone === "Approved" && !showApproved) return null;
  return (
    <span
      className={cn(
        "inline-flex h-[22px] items-center rounded-full px-[9px] text-xs font-semibold whitespace-nowrap",
        tones[tone],
      )}
    >
      {t(tone === "claim" ? "pill.claim" : `pill.${tone}`)}
    </span>
  );
}
