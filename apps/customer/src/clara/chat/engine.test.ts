import { describe, expect, it } from "vitest";

import type { Transaction } from "../../bank/types";
import { translator } from "../../i18n/locale";
import { claimOf } from "../claims";
import { cardAt, purchase, setupAt } from "../fixtures";
import { cardLock, claimForTransaction } from "../overlay";
import { createClaraSession, memoryStorage, type ClaraSession } from "../session";
import { barOf, type BarOption } from "./bar";
import { createMockChat, type MockChat } from "./engine";
import type { Context } from "./insight";
import { referenceOf } from "./references";
import { currentView, type ChatState, type Entry } from "./state";
import { plain } from "./text";

const t = translator("en");
const credit = cardAt("Tarjeta Crédito", setupAt, { product_number: "**** 4821", credit_limit: "45000.00" });
const debit = cardAt("Tarjeta Débito", setupAt + 1);
const cards = [credit, debit];

function harness(
  entries: Transaction[],
  session: ClaraSession = openSession(),
  wait: () => Promise<void> = () => Promise.resolve(),
  now = setupAt,
) {
  const chat = createMockChat({
    load: () => Promise.resolve({ profile: { country: "MX" }, cards, entries }),
    session,
    t: () => t,
    locale: () => "en",
    now: () => now,
    wait,
    bank: "LATAM Bank",
  });
  const ctx = (): Context => ({ profile: { country: "MX" }, cards, entries, session: session.current(), now: setupAt });
  return { chat, session, ctx };
}

function openSession(storage = memoryStorage()): ClaraSession {
  const session = createClaraSession(storage);
  session.open("customer-a");
  return session;
}

