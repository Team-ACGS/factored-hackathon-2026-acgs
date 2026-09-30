import type { Translate } from "../../i18n/locale";
import { findClaim } from "../overlay";
import { agent } from "./engine";
import { cardOf, findEntry, type Context } from "./insight";
import type { ViewSpec } from "./state";
import { cardLabel } from "./text";

export interface ViewMeta {
  kicker: string;
  title: string;
  label: string;
}

export function viewMeta(spec: ViewSpec, ctx: Context, t: Translate): ViewMeta {
  const merchantOf = (transactionId: string | null) =>
    (transactionId ? findEntry(ctx, transactionId)?.merchant_name : undefined) ?? "";
  switch (spec.kind) {
    case "movements":
      return {
        kicker: t("clara.chat.view.movements.kicker"),
        title: t("clara.chat.view.movements.title"),
        label: t("clara.chat.view.movements.label"),
      };
    case "cards":
      return {
        kicker: t("clara.chat.view.cards.kicker"),
        title: t("clara.chat.view.cards.title"),
        label: t("clara.chat.view.cards.label"),
      };
    case "card": {
      const card = cardOf(ctx, spec.productId);
      const name = card ? cardLabel(card, t) : "";
      return { kicker: t("clara.chat.view.card.kicker"), title: name, label: t("clara.chat.view.card.label", { card: name }) };
    }
    case "movement": {
      const merchant = merchantOf(spec.transactionId);
      return {
        kicker: t("clara.chat.view.charge.kicker"),
        title: merchant,
        label: t("clara.chat.view.movement.label", { merchant }),
      };
    }
    case "charge":
      return {
        kicker: t("clara.chat.view.charge.kicker"),
        title: merchantOf(spec.transactionId),
        label: t("clara.chat.view.charge.label"),
      };
    case "history": {
      const merchant = merchantOf(spec.transactionId);
      return {
        kicker: t("clara.chat.view.charge.kicker"),
        title: merchant,
        label: t("clara.chat.view.history.label", { merchant }),
      };
    }
    case "calm":
      return {
        kicker: t("clara.chat.view.calm.kicker"),
        title: t("clara.chat.view.calm.title"),
        label: t("clara.chat.view.calm.label"),
      };
    case "blockConfirm":
      return {
        kicker: t("clara.chat.view.protect.kicker"),
        title: t("clara.chat.view.blockConfirm.title"),
        label: t("clara.chat.view.blockConfirm.label"),
      };
    case "blockSteps":
      return {
        kicker: t("clara.chat.view.protect.kicker"),
        title: t("clara.chat.view.blockSteps.title"),
        label: t("clara.chat.view.steps.label"),
      };
    case "blockResult":
      return {
        kicker: t("clara.chat.view.protect.kicker"),
        title: t("clara.chat.view.blockResult.title"),
        label: t("clara.chat.view.blockResult.label"),
      };
    case "claimConfirm":
      return {
        kicker: t("clara.chat.view.claim.kicker"),
        title: t("clara.chat.view.claimConfirm.title"),
        label: t("clara.chat.view.claimConfirm.label"),
      };
    case "claimSteps":
      return {
        kicker: t("clara.chat.view.claim.kicker"),
        title: t("clara.chat.view.claimSteps.title"),
        label: t("clara.chat.view.steps.label"),
      };
    case "claimReceipt":
      return {
        kicker: t("clara.chat.view.claim.kicker"),
        title: t("clara.chat.view.claimReceipt.title"),
        label: t("clara.chat.view.claimReceipt.label"),
      };
    case "claimStatus":
      return {
        kicker: t("clara.chat.view.claimStatus.kicker"),
        title: findClaim(spec.claimId, ctx.session)?.merchant_name ?? "",
        label: t("clara.chat.view.claimReceipt.label"),
      };
    case "agent":
      return {
        kicker: t("clara.chat.view.agent.kicker"),
        title: t("clara.chat.view.agent.title"),
        label: t("clara.chat.view.agent.label", { name: agent.name }),
      };
  }
}
