import { formatMoney } from "../bank/format";
import type { Transaction } from "../bank/types";
import type { Locale, Translate } from "../i18n/locale";
import type { Input } from "./chat/state";

export type TopicCharge = Pick<
  Transaction,
  "transaction_id" | "product_id" | "merchant_name" | "amount" | "currency" | "transaction_date"
>;

export type Topic =
  | { kind: "unrecognized" }
  | { kind: "cards" }
  | { kind: "claim"; claim_id: string | null; merchant_name: string | null }
  | { kind: "charge"; charge: TopicCharge }
  | { kind: "text"; text: string };

export function chargeTopic(transaction: Transaction): Topic {
  const { transaction_id, product_id, merchant_name, amount, currency, transaction_date } = transaction;
  return { kind: "charge", charge: { transaction_id, product_id, merchant_name, amount, currency, transaction_date } };
}

export function topicMessage(topic: Topic, t: Translate, locale: Locale): string {
  switch (topic.kind) {
    case "unrecognized":
      return t("clara.topic.unrecognized");
    case "cards":
      return t("clara.topic.cards");
    case "claim":
      return topic.merchant_name
        ? t("clara.topic.claimOf", { merchant: topic.merchant_name })
        : t("clara.topic.claim");
    case "charge":
      return t("clara.topic.charge", {
        merchant: topic.charge.merchant_name,
        amount: formatMoney(topic.charge.amount, topic.charge.currency, locale),
        date: new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(new Date(topic.charge.transaction_date)),
      });
    case "text":
      return topic.text;
  }
}

export function topicInput(topic: Topic): Input {
  switch (topic.kind) {
    case "unrecognized":
      return { type: "flow", flow: "unrecognized" };
    case "cards":
      return { type: "flow", flow: "cards" };
    case "claim":
      return { type: "claims", claimId: topic.claim_id };
    case "charge":
      return { type: "charge", productId: topic.charge.product_id, transactionId: topic.charge.transaction_id };
    case "text":
      return { type: "text", text: topic.text };
  }
}
