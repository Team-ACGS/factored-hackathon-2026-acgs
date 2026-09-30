import type { EntityState } from "@clara/ui/lib/entity";

import { formatMoney } from "../../bank/format";
import { isCredit } from "../../bank/labels";
import type { Card, Transaction } from "../../bank/types";
import type { MessageKey } from "../../i18n/en";
import type { Locale, Translate } from "../../i18n/locale";
import { claimId, claimOf, claimStage } from "../claims";
import { claimForTransaction, findClaim, openClaims } from "../overlay";
import type { ClaraSession } from "../session";
import { cardOf, findEntry, isBlockedCard, type Context, type Snapshot } from "./insight";
import { intentOf, mentionedMovement, polarity } from "./lexicon";
import {
  initialChat,
  restored,
  settled,
  type Ask,
  type AskKind,
  type BarChoice,
  type ChatState,
  type Chip,
  type Entry,
  type HintKey,
  type Input,
  type PanelPick,
  type Skeleton,
  type ViewSpec,
} from "./state";
import { cardLabel, rich, whenText, wordCount } from "./text";
import { afterHistory, flaggedCandidate, recentList, triage } from "./triage";

export const latency = {
  word: 26,
  afterSay: 160,
  think: 1000,
  thinkShort: 700,
  thinkLong: 1300,
  fetch: 2200,
  fetchLong: 2600,
  fetchShort: 1600,
  step: 1300,
  stepsDone: 300,
  call: 3200,
  humanTyping: 1800,
  humanReply: 1600,
  pause: 300,
} as const;

export const agent = { name: "Mariana R.", initials: "MR" } as const;

const LIST_SIZE = 6;

export interface MockChatPorts {
  load: () => Promise<Snapshot>;
  session: ClaraSession;
  t: () => Translate;
  locale: () => Locale;
  now: () => number;
  wait: (ms: number) => Promise<void>;
  bank: string;
}

class Cancelled extends Error {}

interface Run {
  wait: (ms: number) => Promise<void>;
}

