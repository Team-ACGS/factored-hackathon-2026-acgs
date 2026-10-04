import { useQuery, useSuspenseQuery } from "@tanstack/react-query";

import { chargeOf, useRow } from "../../bank/rows";
import { bankQueries } from "../../bank/services";
import { useI18n } from "../../i18n";
import type { Readings } from "../../chat/conversation";
import type { ViewSpec } from "./panel-state";
import { cardLabel } from "./text";

export interface ViewMeta {
  kicker: string;
  title: string;
  label: string;
}

function rowOf(spec: ViewSpec) {
  return spec.kind === "movement" || spec.kind === "charge"
    ? { product_id: spec.row.productId, transaction_id: spec.row.transactionId }
    : null;
}

export function useViewMeta(spec: ViewSpec): ViewMeta {
  const { t } = useI18n();
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const cases = useQuery(bankQueries.cases()).data ?? [];
  const firstCase = spec.kind === "case" ? cases.find((item) => item.complaint_id === spec.cases[0]) : undefined;
  const tx = useRow(rowOf(spec) ?? (firstCase ? chargeOf(firstCase) : null));
  const merchant = tx?.merchant_name ?? "";

  switch (spec.kind) {
    case "movements":
      return {
        kicker: t("clara.chat.view.movements.kicker"),
        title: movementsTitle(spec.readings, t),
        label: t("clara.chat.view.movements.label"),
      };
    case "cards":
      return {
        kicker: t("clara.chat.view.cards.kicker"),
        title: t("clara.chat.view.cards.title"),
        label: t("clara.chat.view.cards.label"),
      };
    case "card": {
      const card = cards.find((item) => item.product_id === spec.productId);
      const name = card ? cardLabel(card, t) : "";
      return { kicker: t("clara.chat.view.card.kicker"), title: name, label: t("clara.chat.view.card.label", { card: name }) };
    }
    case "movement":
      return {
        kicker: t("clara.chat.view.movement.kicker"),
        title: merchant,
        label: t("clara.chat.view.movement.label", { merchant }),
      };
    case "charge":
      return { kicker: t("clara.chat.view.charge.kicker"), title: merchant, label: t("clara.chat.view.charge.label") };
    case "history": {
      const name = spec.readings.merchant ?? "";
      return {
        kicker: t("clara.chat.view.history.kicker"),
        title: name,
        label: t("clara.chat.view.history.label", { merchant: name }),
      };
    }
    case "case":
      return {
        kicker: t("clara.chat.view.case.kicker"),
        title: merchant || (firstCase?.case_id ?? ""),
        label: t("clara.chat.view.case.label"),
      };
    case "handoff":
      return {
        kicker: t("clara.chat.view.handoff.kicker"),
        title: t("clara.chat.view.handoff.title"),
        label: t("clara.chat.view.handoff.label"),
      };
  }
}

function movementsTitle(readings: Readings, t: ReturnType<typeof useI18n>["t"]): string {
  if (readings.merchant) return readings.merchant;
  if (readings.kind === "series") return t("clara.chat.view.movements.series");
  const period = readings.period ?? "";
  return period.charAt(0).toLocaleUpperCase() + period.slice(1) || t("clara.chat.view.movements.title");
}
