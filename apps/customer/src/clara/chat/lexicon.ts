import type { Transaction } from "../../bank/types";
import { merchantKey } from "./insight";

export function normalized(text: string): string {
  return ` ${merchantKey(text)} `;
}

const negative = / (no|not|nope|nao|nunca|never|wasn t|wasnt|didn t|didnt|don t|dont|ahora no|not now|agora nao) /;
const positive =
  / (si|yes|yeah|yep|sim|claro|ok|okay|dale|sure|correct|correcto|exacto|exato|isso|ese|esse|that one|es ese|e esse|fui yo|was me|fui eu|la tengo|have it|i do|tenho|bloquea\w*|block\w*|bloqueia\w*|abre\w*|abra\w*|open\w*) /;

export function polarity(text: string): boolean | null {
  const words = normalized(text);
  if (negative.test(words)) return false;
  if (positive.test(words)) return true;
  return null;
}

export type Intent = "protect" | "claims" | "cards" | "charge";

const intents: readonly [Intent, RegExp][] = [
  ["protect", / (bloque\w*|block\w*|bloqueia\w*|robad\w*|robaron|roubad\w*|stolen|lost|perdi|perdida|clonad\w*|not me|no fui|nao fui) /],
  ["claims", / (aclaraci\w*|aclaracion\w*|reclam\w*|claim\w*|caso|case|contestac\w*|disputa|dispute) /],
  ["cards", / (tarjeta|tarjetas|card|cards|cartao|cartoes|saldo|saldos|balance|limite|limit) /],
  ["charge", / (cargo|cargos|cobro|cobros|charge|charges|compra|compras|purchase|cobranca|reconozco|recognize|reconheco|movimiento\w*|movement\w*|transac\w*) /],
];

export function intentOf(text: string): Intent | null {
  const words = normalized(text);
  return intents.find(([, pattern]) => pattern.test(words))?.[0] ?? null;
}

const ignored = new Set(["com", "www", "the", "del", "los", "las"]);

export function mentionedMovement(text: string, entries: readonly Transaction[]): Transaction | undefined {
  const words = normalized(text);
  const newest = [...entries].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  const byMerchant = newest.find((entry) =>
    merchantKey(entry.merchant_name)
      .split(" ")
      .some((part) => part.length >= 4 && !ignored.has(part) && words.includes(` ${part} `)),
  );
  if (byMerchant) return byMerchant;
  const amounts = [...text.matchAll(/\d[\d.,]*/g)].map((match) => Number(match[0].replace(/,(?=\d{3}\b)/g, "").replace(",", ".")));
  return newest.find((entry) => amounts.some((amount) => amount > 0 && Math.abs(Number(entry.amount) - amount) < 0.005));
}
