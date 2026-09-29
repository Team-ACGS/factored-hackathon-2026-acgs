import type { BadgeVariant } from "@clara/ui/components/badge";

import type { MessageKey } from "../i18n/en";
import { isMessageKey, type Translate } from "../i18n/locale";
import type { Card, Country, TransactionStatus } from "./types";
import { countries } from "./types";

export const statusVariants: Record<TransactionStatus, BadgeVariant> = {
  Approved: "secondary",
  Pending: "warning",
  Declined: "destructive",
  Reversed: "info",
};

export function cardTypeKey(card: Pick<Card, "product_type">): MessageKey {
  return card.product_type === "Tarjeta Débito" ? "card.debit" : "card.credit";
}

export function isCredit(card: Pick<Card, "product_type">): boolean {
  return cardTypeKey(card) === "card.credit";
}

export function labelOf(t: Translate, prefix: "category" | "channel", value: string | null): string | null {
  if (!value) return null;
  const key = `${prefix}.${value}`;
  return isMessageKey(key) ? t(key) : value;
}

export function countryName(code: string, locale: string): string {
  return new Intl.DisplayNames([locale], { type: "region" }).of(code) ?? code;
}

export function guessCountry(languages: readonly string[]): Country {
  for (const tag of languages) {
    const region = tag.split("-")[1]?.toUpperCase();
    const match = countries.find((country) => country === region);
    if (match) return match;
  }
  return "US";
}
