import { lastDigits } from "../../bank/format";
import { cardTypeKey } from "../../bank/labels";
import type { Card } from "../../bank/types";
import type { Translate } from "../../i18n/locale";

export function sameDay(a: number, b: number): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString();
}

export function whenText(iso: string, now: number, locale: string, t: Translate): string {
  const at = Date.parse(iso);
  const time = new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(at);
  if (sameDay(at, now)) return t("clara.when.today", { time });
  if (sameDay(at, now - 86_400_000)) return t("clara.when.yesterday", { time });
  return t("clara.when.on", {
    date: new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(at),
    time,
  });
}

export function cardLabel(card: Card, t: Translate): string {
  return `${t(cardTypeKey(card))} •••• ${lastDigits(card.product_number)}`;
}
