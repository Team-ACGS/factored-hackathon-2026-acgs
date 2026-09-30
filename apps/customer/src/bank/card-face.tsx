import { cn } from "@clara/ui/lib/cn";
import { Lock } from "lucide-react";

import type { CardLock } from "../clara/overlay";
import { useI18n } from "../i18n";
import { brand } from "./brand";
import { useLockTime, type Material } from "./card-display";
import { formatExpiration, formatMoney, lastDigits } from "./format";
import { cardTypeKey, isCredit } from "./labels";
import type { Card } from "./types";

interface CardFaceProps {
  card: Card;
  material: Material;
  lock: CardLock;
  className?: string;
}

export function CardFace({ card, material, lock, className }: CardFaceProps) {
  const { t } = useI18n();
  const lockTime = useLockTime();

  return (
    <div
      data-material={material}
      className={cn(
        "card-face flex aspect-[1.586] w-full flex-col justify-between rounded-[14px] px-[18px] py-4 text-left text-on-mat",
        className,
      )}
    >
      <span className="relative flex items-start justify-between">
        <span className="text-[13.5px] font-medium">{t(cardTypeKey(card))}</span>
        <span className="font-mono text-[11px] tracking-[0.14em] text-on-mat-2">{brand.cardWord}</span>
      </span>
      <span className="relative flex items-center">
        <span className="card-chip" />
      </span>
      <span className="relative flex items-end justify-between gap-2">
        <span className="font-mono text-[15px] tracking-[0.08em]">•••• {lastDigits(card.product_number)}</span>
        <span className="text-right font-mono text-[11px] text-on-mat-2">
          {t("card.expiresShort")}
          <b className="block text-xs font-medium text-on-mat">{formatExpiration(card.expiration_date)}</b>
        </span>
      </span>
      {lock.blocked && (
        <span className="absolute inset-0 z-[2] grid place-items-center bg-[rgb(9_13_11/0.66)] p-3 text-center text-on-mat">
          <span className="flex flex-col items-center gap-1.5 font-semibold">
            <Lock className="size-6" aria-hidden />
            {t("card.blocked")}
            {lock.since && <small className="text-xs font-normal text-on-mat-2">{t("card.since", { time: lockTime(lock.since) })}</small>}
          </span>
        </span>
      )}
    </div>
  );
}

export function CardUsage({ card, className }: { card: Card; className?: string }) {
  const { locale, t } = useI18n();
  const money = (amount: string) => formatMoney(amount, card.currency, locale);

  if (isCredit(card) && card.credit_limit && card.current_balance) {
    const percent = Math.min(100, Math.round((Number(card.current_balance) / Number(card.credit_limit)) * 100));
    return (
      <div className={cn("flex flex-col gap-1.5", className)}>
        <div className="flex justify-between gap-2 text-[13px] text-ink-2">
          <span>
            {t("card.used")} <b className="font-semibold text-ink tabular-nums">{money(card.current_balance)}</b>
          </span>
          <span className="tabular-nums">{t("card.of", { amount: money(card.credit_limit) })}</span>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-neutral-soft"
          role="img"
          aria-label={t("card.usedPercent", { percent: String(percent) })}
        >
          <i className="block h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex justify-between gap-2 text-[13px] text-ink-2", className)}>
      <span>{t("card.available")}</span>
      <b className="font-semibold text-ink tabular-nums">{card.current_balance ? money(card.current_balance) : "·"}</b>
    </div>
  );
}
