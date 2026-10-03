import { useI18n } from "../i18n";
import { lastDigits } from "./format";
import { cardTypeKey } from "./labels";
import type { Card } from "./types";

const materials = ["emerald", "brass", "graphite"] as const;
export type Material = (typeof materials)[number];

export function materialOf(cards: readonly Card[], productId: string): Material {
  const index = Math.max(0, cards.findIndex((card) => card.product_id === productId));
  return materials[index % materials.length] ?? "emerald";
}

export function useCardName() {
  const { t } = useI18n();
  return (card: Card) => `${t(cardTypeKey(card))} •••• ${lastDigits(card.product_number)}`;
}