export function createMockChat(ports: MockChatPorts) {
  let state: ChatState = initialChat;
  let token = 0;
  let running = false;
  let started = false;
  const listeners = new Set<() => void>();

  const t: Translate = (key, values) => ports.t()(key, { bank: ports.bank, ...values });
  const money = (item: Pick<Transaction, "amount" | "currency">) =>
    formatMoney(item.amount, item.currency, ports.locale());
  const cardName = (card: Card) => cardLabel(card, t);
  const time = (at: number) => new Intl.DateTimeFormat(ports.locale(), { timeStyle: "short" }).format(at);
  const day = (iso: string) =>
    new Intl.DateTimeFormat(ports.locale(), { day: "numeric", month: "long" }).format(Date.parse(iso));
  function emit() {
    for (const listener of listeners) listener();
  }

  function set(change: Partial<ChatState> | ((current: ChatState) => ChatState)) {
    state = typeof change === "function" ? change(state) : { ...state, ...change };
    emit();
  }

  function persist() {
    ports.session.saveChat(settled(state));
  }

  function nextId(prefix: string): string {
    const sequence = state.sequence + 1;
    state = { ...state, sequence };
    return `${prefix}${sequence}`;
  }

  function runner(mine: number): Run {
    return {
      wait: async (ms) => {
        await ports.wait(ms);
        if (mine !== token) throw new Cancelled();
      },
    };
  }

  async function context(r: Run, ms = 0): Promise<Context> {
    const [snapshot] = await Promise.all([ports.load(), r.wait(ms)]);
    return { ...snapshot, session: ports.session.current(), now: ports.now() };
  }

  function append(entry: Entry) {
    set((current) => ({ ...current, entries: [...current.entries, entry] }));
  }

  async function say(r: Run, text: string, options: { ref?: string; hint?: HintKey; speed?: number } = {}) {
    const segments = rich(text);
    const words = wordCount(segments);
    const id = nextId("m");
    append({
      id,
      kind: "clara",
      segments,
      words,
      shown: 0,
      ...(options.ref ? { ref: { viewId: options.ref, ...(options.hint ? { hint: options.hint } : {}) } } : {}),
    });
    for (let shown = 1; shown <= words; shown += 1) {
      await r.wait(options.speed ?? latency.word);
      set((current) => ({
        ...current,
        entries: current.entries.map((entry) => (entry.id === id && entry.kind === "clara" ? { ...entry, shown } : entry)),
      }));
    }
    persist();
    await r.wait(latency.afterSay);
  }

  async function think<T>(r: Run, label: MessageKey, ms: number, work?: () => Promise<T>): Promise<T | undefined> {
    set({ thinking: t(label) });
    try {
      const [result] = await Promise.all([work?.(), r.wait(ms)]);
      return result;
    } finally {
      set({ thinking: null });
    }
  }

  function rest(face: EntityState) {
    set({ face });
  }

  function open(spec: ViewSpec, face: EntityState): string {
    const id = nextId("v");
    set((current) => ({
      ...current,
      views: [...current.views, { id, spec, face }],
      current: id,
      panel: { mode: "docked" },
      face,
      selected: null,
      pick: null,
    }));
    return id;
  }

  async function search(r: Run, status: string, skeleton: Skeleton | null, ms: number): Promise<Context> {
    set({ panel: { mode: "searching", status, skeleton }, selected: null, pick: null });
    return context(r, ms);
  }

  function ask(next: Omit<Ask, "viewId">, viewId: string) {
    set({ ask: { ...next, viewId }, selected: null });
  }

  async function runSteps(r: Run, spec: ViewSpec, status: string, count: number) {
    const id = open(spec, "revisa");
    set((current) => ({
      ...current,
      panel: { mode: "searching", status, skeleton: null },
      steps: { ...current.steps, [id]: 0 },
    }));
    for (let done = 1; done <= count; done += 1) {
      await r.wait(latency.step);
      set((current) => ({ ...current, steps: { ...current.steps, [id]: done } }));
    }
    await r.wait(latency.stepsDone);
  }

  async function greet(r: Run) {
    set({ panel: { mode: "hero" }, current: null, face: "hola" });
    await r.wait(latency.pause);
    await say(r, t("clara.chat.say.greeting"));
  }

  async function unknown(r: Run) {
    await think(r, "clara.chat.think.default", latency.think);
    rest("favor");
    await say(r, t("clara.chat.say.unknown"));
  }

  async function unrecognized(r: Run) {
    await think(r, "clara.chat.think.understanding", latency.think);
    await say(r, t("clara.chat.say.letMeCheck"), { speed: 20 });
    const ctx = await search(r, t("clara.chat.search.movements"), "list", latency.fetchLong);
    const candidate = flaggedCandidate(ctx);
    const list = recentList(ctx, candidate, LIST_SIZE);
    const view = open(
      { kind: "movements", transactionIds: list.map((entry) => entry.transaction_id), candidate: candidate?.transaction_id ?? null },
      candidate ? "confirma" : "orden",
    );
    if (!candidate) {
      await say(r, t("clara.chat.say.pickOne"), { ref: view });
      return;
    }
    ports.session.markReviewed(candidate.transaction_id);
    ask({ kind: "isThis", productId: candidate.product_id, transactionId: candidate.transaction_id }, view);
    await say(
      r,
      t("clara.chat.say.foundOne", {
        merchant: candidate.merchant_name,
        amount: money(candidate),
        when: whenText(candidate.transaction_date, ports.now(), ports.locale(), t).toLocaleLowerCase(ports.locale()),
      }),
      { ref: view, hint: "clara.chat.hint.answer" },
    );
  }

  async function favor(r: Run) {
    await think(r, "clara.chat.think.default", latency.thinkShort);
    rest("favor");
    await say(r, t("clara.chat.say.helpMe"));
  }

  async function charge(r: Run, productId: string, transactionId: string) {
    await think(r, "clara.chat.think.default", latency.thinkShort);
    const ctx = await search(r, t("clara.chat.search.charge"), "detail", latency.fetch);
    const tx = findEntry(ctx, transactionId);
    if (!tx) return notFound(r);
    if (triage(tx, ctx).outcome !== "protect") return explain(r, ctx, tx, "list");
    ports.session.markReviewed(tx.transaction_id);
    const view = open({ kind: "charge", productId, transactionId }, "confirma");
    ask({ kind: "fuiste", productId, transactionId }, view);
    await say(r, t("clara.chat.say.chargeAsk"), { ref: view, hint: "clara.chat.hint.answer" });
  }

  async function notFound(r: Run) {
    set({ panel: state.current ? { mode: "docked" } : { mode: "hero" } });
    rest("favor");
    await say(r, t("clara.chat.say.notFound"));
  }

  async function mine(r: Run, productId: string, transactionId: string) {
    await think(r, "clara.chat.think.saving", latency.thinkLong);
    ports.session.recognize(transactionId);
    ports.session.markReviewed(transactionId);
    const view = open({ kind: "calm", productId, transactionId }, "orden");
    await say(r, t("clara.chat.say.mine"), { ref: view });
  }

  async function protect(r: Run, productId: string, transactionId: string | null, lost: boolean) {
    const ctx = await think(r, "clara.chat.think.protect", latency.thinkLong, () => context(r));
    if (!ctx) return;
    const card = cardOf(ctx, productId);
    if (!card) return notFound(r);
    if (isBlockedCard(productId, ctx)) {
      rest("orden");
      await say(r, t("clara.chat.say.alreadyBlocked", { card: cardName(card) }));
      return handoff(r, ctx, productId, transactionId, lost, caseIdOf(productId, transactionId, ctx));
    }
    const view = open({ kind: "blockConfirm", productId, transactionId, lost }, "protege");
    ask({ kind: "block", productId, transactionId, lost }, view);
    await say(r, t(lost ? "clara.chat.say.protectLost" : "clara.chat.say.protect", { card: cardName(card) }), {
      ref: view,
      hint: "clara.chat.hint.confirm",
    });
  }

  function caseIdOf(productId: string, transactionId: string | null, ctx: Context): string {
    const since = ctx.session.blocks[productId] ?? new Date(ctx.now).toISOString();
    return claimId(`${transactionId ?? productId}#block`, since);
  }

  async function notNow(r: Run, previous: Ask) {
    await think(r, "clara.chat.think.default", latency.thinkShort);
    rest("orden");
    await say(r, t("clara.chat.say.notNow"));
    set({ ask: previous });
  }

  async function block(r: Run, productId: string, transactionId: string | null, lost: boolean) {
    await runSteps(r, { kind: "blockSteps", productId }, t("clara.chat.search.block"), 3);
    const at = ports.now();
    ports.session.block(productId, new Date(at).toISOString());
    const ctx = await context(r, latency.pause);
    const caseId = caseIdOf(productId, transactionId, ctx);
    const view = open({ kind: "blockResult", productId, transactionId, caseId }, "listo");
    await say(r, t("clara.chat.say.blocked", { time: time(at), caseId }), { ref: view });
    await r.wait(500);
    await say(r, t("clara.chat.say.handingOff"));
    await r.wait(latency.pause);
    await handoff(r, ctx, productId, transactionId, lost, caseId);
  }

  async function handoff(
    r: Run,
    ctx: Context,
    productId: string,
    transactionId: string | null,
    lost: boolean,
    caseId: string,
  ) {
    set({ panel: { mode: "calling" }, face: "telefono", selected: null, pick: null });
    await r.wait(latency.call);
    open({ kind: "agent", productId, transactionId, lost, caseId }, "orden");
    append({ id: nextId("m"), kind: "system", text: t("clara.chat.agent.joined", { name: agent.name }) });
    set({ humanTyping: true });
    await r.wait(latency.humanTyping);
    const card = cardOf(ctx, productId);
    const tx = transactionId ? findEntry(ctx, transactionId) : undefined;
    const first = lost
      ? t("clara.chat.agent.firstLost", { card: card ? cardName(card) : "" })
      : tx
        ? t("clara.chat.agent.first", { merchant: tx.merchant_name })
        : t("clara.chat.agent.firstCard", { card: card ? cardName(card) : "" });
    const chips: Chip[] = (
      lost
        ? (["clara.chat.agent.chipLost1", "clara.chat.agent.chipLost2"] as const)
        : (["clara.chat.agent.chip1", "clara.chat.agent.chip2"] as const)
    ).map((key) => ({ label: t(key), input: { type: "reply" } }));
    set({ humanTyping: false, human: { ...agent }, chips, ask: null });
    append({ id: nextId("m"), kind: "human", text: first });
  }

  async function reply(r: Run) {
    set({ humanTyping: true });
    await r.wait(latency.humanReply);
    set({ humanTyping: false });
    append({ id: nextId("m"), kind: "human", text: t("clara.chat.agent.thanks") });
  }

  async function cards(r: Run) {
    await think(r, "clara.chat.think.understanding", latency.think);
    const ctx = await search(r, t("clara.chat.search.cards"), "cards", latency.fetch);
    const view = open({ kind: "cards" }, "orden");
    const blocked = ctx.cards.find((card) => isBlockedCard(card.product_id, ctx));
    await say(
      r,
      blocked ? t("clara.chat.say.cardsBlocked", { card: cardName(blocked) }) : t("clara.chat.say.cardsActive"),
      { ref: view },
    );
  }

  async function card(r: Run, productId: string) {
    await think(r, "clara.chat.think.default", latency.thinkShort);
    const ctx = await context(r);
    const found = cardOf(ctx, productId);
    if (!found) return notFound(r);
    await search(r, t("clara.chat.search.card", { card: cardName(found) }), "detail", latency.fetchShort);
    const view = open({ kind: "card", productId }, "orden");
    const name = cardName(found);
    const flagged = flaggedCandidate({ ...ctx, entries: ctx.entries.filter((entry) => entry.product_id === productId) });
    const claim = openClaims(ctx.session).find((item) => item.product_id === productId);
    if (isBlockedCard(productId, ctx)) return say(r, t("clara.chat.say.cardBlocked", { card: name }), { ref: view });
    if (flagged) {
      rest("confirma");
      return say(r, t("clara.chat.say.cardFlagged", { card: name, merchant: flagged.merchant_name, amount: money(flagged) }), {
        ref: view,
      });
    }
    if (claim) return say(r, t("clara.chat.say.cardClaim", { card: name, merchant: claim.merchant_name }), { ref: view });
    if (isCredit(found) && found.credit_limit && found.current_balance) {
      const percent = Math.round((Number(found.current_balance) / Number(found.credit_limit)) * 100);
      return say(r, t("clara.chat.say.cardCredit", { card: name, percent: String(percent) }), { ref: view });
    }
    return say(
      r,
      t("clara.chat.say.cardDebit", {
        card: name,
        amount: formatMoney(found.current_balance ?? "0", found.currency, ports.locale()),
      }),
      { ref: view },
    );
  }

  async function movement(r: Run, productId: string, transactionId: string, origin: "card" | "list") {
    const ctx = await think(r, "clara.chat.think.movement", latency.think, () => context(r));
    if (!ctx) return;
    const tx = findEntry(ctx, transactionId);
    if (!tx) return notFound(r);
    const outcome = triage(tx, ctx).outcome;
    if (outcome === "inClaim") return claimStatus(r, ctx, transactionId);
    if (outcome === "protect") return charge(r, productId, transactionId);
    return explain(r, ctx, tx, origin);
  }

  function explanation(ctx: Context, tx: Transaction): string[] {
    const verdict = triage(tx, ctx);
    const merchant = tx.merchant_name;
    const card = cardOf(ctx, tx.product_id);
    const stale = verdict.stale ? [t("clara.chat.explain.stale", { merchant, date: day(tx.transaction_date) })] : [];
    switch (verdict.outcome) {
      case "blocked":
        return [t("clara.chat.explain.blocked", { card: card ? cardName(card) : "" })];
      case "refunded":
        return [t("clara.chat.explain.refunded", { merchant })];
      case "neverCharged":
        return [t("clara.chat.explain.neverCharged", { merchant })];
      case "hold":
        return [t("clara.chat.explain.hold", { merchant })];
      case "recognized":
        return [t("clara.chat.explain.recognized", { merchant })];
      case "history":
        return [
          ...stale,
          verdict.prior.length === 1
            ? t("clara.chat.explain.historyOne", { merchant })
            : t("clara.chat.explain.history", { merchant, count: String(verdict.prior.length) }),
        ];
      default:
        return verdict.stale
          ? [t("clara.chat.explain.staleQuestion", { merchant, date: day(tx.transaction_date) })]
          : [t("clara.chat.explain.question", { merchant })];
    }
  }

  async function explain(r: Run, ctx: Context, tx: Transaction, origin: "card" | "list") {
    const view = open({ kind: "movement", productId: tx.product_id, transactionId: tx.transaction_id, origin }, "orden");
    const lines = explanation(ctx, tx);
    for (const [index, line] of lines.entries()) {
      await say(r, line, index === lines.length - 1 ? { ref: view } : {});
    }
  }

  function onView(transactionId: string): string | null {
    const view = state.views.find((item) => item.id === state.current);
    const spec = view?.spec;
    return spec && "transactionId" in spec && spec.transactionId === transactionId ? view.id : null;
  }

  async function unrecognizedMovement(r: Run, productId: string, transactionId: string) {
    const ctx = await think(r, "clara.chat.think.default", latency.thinkShort, () => context(r));
    if (!ctx) return;
    const tx = findEntry(ctx, transactionId);
    if (!tx) return notFound(r);
    const verdict = triage(tx, ctx);
    switch (verdict.outcome) {
      case "inClaim":
        return claimStatus(r, ctx, transactionId);
      case "blocked":
        return protect(r, productId, transactionId, false);
      case "refunded":
      case "neverCharged":
      case "hold": {
        const view = onView(transactionId) ?? open({ kind: "movement", productId, transactionId, origin: "list" }, "orden");
        rest("orden");
        await say(r, t("clara.chat.say.noClaimNeeded"));
        for (const line of explanation(ctx, tx)) await say(r, line, { ref: view });
        return;
      }
      case "history": {
        const view = open({ kind: "history", productId, transactionId }, "confirma");
        ask({ kind: "recognize", productId, transactionId }, view);
        return say(r, t("clara.chat.say.historyAsk", { merchant: tx.merchant_name }), {
          ref: view,
          hint: "clara.chat.hint.answer",
        });
      }
      case "protect":
        return protect(r, productId, transactionId, false);
      default:
        return oneQuestion(r, tx);
    }
  }

  async function oneQuestion(r: Run, tx: Transaction) {
    const view =
      onView(tx.transaction_id) ??
      open({ kind: "movement", productId: tx.product_id, transactionId: tx.transaction_id, origin: "list" }, "confirma");
    rest("confirma");
    ask({ kind: "haveCard", productId: tx.product_id, transactionId: tx.transaction_id }, view);
    await say(r, t("clara.chat.say.oneQuestion", { merchant: tx.merchant_name, amount: money(tx) }), {
      ref: view,
      hint: "clara.chat.hint.answer",
    });
  }

  async function claimOffer(r: Run, productId: string, transactionId: string) {
    const ctx = await think(r, "clara.chat.think.claim", latency.thinkLong, () => context(r));
    if (!ctx) return;
    const tx = findEntry(ctx, transactionId);
    if (!tx) return notFound(r);
    const view = open({ kind: "claimConfirm", productId, transactionId }, "orden");
    ask({ kind: "claim", productId, transactionId }, view);
    await say(r, t("clara.chat.say.claimOffer", { amount: money(tx) }), { ref: view, hint: "clara.chat.hint.confirm" });
  }

  async function claimWrite(r: Run, transactionId: string) {
    const ctx = await context(r);
    const tx = findEntry(ctx, transactionId);
    if (!tx) return notFound(r);
    await runSteps(r, { kind: "claimSteps" }, t("clara.chat.search.claimWrite"), 3);
    const claim =
      claimForTransaction(transactionId, ports.session.current()) ?? claimOf(tx, new Date(ports.now()).toISOString());
    ports.session.addClaim(claim);
    ports.session.markReviewed(transactionId);
    const view = open({ kind: "claimReceipt", claimId: claim.claim_id }, "listo");
    await say(r, t("clara.chat.say.claimOpened", { claimId: claim.claim_id }), { ref: view });
  }

  async function claimNotNow(r: Run) {
    await think(r, "clara.chat.think.default", latency.thinkShort);
    rest("orden");
    await say(r, t("clara.chat.say.claimNotNow"));
  }

  async function claims(r: Run, wanted: string | null) {
    await think(r, "clara.chat.think.understanding", latency.think);
    const ctx = await search(r, t("clara.chat.search.claim"), "timeline", latency.fetch);
    const claim = (wanted ? findClaim(wanted, ctx.session) : undefined) ?? openClaims(ctx.session)[0];
    if (!claim) {
      set({ panel: state.current ? { mode: "docked" } : { mode: "hero" } });
      rest("orden");
      return say(r, t("clara.chat.say.noClaims"));
    }
    return claimStatus(r, ctx, claim.transaction_id);
  }

  async function claimStatus(r: Run, ctx: Context, transactionId: string) {
    const claim = openClaims(ctx.session).find((item) => item.transaction_id === transactionId);
    if (!claim) return notFound(r);
    const view = open({ kind: "claimStatus", claimId: claim.claim_id }, "orden");
    const stage = claimStage(claim, ctx.now);
    await say(
      r,
      t("clara.chat.say.claimStatus", {
        merchant: claim.merchant_name,
        status: t(`claim.status.${stage}`).toLocaleLowerCase(ports.locale()),
      }),
      { ref: view },
    );
  }

  async function answer(r: Run, kind: AskKind, yes: boolean, target?: Ask) {
    const current = target ?? state.ask;
    if (!current || current.kind !== kind) return unknown(r);
    set({ ask: null, selected: null });
    const { productId, transactionId } = current;
    switch (kind) {
      case "isThis":
        return yes && transactionId ? charge(r, productId, transactionId) : favor(r);
      case "fuiste":
        if (!transactionId) return unknown(r);
        return yes ? mine(r, productId, transactionId) : protect(r, productId, transactionId, false);
      case "recognize": {
        if (!transactionId) return unknown(r);
        if (yes) return mine(r, productId, transactionId);
        const ctx = await context(r);
        const tx = findEntry(ctx, transactionId);
        if (!tx) return notFound(r);
        return afterHistory(tx, ctx) === "protect" ? protect(r, productId, transactionId, false) : oneQuestion(r, tx);
      }
      case "haveCard":
        if (!transactionId) return unknown(r);
        return yes ? claimOffer(r, productId, transactionId) : protect(r, productId, transactionId, true);
      case "claim":
        if (!transactionId) return unknown(r);
        return yes ? claimWrite(r, transactionId) : claimNotNow(r);
      case "block":
        return yes ? block(r, productId, transactionId, current.lost ?? false) : notNow(r, current);
    }
  }

  async function text(r: Run, message: string) {
    if (state.human) return reply(r);
    const pending = state.ask;
    const yes = pending ? polarity(message) : null;
    if (pending && yes !== null) {
      set({ inflight: { type: "answer", ask: pending.kind, yes, target: pending } });
      persist();
      return answer(r, pending.kind, yes, pending);
    }
    const intent = intentOf(message);
    if (intent === "cards") return cards(r);
    if (intent === "claims") return claims(r, null);
    const ctx = await context(r);
    const mentioned = mentionedMovement(message, ctx.entries);
    if (intent === "protect") {
      const target = mentioned ?? contextCharge(ctx) ?? flaggedCandidate(ctx);
      if (target) return protect(r, target.product_id, target.transaction_id, false);
      return unrecognized(r);
    }
    if (mentioned) return movement(r, mentioned.product_id, mentioned.transaction_id, "list");
    if (intent === "charge") return unrecognized(r);
    return unknown(r);
  }

  function contextCharge(ctx: Context): Transaction | undefined {
    const spec = state.views.find((view) => view.id === state.current)?.spec;
    return spec && "transactionId" in spec && spec.transactionId ? findEntry(ctx, spec.transactionId) : undefined;
  }

  async function handle(input: Input, r: Run) {
    switch (input.type) {
      case "greet":
        return greet(r);
      case "text":
        return text(r, input.text);
      case "flow":
        return input.flow === "cards" ? cards(r) : unrecognized(r);
      case "claims":
        return claims(r, input.claimId);
      case "charge":
        return charge(r, input.productId, input.transactionId);
      case "card":
        return card(r, input.productId);
      case "movement":
        return movement(r, input.productId, input.transactionId, input.origin);
      case "unrecognized":
        return unrecognizedMovement(r, input.productId, input.transactionId);
      case "notAttempted":
        return protect(r, input.productId, input.transactionId, false);
      case "answer":
        return answer(r, input.ask, input.yes, input.target);
      case "reply":
        return reply(r);
    }
  }

  async function recover(r: Run) {
    set({ thinking: null, humanTyping: false, panel: state.current ? { mode: "docked" } : { mode: "hero" } });
    rest("favor");
    await say(r, t("clara.chat.say.loadFailed"));
  }

  async function drain() {
    if (running) return;
    running = true;
    const mine = token;
    const r = runner(mine);
    set({ busy: true });
    while (mine === token && state.queue.length > 0) {
      const [next, ...remaining] = state.queue;
      set({ queue: remaining, inflight: next ?? null });
      if (!next) continue;
      persist();
      try {
        await handle(next, r);
      } catch (error) {
        if (error instanceof Cancelled) return;
        try {
          await recover(r);
        } catch {
          return;
        }
      }
      if (mine !== token) return;
      set({ inflight: null });
      persist();
    }
    if (mine !== token) return;
    running = false;
    set({ busy: false, thinking: null, humanTyping: false });
    persist();
  }

  function enqueue(input: Input, echo?: string) {
    set((current) => ({
      ...current,
      entries: echo ? [...current.entries, { id: `c${current.sequence + 1}`, kind: "me", text: echo }] : current.entries,
      sequence: echo ? current.sequence + 1 : current.sequence,
      queue: [...current.queue, input],
      chips: echo ? [] : current.chips,
      selected: null,
      pick: null,
    }));
    persist();
    void drain();
  }

  return {
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    current: () => state,
    start: () => {
      if (started) return;
      started = true;
      const saved = ports.session.current().chat;
      if (saved) {
        state = restored(saved);
        emit();
        if (state.queue.length > 0) void drain();
        return;
      }
      enqueue({ type: "greet" });
    },
    send: (message: string) => {
      const trimmed = message.trim();
      if (trimmed) enqueue({ type: "text", text: trimmed }, trimmed);
    },
    input: enqueue,
    select: (id: string) => {
      set({ selected: id });
    },
    confirm: (choice: BarChoice) => {
      if (state.selected !== choice.id) return;
      enqueue(choice.input, choice.echo);
    },
    pick: (next: PanelPick) => {
      set({ pick: next, selected: null });
    },
    cancelPick: () => {
      set({ pick: null });
    },
    confirmPick: () => {
      const chosen = state.pick;
      if (chosen) enqueue(chosen.input, chosen.echo);
    },
    navigate: (spec: ViewSpec, face: EntityState) => {
      if (state.panel.mode === "searching" || state.panel.mode === "calling") return;
      open(spec, face);
      persist();
    },
    restore: (viewId: string) => {
      const view = state.views.find((item) => item.id === viewId);
      if (!view || state.panel.mode === "searching" || state.panel.mode === "calling") return;
      set({ current: viewId, panel: { mode: "docked" }, face: view.face, selected: null, pick: null });
      persist();
    },
    reset: () => {
      token += 1;
      running = false;
      started = false;
      state = initialChat;
      emit();
    },
  };
}

export type MockChat = ReturnType<typeof createMockChat>;
