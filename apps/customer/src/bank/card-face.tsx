import { cn } from "@clara/ui/lib/cn";
import { CreditCard } from "lucide-react";

import { useI18n } from "../i18n";
import { formatExpiration, formatMoney, lastDigits } from "./format";
import { cardTypeKey, isCredit } from "./labels";
import type { Card } from "./types";

export function CardFace({ card, className }: { card: Card; className?: string }) {
  const { locale, t } = useI18n();
  const credit = isCredit(card);

  return (
    <div
      className={cn(
        "flex aspect-[1.586] w-full flex-col justify-between rounded-xl bg-gradient-to-br p-5 text-white shadow-sm",
        credit ? "from-neutral-900 to-neutral-700" : "from-sky-900 to-sky-700",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium">{t(cardTypeKey(card))}</span>
        <CreditCard className="size-5 opacity-80" aria-hidden />
      </div>
      <div>
        <p className="text-xs text-white/70">{t(credit ? "card.balance" : "card.available")}</p>
        <p className="text-xl font-semibold tabular-nums">
          {card.current_balance ? formatMoney(card.current_balance, card.currency, locale) : "·"}
        </p>
        {credit && card.credit_limit && (
          <p className="text-xs text-white/70 tabular-nums">
            {t("card.limit")} {formatMoney(card.credit_limit, card.currency, locale)}
          </p>
        )}
      </div>
      <div className="flex items-center justify-between text-sm text-white/80 tabular-nums">
        <span aria-label={card.product_number}>•••• {lastDigits(card.product_number)}</span>
        <span>{t("card.expires", { date: formatExpiration(card.expiration_date) })}</span>
      </div>
    </div>
  );
}
