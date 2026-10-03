import { cn } from "@clara/ui/lib/cn";
import { Lock } from "lucide-react";

import { isBlocked } from "../clara/overlay";
import { useI18n } from "../i18n";
import { brand } from "./brand";
import type { Material } from "./card-display";
import { formatExpiration, formatMoney, lastDigits } from "./format";
import { cardTypeKey, isCredit } from "./labels";
import type { Card } from "./types";

interface CardFaceProps {
  card: Card;
  material: Material;
  tone?: "bank" | "clara";
  className?: string;
}

export function CardFace({ card, material, tone = "bank", className }: CardFaceProps) {
  const { t } = useI18n();
  const clara = tone === "clara";

  return (
    <div
      data-material={material}
      data-tone={tone}
      className={cn(
        "card-face flex aspect-[1.586] w-full flex-col justify-between rounded-[14px] text-left text-on-mat",
        clara ? "px-4 py-3.5" : "px-[18px] py-4",
        className,
      )}
    >
      <span className="relative flex items-start justify-between">
        <span className={cn("font-medium", clara ? "text-[13px]" : "text-[13.5px]")}>{t(cardTypeKey(card))}</span>
        <span className={cn("font-mono tracking-[0.14em] text-on-mat-2", clara ? "text-[10.5px]" : "text-[11px]")}>
          {brand.cardWord}
        </span>
      </span>
      <span className="relative flex items-center">
        <span className="card-chip" />
      </span>
      <span className="relative flex items-end justify-between gap-2">
        <span className={cn("font-mono tracking-[0.08em]", clara ? "text-sm" : "text-[15px]")}>
          •••• {lastDigits(card.product_number)}
        </span>
        <span className={cn("text-right font-mono text-on-mat-2", clara ? "text-[10.5px]" : "text-[11px]")}>
          {t("card.expiresShort")}
          <b className={cn("block font-medium text-on-mat", clara ? "text-[11.5px]" : "text-xs")}>
            {formatExpiration(card.expiration_date)}
          </b>
        </span>
      </span>
      {isBlocked(card) && (
        <span className="absolute inset-0 z-[2] grid place-items-center bg-[rgb(9_13_11/0.66)] p-3 text-center text-on-mat">
          <span className="flex flex-col items-center gap-1.5 font-semibold">
            <Lock className="size-6" aria-hidden />
            {t("card.blocked")}
          </span>
        </span>
      )}
    </div>
  );
}

export function CardUsage({ card, tone = "bank", className }: { card: Card; tone?: "bank" | "clara"; className?: string }) {
  const { locale, t } = useI18n();
  const money = (amount: string) => formatMoney(amount, card.currency, locale);
  const clara = tone === "clara";
  const fill = cn("block h-full rounded-full", clara ? "bg-[linear-gradient(90deg,#1f9f7c,#4c8fe6)]" : "bg-primary");
  const track = cn("h-1.5 overflow-hidden rounded-full", clara ? "bg-muted" : "bg-neutral-soft");

  if (isCredit(card) && card.credit_limit && card.current_balance) {
    const percent = Math.min(100, Math.round((Number(card.current_balance) / Number(card.credit_limit)) * 100));
    return (
      <div className={cn("flex flex-col gap-1.5", clara && "chat-usage", className)}>
        <div className="flex justify-between gap-2 text-[13px] text-ink-2">
          <span>
            {t("card.used")} <b className="font-semibold text-ink tabular-nums">{money(card.current_balance)}</b>
          </span>
          <span className="tabular-nums">{t("card.of", { amount: money(card.credit_limit) })}</span>
        </div>
        <div className={track} role="img" aria-label={t("card.usedPercent", { percent: String(percent) })}>
          <i className={fill} style={{ width: `${percent}%` }} />
        </div>
      </div>
    );
  }

  const available = (
    <div className="flex justify-between gap-2 text-[13px] text-ink-2">
      <span>{t("card.available")}</span>
      <b className="font-semibold text-ink tabular-nums">{card.current_balance ? money(card.current_balance) : "·"}</b>
    </div>
  );
  if (!clara) return <div className={className}>{available}</div>;
  return (
    <div className={cn("chat-usage flex flex-col gap-1.5", className)}>
      {available}
      <div className={track} aria-hidden>
        <i className={cn(fill, "opacity-35")} style={{ width: "100%" }} />
      </div>
    </div>
  );
}
