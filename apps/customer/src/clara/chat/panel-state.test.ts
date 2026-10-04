import { describe, expect, it } from "vitest";

import type { AskKind, ChatMessage, ViewPart } from "../../chat/conversation";
import {
  entityMode,
  faceOf,
  initialPanel,
  latestView,
  panelMode,
  panelViews,
  pickIds,
  reducePanel,
  shownView,
  specOf,
  storyFaces,
  type PanelState,
} from "./panel-state";

function clara(id: string, view: ViewPart | null): ChatMessage {
  return {
    roomId: "r",
    messageId: id,
    senderType: "assistant",
    text: "",
    says: [],
    view,
    ask: null,
    sentAt: id,
    createdAt: id,
    delivery: "sent",
    effects: [],
  };
}

const rows = [{ productId: "p1", transactionId: "t1" }];
const movements: ViewPart = { kind: "movements", rows, cards: [], cases: [], readings: {} };
const cards: ViewPart = { kind: "cards", rows: [], cards: ["p1", "p2"], cases: [], readings: {} };

describe("clara's panel", () => {
  it("lists the views of Clara's answers and skips one with nothing to show", () => {
    const views = panelViews([clara("m1", movements), clara("m2", null), clara("m3", { ...cards, cards: [] }), clara("m4", cards)]);

    expect(views.map((view) => view.id)).toEqual(["m1", "m4"]);
  });

  it("follows the newest view, reopens a past one and drills down without a turn", () => {
    const views = panelViews([clara("m1", movements), clara("m2", cards)]);
    const steps: Parameters<typeof reducePanel>[1][] = [
      { type: "follow", id: "m2" },
      { type: "restore", id: "m1" },
      { type: "open", spec: { kind: "movement", row: { productId: "p1", transactionId: "t1" } } },
    ];
    const states = steps.reduce<PanelState[]>((all, step) => [...all, reducePanel(all.at(-1) ?? initialPanel, step)], []);

    expect(states.map((state) => shownView(state, views)?.spec.kind)).toEqual(["cards", "movements", "movement"]);
    const back = reducePanel(states[2] ?? initialPanel, { type: "back" });
    expect(shownView(back, views)?.id).toBe("m1");
  });

  it("works alone in the panel while Clara reads and docks once a view is shown", () => {
    const shown = { id: "m1", spec: specOf(movements) ?? { kind: "cards", cards: [] } };

    expect([panelMode(null, false, false), panelMode(shown, false, false), panelMode(shown, true, false)]).toEqual([
      "hero",
      "docked",
      "working",
    ]);
    expect(panelMode(null, false, true)).toBe("docked");
    expect(panelMode(null, true, true)).toBe("working");
    expect(entityMode("working")).toBe("work");
  });

  it("checks while working, greets the reply, listens on an open ask and rests on a view", () => {
    const calm = { typing: false, asking: false, arriving: false, working: "revisa" as const };

    expect(faceOf("working", { ...calm, asking: true, arriving: true })).toBe("revisa");
    expect(faceOf("working", { ...calm, working: "escucha" })).toBe("escucha");
    expect(faceOf("docked", { ...calm, arriving: true })).toBe("hola");
    expect(faceOf("docked", { ...calm, asking: true })).toBe("escucha");
    expect(faceOf("docked", calm)).toBe("orden");
    expect(faceOf("hero", { ...calm, typing: true })).toBe("escucha");
  });

  it("follows only the latest reply's view, so a reply without one leaves the panel to Clara", () => {
    const answered = [clara("m1", movements), clara("m2", null)];
    const latest = (messages: ChatMessage[]) => latestView(messages, panelViews(messages));

    expect(latest(answered)).toBeNull();
    expect(latest([clara("m1", movements)])).toBe("m1");
    expect(latest([clara("m1", movements), clara("m2", cards)])).toBe("m2");
    const followed = reducePanel(reducePanel(initialPanel, { type: "follow", id: "m1" }), {
      type: "follow",
      id: latest(answered),
    });
    expect(shownView(followed, panelViews(answered))).toBeNull();
    const reopened = reducePanel(followed, { type: "restore", id: "m1" });
    expect(shownView(reopened, panelViews(answered))?.id).toBe("m1");
  });

  it("shows a handoff card with its subject and the points the person gets", () => {
    const handoff: ViewPart = {
      kind: "handoff",
      rows: [],
      cards: [],
      cases: ["c1"],
      readings: { points: ["Pide hablar con una persona."] },
    };

    expect(specOf(handoff)).toEqual({
      kind: "handoff",
      subject: { kind: "case", cases: ["c1"] },
      points: ["Pide hablar con una persona."],
    });
    expect(specOf({ ...handoff, cases: [], readings: {} })).toEqual({ kind: "handoff", subject: null, points: [] });
  });
});

