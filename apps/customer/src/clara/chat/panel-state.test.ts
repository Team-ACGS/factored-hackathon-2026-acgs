import { describe, expect, it } from "vitest";

import type { ChatMessage, ViewPart } from "../../chat/conversation";
import {
  entityMode,
  faceOf,
  fromEarlier,
  initialPanel,
  panelMode,
  panelViews,
  reducePanel,
  shownView,
  specOf,
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

  it("marks a view that is not the latest reply's own", () => {
    const answered = [clara("m1", movements), clara("m2", null)];

    expect(fromEarlier(answered, "m1")).toBe(true);
    expect(fromEarlier([clara("m1", movements)], "m1")).toBe(false);
    expect(fromEarlier([clara("m1", movements), clara("m2", cards)], "m1")).toBe(true);
    expect(fromEarlier(answered, null)).toBe(false);
  });
});
