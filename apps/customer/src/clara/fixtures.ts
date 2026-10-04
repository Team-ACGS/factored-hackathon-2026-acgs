import { v7 } from "uuid";

import type { Card, Transaction } from "../bank/types";

export const setupAt = Date.parse("2026-09-01T15:00:00.000Z");
export const DAY = 86_400_000;

export function cardAt(product_type: string, instant = setupAt, overrides: Partial<Card> = {}): Card {
  return {
    product_id: v7({ msecs: instant }),
    product_type,
    product_number: "**** 1156",
    currency: "MXN",
    current_balance: "1000.00",
    credit_limit: null,
    product_status: "Active",
    balance_as_of: new Date(instant).toISOString(),
    ...overrides,
  };
}

let sequence = 0;

export function purchase(card: Card, daysBeforeSetup: number, overrides: Partial<Transaction> = {}): Transaction {
  const instant = setupAt - daysBeforeSetup * DAY;
  sequence += 1;
  return {
    transaction_id: v7({ msecs: instant, seq: sequence }),
    product_id: card.product_id,
    transaction_date: new Date(instant).toISOString(),
    transaction_category: "Entertainment",
    amount: "540.00",
    currency: "MXN",
    channel: "POS",
    merchant_name: `Cinemex ${sequence}`,
    merchant_category: "Entertainment",
    transaction_country: "MX",
    transaction_city: "Tlalnepantla",
    transaction_status: "Approved",
    fraud_score: "12.50",
    ...overrides,
  };
}
