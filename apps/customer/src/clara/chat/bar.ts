import type { MessageKey } from "../../i18n/en";
import type { Translate } from "../../i18n/locale";
import { openClaims } from "../overlay";
import { cardOf, findEntry, type Context } from "./insight";
import { currentView, type Ask, type AskKind, type BarChoice, type ChatState, type PanelPick } from "./state";
import { cardLabel } from "./text";
import { flaggedCandidate, triage } from "./triage";

export type BarIcon = "store" | "card" | "clock" | "question";

export interface BarOption extends BarChoice {
  label: string;
  icon?: BarIcon;
}

export type Bar = { kind: "choose"; prompt: string; options: BarOption[] } | { kind: "pick"; pick: PanelPick };

const askPrompts: Record<AskKind, MessageKey> = {
  isThis: "clara.chat.ask.isThis",
  fuiste: "clara.chat.ask.fuiste",
  recognize: "clara.chat.ask.recognize",
  haveCard: "clara.chat.ask.haveCard",
  claim: "clara.chat.ask.claim",
  block: "clara.chat.ask.block",
};

const askOptions: Record<AskKind, readonly [boolean, MessageKey][]> = {
  isThis: [
    [true, "clara.chat.option.isThisYes"],
    [false, "clara.chat.option.isThisNo"],
  ],
  fuiste: [
    [false, "clara.chat.option.fuisteNo"],
    [true, "clara.chat.option.fuisteYes"],
  ],
  recognize: [
    [true, "clara.chat.option.recognizeYes"],
    [false, "clara.chat.option.recognizeNo"],
  ],
  haveCard: [
    [true, "clara.chat.option.haveCardYes"],
    [false, "clara.chat.option.haveCardNo"],
  ],
  claim: [
    [true, "clara.chat.option.claimYes"],
    [false, "clara.chat.option.notNow"],
  ],
  block: [
    [true, "clara.chat.option.blockYes"],
    [false, "clara.chat.option.notNow"],
  ],
};

function choose(prompt: string, options: BarOption[]): Bar {
  return { kind: "choose", prompt, options };
}

function option(id: string, label: string, choice: Omit<BarChoice, "id" | "echo">, icon?: BarIcon): BarOption {
  return { id, label, echo: label, ...choice, ...(icon ? { icon } : {}) };
}

function askBar(ask: Ask, ctx: Context | null, t: Translate): Bar {
  const card = ctx ? cardOf(ctx, ask.productId) : undefined;
  return choose(
    t(askPrompts[ask.kind], { card: card ? cardLabel(card, t) : "" }),
    askOptions[ask.kind].map(([yes, key]) =>
      option(`${ask.kind}:${yes ? "yes" : "no"}`, t(key), { input: { type: "answer", ask: ask.kind, yes } }),
    ),
  );
}

export function starters(t: Translate): Bar {
  return choose(t("clara.chat.ask.help"), [
    option("start:unrecognized", t("clara.shortcut.unrecognized"), { input: { type: "flow", flow: "unrecognized" } }, "store"),
    option("start:cards", t("clara.shortcut.cards"), { input: { type: "flow", flow: "cards" } }, "card"),
    option("start:claims", t("clara.shortcut.claim"), { input: { type: "claims", claimId: null } }, "clock"),
  ]);
}

export function barOf(state: ChatState, ctx: Context | null, t: Translate): Bar | null {
  if (state.pick) return { kind: "pick", pick: state.pick };
  if (state.panel.mode === "searching" || state.panel.mode === "calling") return null;
  const view = currentView(state);
  if (!view) return state.human ? null : starters(t);
  if (state.ask?.viewId === view.id) return askBar(state.ask, ctx, t);
  if (!ctx) return null;
  const spec = view.spec;
  if (spec.kind === "card") {
    const flagged = flaggedCandidate({ ...ctx, entries: ctx.entries.filter((entry) => entry.product_id === spec.productId) });
    if (flagged) {
      return choose(t("clara.chat.ask.direct"), [
        option(
          "card:review",
          t("clara.chat.option.review", { merchant: flagged.merchant_name }),
          { input: { type: "charge", productId: flagged.product_id, transactionId: flagged.transaction_id } },
          "store",
        ),
      ]);
    }
    const claim = openClaims(ctx.session).find((item) => item.product_id === spec.productId);
    if (claim) {
      return choose(t("clara.chat.ask.direct"), [
        option(
          "card:claim",
          t("clara.chat.option.seeClaim", { merchant: claim.merchant_name }),
          { input: { type: "claims", claimId: claim.claim_id } },
          "clock",
        ),
      ]);
    }
    return null;
  }
  if (spec.kind === "movement") {
    const tx = findEntry(ctx, spec.transactionId);
    if (!tx) return null;
    const { outcome } = triage(tx, ctx);
    const target = { productId: tx.product_id, transactionId: tx.transaction_id };
    if (outcome === "neverCharged") {
      return choose(t("clara.chat.ask.direct"), [
        option("movement:notAttempted", t("clara.chat.option.notAttempted"), { input: { type: "notAttempted", ...target } }, "question"),
      ]);
    }
    if (outcome === "question" || outcome === "history" || outcome === "recognized") {
      return choose(t("clara.chat.ask.direct"), [
        option("movement:unrecognized", t("clara.chat.option.unrecognized"), { input: { type: "unrecognized", ...target } }, "question"),
      ]);
    }
  }
  return null;
}
