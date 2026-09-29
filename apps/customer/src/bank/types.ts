import type { Locale } from "../i18n/locale";

export const countries = ["PE", "MX", "CO", "AR", "US", "BR"] as const;
export type Country = (typeof countries)[number];

export type TransactionStatus = "Approved" | "Declined" | "Pending" | "Reversed";
export type CaseKind = "fresh_hold" | "reversed_charge" | "stale_pending";
export type ScoreOption = "flagged" | "missed" | "none";

export interface Profile {
  country: Country | null;
  language: Locale | null;
  setup_completed: boolean;
}

export interface Card {
  product_id: string;
  product_type: string;
  product_number: string;
  currency: string;
  current_balance: string | null;
  credit_limit: string | null;
  product_status: string;
  expiration_date: string;
}

export interface Transaction {
  transaction_id: string;
  product_id: string;
  transaction_date: string;
  transaction_type: string;
  transaction_category: string | null;
  amount: string;
  currency: string;
  channel: string;
  merchant_name: string;
  merchant_category: string | null;
  transaction_country: string;
  transaction_city: string | null;
  transaction_status: TransactionStatus;
  response_code: string;
  fraud_score: string | null;
}

export interface PlantedCase {
  kind: CaseKind;
  transaction: Transaction;
}

export interface Setup {
  profile: Profile;
  cases: PlantedCase[];
}

export interface CardPage {
  card: Card;
  transactions: Transaction[];
  next_cursor: string | null;
  server_time: string;
}

export type NewTransaction =
  | { transaction_id: string; kind: "normal" }
  | { transaction_id: string; kind: "suspicious"; score: ScoreOption };