async function idle(chat: MockChat) {
  for (let turn = 0; turn < 5000; turn += 1) {
    const state = chat.current();
    if (!state.busy && state.queue.length === 0) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("the chat never settled");
}

const said = (state: ChatState) =>
  state.entries
    .filter((entry): entry is Extract<Entry, { kind: "clara" }> => entry.kind === "clara")
    .map((entry) => plain(entry.segments));
const mine = (state: ChatState) => state.entries.filter((entry) => entry.kind === "me").map((entry) => entry.kind === "me" && entry.text);

function options(chat: MockChat, ctx: Context): BarOption[] {
  const bar = barOf(chat.current(), ctx, t);
  if (bar?.kind !== "choose") throw new Error(`expected a choice, got ${bar?.kind ?? "no bar"}`);
  return bar.options;
}

async function choose(chat: MockChat, ctx: Context, id: string) {
  const option = options(chat, ctx).find((item) => item.id === id);
  if (!option) throw new Error(`no option ${id} in ${options(chat, ctx).map((item) => item.id).join()}`);
  chat.select(option.id);
  chat.confirm(option);
  await idle(chat);
}

const kindOf = (chat: MockChat) => currentView(chat.current())?.spec.kind;

async function started(entries: Transaction[], session?: ClaraSession, wait?: () => Promise<void>) {
  const setup = harness(entries, session, wait);
  setup.chat.start();
  await idle(setup.chat);
  return setup;
}

describe("mock chat", () => {
  const usual = [purchase(credit, 20), purchase(debit, 25), purchase(credit, 30)];
  const flagged = purchase(credit, 1, { merchant_name: "GLOBALPAY*DIGITALSVC", fraud_score: "87.00", channel: "Web" });

  it("greets once and keeps the conversation in the session for the next visit", async () => {
    const storage = memoryStorage();
    const { chat } = await started(usual, openSession(storage));
    chat.start();
    await idle(chat);

    expect(said(chat.current())).toHaveLength(1);

    const again = harness(usual, openSession(storage)).chat;
    again.start();
    await idle(again);
    expect(said(again.current())).toEqual(said(chat.current()));
  });

  it("walks the flagged charge to a block the bank pages show, then hands off to a person", async () => {
    const { chat, session, ctx } = await started([flagged, ...usual]);

    chat.input({ type: "flow", flow: "unrecognized" }, t("clara.shortcut.unrecognized"));
    await idle(chat);
    expect(kindOf(chat)).toBe("movements");
    expect(chat.current().ask).toMatchObject({ kind: "isThis", transactionId: flagged.transaction_id });
    expect(session.current().reviewed).toContain(flagged.transaction_id);

    await choose(chat, ctx(), "isThis:yes");
    expect(kindOf(chat)).toBe("charge");

    await choose(chat, ctx(), "fuiste:no");
    expect(kindOf(chat)).toBe("blockConfirm");
    expect(cardLock(credit, session.current()).blocked).toBe(false);

    await choose(chat, ctx(), "block:yes");
    expect(cardLock(credit, session.current())).toEqual({ blocked: true, since: new Date(setupAt).toISOString() });
    expect(cardLock(debit, session.current()).blocked).toBe(false);
    expect(chat.current().views.map((view) => view.spec.kind)).toContain("blockResult");
    expect(kindOf(chat)).toBe("agent");
    expect(chat.current().human).not.toBeNull();
    expect(chat.current().entries.at(-1)?.kind).toBe("human");
    expect(chat.current().chips).toHaveLength(2);
  });

  it("opens a claim with the one question, and the claim reaches the bank overlay", async () => {
    const plainCharge = purchase(debit, 3, { merchant_name: "Soriana Hiper" });
    const { chat, session, ctx } = await started([plainCharge, ...usual]);

    chat.input({ type: "movement", productId: debit.product_id, transactionId: plainCharge.transaction_id, origin: "card" });
    await idle(chat);
    expect(kindOf(chat)).toBe("movement");

    await choose(chat, ctx(), "movement:unrecognized");
    expect(chat.current().ask?.kind).toBe("haveCard");

    await choose(chat, ctx(), "haveCard:yes");
    expect(kindOf(chat)).toBe("claimConfirm");
    expect(claimForTransaction(plainCharge.transaction_id, session.current())).toBeUndefined();

    await choose(chat, ctx(), "claim:yes");
    const claim = claimForTransaction(plainCharge.transaction_id, session.current());
    expect(claim?.product_id).toBe(debit.product_id);
    expect(currentView(chat.current())?.spec).toEqual({ kind: "claimReceipt", claimId: claim?.claim_id });
  });

  it("protects the card the customer no longer has, any card", async () => {
    const plainCharge = purchase(debit, 3, { merchant_name: "Soriana Hiper" });
    const { chat, session } = await started([plainCharge, ...usual]);

    chat.input({ type: "unrecognized", productId: debit.product_id, transactionId: plainCharge.transaction_id });
    await idle(chat);
    chat.send("No la tengo");
    await idle(chat);
    expect(chat.current().ask).toMatchObject({ kind: "block", productId: debit.product_id, lost: true });

    chat.send("sí, bloquéala");
    await idle(chat);
    expect(cardLock(debit, session.current()).blocked).toBe(true);
  });

  it("never runs a selection until it is confirmed", async () => {
    const { chat, ctx } = await started(usual);
    const before = chat.current();
    const [first, second] = options(chat, ctx());
    if (!first || !second) throw new Error("expected starters");

    chat.select(first.id);
    chat.confirm(second);
    await idle(chat);
    expect(chat.current().entries).toEqual(before.entries);
    expect(chat.current().queue).toEqual([]);

    chat.pick({ prompt: "", label: "", cta: "", echo: "See my card", input: { type: "card", productId: credit.product_id }, target: credit.product_id });
    await idle(chat);
    expect(chat.current().entries).toEqual(before.entries);
    chat.cancelPick();
    expect(barOf(chat.current(), ctx(), t)?.kind).toBe("choose");

    chat.select(first.id);
    chat.confirm(first);
    await idle(chat);
    expect(mine(chat.current())).toEqual([first.echo]);
  });

  it("queues what the customer sends while Clara writes and answers all of it in order", async () => {
    const seeded = claimOf(usual[1] as Transaction, "2026-08-10T10:00:00.000Z");
    const session = openSession();
    session.resolveSeeded(seeded);
    const { chat } = harness(usual, session);

    chat.start();
    chat.send("I want to see my cards");
    chat.send("How is my claim going?");
    expect(mine(chat.current())).toEqual(["I want to see my cards", "How is my claim going?"]);
    expect(chat.current().queue).toHaveLength(2);

    await idle(chat);
    expect(chat.current().views.map((view) => view.spec.kind)).toEqual(["cards", "claimStatus"]);
    expect(said(chat.current()).at(-1)).toContain(seeded.merchant_name);
  });

  it("reopens a past view through its reference with the current state", async () => {
    const { chat, ctx } = await started([flagged, ...usual]);
    chat.input({ type: "flow", flow: "unrecognized" });
    await idle(chat);
    const list = chat.current().current ?? "";
    const reference = chat.current().entries.findLast((entry) => entry.kind === "clara" && entry.ref);
    if (reference?.kind !== "clara" || !reference.ref) throw new Error("expected a reference");
    expect(referenceOf(reference.ref, chat.current())).toEqual({ state: "current", hint: "clara.chat.hint.answer" });

    await choose(chat, ctx(), "isThis:yes");
    await choose(chat, ctx(), "fuiste:no");
    await choose(chat, ctx(), "block:yes");
    expect(referenceOf(reference.ref, chat.current())?.state).toBe("past");

    chat.restore(list);
    expect(chat.current().current).toBe(list);
    expect(referenceOf(reference.ref, chat.current())).toEqual({ state: "current", hint: null });
    expect(barOf(chat.current(), ctx(), t)).toBeNull();
  });

  it("explains the gap cases instead of opening a claim", async () => {
    const refunded = purchase(credit, 4, { merchant_name: "Liverpool", transaction_status: "Reversed" });
    const earlier = purchase(credit, 80, { merchant_name: "Uber Eats" });
    const stale = purchase(debit, 60, { merchant_name: "Uber Eats", transaction_status: "Pending" });
    const { chat, ctx } = await started([refunded, earlier, stale, ...usual]);

    chat.send("¿qué es lo de Liverpool?");
    await idle(chat);
    expect(said(chat.current()).at(-1)).toContain("refunded");
    expect(barOf(chat.current(), ctx(), t)).toBeNull();

    chat.input({ type: "movement", productId: debit.product_id, transactionId: stale.transaction_id, origin: "list" });
    await idle(chat);
    const lines = said(chat.current()).slice(-2).join(" ");
    expect(lines).toContain("counts as charged");
    expect(lines).not.toMatch(/hold|temporary/i);

    await choose(chat, ctx(), "movement:unrecognized");
    expect(kindOf(chat)).toBe("history");
    expect(chat.current().ask?.kind).toBe("recognize");
  });

  it("explains an old pending charge with no history as charged, never approved or temporary", async () => {
    const stale = purchase(debit, 98, { merchant_name: "Uber Eats", transaction_status: "Pending" });
    const { chat, ctx } = await started([stale, ...usual]);

    chat.input({ type: "movement", productId: debit.product_id, transactionId: stale.transaction_id, origin: "list" });
    await idle(chat);
    const line = said(chat.current()).at(-1) ?? "";
    expect(line).toContain("counts as charged");
    expect(line).not.toMatch(/approved|hold|temporary|nothing unusual/i);
    expect(options(chat, ctx()).map((option) => option.id)).toEqual(["movement:unrecognized"]);
  });

  it("applies a back link at once while Clara writes, never while she searches", async () => {
    let hold = false;
    const gate = () => (hold ? new Promise<void>(() => undefined) : Promise.resolve());
    const { chat } = await started(usual, undefined, gate);
    chat.input({ type: "card", productId: credit.product_id });
    await idle(chat);
    const card = chat.current().current;

    hold = true;
    chat.send("hola");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(chat.current().busy).toBe(true);
    chat.navigate({ kind: "cards" }, "orden");
    expect(kindOf(chat)).toBe("cards");
    expect(chat.current().current).not.toBe(card);
  });

  it.each([
    ["a block before it is written", "block:yes", (session: ClaraSession) => session.current().blocks[credit.product_id] === undefined],
    ["a claim after it is written", "claim:yes", (session: ClaraSession) => session.current().claims.length > 0],
  ])("finishes %s exactly once after a reload mid-flow", async (_, confirm, hangWhen) => {
    const plainCharge = purchase(credit, 3, { merchant_name: "Soriana Hiper" });
    const entries = [flagged, plainCharge, ...usual];
    const storage = memoryStorage();
    const session = openSession(storage);
    let armed = false;
    const gate = () => (armed && hangWhen(session) && session.current().chat?.inflight ? new Promise<void>(() => undefined) : Promise.resolve());
    const { chat, ctx } = await started(entries, session, gate);
    if (confirm === "block:yes") {
      chat.input({ type: "flow", flow: "unrecognized" });
      await idle(chat);
      await choose(chat, ctx(), "isThis:yes");
      await choose(chat, ctx(), "fuiste:no");
    } else {
      chat.input({ type: "unrecognized", productId: credit.product_id, transactionId: plainCharge.transaction_id });
      await idle(chat);
      await choose(chat, ctx(), "haveCard:yes");
    }

    armed = true;
    const option = options(chat, ctx()).find((item) => item.id === confirm);
    if (!option) throw new Error(`no option ${confirm}`);
    chat.select(option.id);
    chat.confirm(option);
    for (let turn = 0; turn < 200; turn += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    expect(chat.current().busy).toBe(true);

    const reloaded = openSession(storage);
    const again = harness(entries, reloaded, undefined, setupAt + 60_000).chat;
    again.start();
    await idle(again);

    const result = confirm === "block:yes" ? "blockResult" : "claimReceipt";
    expect(again.current().views.filter((view) => view.spec.kind === result)).toHaveLength(1);
    if (confirm === "block:yes") {
      expect(cardLock(credit, reloaded.current()).blocked).toBe(true);
      expect(kindOf(again)).toBe("agent");
    } else {
      expect(reloaded.current().claims).toEqual(session.current().claims);
      expect(reloaded.current().claims).toHaveLength(1);
    }
    expect(again.current().inflight).toBeNull();
    expect(again.current().queue).toEqual([]);
  });

  it("stops a running flow when the demo is reset", async () => {
    const { chat } = await started(usual);
    chat.input({ type: "flow", flow: "cards" });
    chat.reset();
    await idle(chat);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(chat.current().entries).toEqual([]);
    expect(chat.current().views).toEqual([]);
  });
});