describe("a pick in the view", () => {
  const rows = ["t1", "t2", "t3"].map((transactionId) => ({ productId: "p1", transactionId }));
  const view: ViewPart = { kind: "movements", rows, cards: [], cases: [], readings: {} };
  const asking = (ids: string[]) => ({
    ...clara("m2", view),
    ask: { kind: "which_one" as const, prompt: null, note: false, options: ids.map((id) => ({ id, label: id })) },
  });

  it("offers the rows of the ask's own list", () => {
    const asked = asking(["t1", "t3"]);
    const [shown] = panelViews([asked]);

    expect([...(pickIds(asked, shown ?? null) ?? [])]).toEqual(["t1", "t3"]);
  });

  it("keeps chips when the list is another message's or misses an option", () => {
    const asked = asking(["t1", "t9"]);
    const [shown] = panelViews([asked]);
    const [other] = panelViews([clara("m1", view)]);

    expect(pickIds(asked, shown ?? null)).toBeNull();
    expect(pickIds(asking(["t1"]), other ?? null)).toBeNull();
  });

  it("offers the active cards of a lost-card ask in the cards view, even one", () => {
    const cards: ViewPart = { kind: "cards", rows: [], cards: ["c1", "c2", "c3"], cases: [], readings: {} };
    const asked = {
      ...clara("m3", cards),
      ask: { kind: "which_one" as const, prompt: null, note: false, options: [{ id: "c2", label: "c2" }] },
    };
    const [shown] = panelViews([asked]);

    expect([...(pickIds(asked, shown ?? null) ?? [])]).toEqual(["c2"]);
  });
});

describe("clara's face in the story", () => {
  const ask = (kind: AskKind) => ({ kind, prompt: null, note: false, options: [{ id: "yes", label: "Sí" }] });
  const customer = (id: string, input?: ChatMessage["input"]): ChatMessage => ({
    ...clara(id, null),
    senderType: "customer",
    ...(input ? { input } : {}),
  });

  it("wants to confirm on a story question and on the block confirmation", () => {
    expect(storyFaces([{ ...clara("m1", null), ask: ask("was_it_you") }])).toEqual({ settled: "confirma" });
    expect(storyFaces([{ ...clara("m1", null), ask: ask("block_card") }])).toEqual({ settled: "confirma" });
    expect(storyFaces([{ ...clara("m1", null), ask: ask("which_one") }])).toEqual({});
  });

  it("protects while the confirmed block runs, never for a declined one", () => {
    const asked = { ...clara("m1", null), ask: ask("block_card") };

    expect(storyFaces([asked, customer("m2", { ask_id: "m1", option: "yes" })])).toEqual({ working: "protege" });
    expect(storyFaces([asked, customer("m2", { ask_id: "m1", option: "no" })])).toEqual({});
  });

  it("is done on the block and hands over on the case, and stays done on a claim", () => {
    const handedOff = {
      ...clara("m3", null),
      effects: [
        { type: "card_blocked" as const, productId: "p1" },
        { type: "case_opened" as const, complaintId: "m1", caseType: "fraud" },
      ],
    };
    const claim = { ...clara("m3", null), effects: [{ type: "case_opened" as const, complaintId: "m1", caseType: "claim" }] };

    expect(storyFaces([handedOff])).toEqual({ arriving: "listo", settled: "telefono" });
    expect(storyFaces([claim])).toEqual({ arriving: "listo", settled: "listo" });
    const calm = { typing: false, asking: false, arriving: true, working: "revisa" as const };
    expect(faceOf("docked", { ...calm, story: storyFaces([handedOff]) })).toBe("listo");
    expect(faceOf("docked", { ...calm, arriving: false, story: storyFaces([handedOff]) })).toBe("telefono");
  });
});
