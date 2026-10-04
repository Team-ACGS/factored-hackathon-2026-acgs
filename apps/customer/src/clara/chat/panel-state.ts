import type { EntityMode, EntityState } from "@clara/ui/lib/entity";

import { confirmKinds, type ChatMessage, type Readings, type Row, type ViewPart } from "../../chat/conversation";

export type ViewSpec =
  | { kind: "movements"; rows: Row[]; readings: Readings }
  | { kind: "cards"; cards: string[] }
  | { kind: "card"; productId: string }
  | { kind: "movement"; row: Row }
  | { kind: "charge"; row: Row; readings: Readings }
  | { kind: "history"; rows: Row[]; readings: Readings }
  | { kind: "case"; cases: string[] };

export interface PanelView {
  id: string;
  spec: ViewSpec;
}

export interface PanelState {
  following: string | null;
  selected: string | null;
  trail: ViewSpec[];
}

export type PanelAction =
  | { type: "follow"; id: string | null }
  | { type: "restore"; id: string }
  | { type: "open"; spec: ViewSpec }
  | { type: "back" };

export const initialPanel: PanelState = { following: null, selected: null, trail: [] };

export function specOf(part: ViewPart): ViewSpec | null {
  const [row] = part.rows;
  const [card] = part.cards;
  switch (part.kind) {
    case "movements":
      return part.rows.length ? { kind: "movements", rows: part.rows, readings: part.readings } : null;
    case "history":
      return part.rows.length ? { kind: "history", rows: part.rows, readings: part.readings } : null;
    case "cards":
      return part.cards.length ? { kind: "cards", cards: part.cards } : null;
    case "card":
      return card ? { kind: "card", productId: card } : null;
    case "movement":
      return row ? { kind: "movement", row } : null;
    case "charge":
      return row ? { kind: "charge", row, readings: part.readings } : null;
    case "case":
      return part.cases.length ? { kind: "case", cases: part.cases } : null;
  }
}

export function panelViews(messages: readonly ChatMessage[]): PanelView[] {
  return messages.flatMap((message) => {
    const spec = message.senderType === "assistant" && message.view ? specOf(message.view) : null;
    return spec ? [{ id: message.messageId, spec }] : [];
  });
}

export function reducePanel(state: PanelState, action: PanelAction): PanelState {
  switch (action.type) {
    case "follow":
      return { following: action.id, selected: action.id, trail: [] };
    case "restore":
      return { ...state, selected: action.id, trail: [] };
    case "open":
      return { ...state, trail: [...state.trail, action.spec] };
    case "back":
      return { ...state, trail: state.trail.slice(0, -1) };
  }
}

export function shownView(state: PanelState, views: readonly PanelView[]): PanelView | null {
  const base = views.find((view) => view.id === state.selected) ?? null;
  const drilled = state.trail.at(-1);
  if (!base) return null;
  return drilled ? { id: `${base.id}#${state.trail.length}`, spec: drilled } : base;
}

export type PanelMode = "hero" | "docked" | "working";

export function panelMode(shown: PanelView | null, working: boolean, asking: boolean): PanelMode {
  if (working) return "working";
  return shown || asking ? "docked" : "hero";
}

export function entityMode(mode: PanelMode): EntityMode {
  if (mode === "working") return "work";
  return mode === "docked" ? "dock" : "hero";
}

export interface StoryFaces {
  working?: EntityState;
  arriving?: EntityState;
  settled?: EntityState;
}

interface FaceInputs {
  typing: boolean;
  asking: boolean;
  arriving: boolean;
  working: EntityState;
  story?: StoryFaces;
}

export function faceOf(mode: PanelMode, { typing, asking, arriving, working, story = {} }: FaceInputs): EntityState {
  if (mode === "working") return story.working ?? working;
  if (arriving) return story.arriving ?? "hola";
  if (story.settled) return story.settled;
  if (asking) return "escucha";
  if (mode === "docked") return "orden";
  return typing ? "escucha" : "hola";
}

const confirming: readonly string[] = ["was_it_you", ...confirmKinds];

export function storyFaces(messages: readonly ChatMessage[]): StoryFaces {
  const last = messages.at(-1);
  if (!last) return {};
  if (last.senderType === "customer") {
    const tap = last.input && "ask_id" in last.input ? last.input : null;
    const asked = tap && messages.find((message) => message.messageId === tap.ask_id);
    return tap?.option === "yes" && asked && asked.ask?.kind === "block_card" ? { working: "protege" } : {};
  }
  const opened = last.effects.find((effect) => effect.type === "case_opened");
  const blocked = last.effects.some((effect) => effect.type === "card_blocked");
  if (opened?.type === "case_opened") {
    if (opened.caseType === "claim") return { arriving: "listo", settled: "listo" };
    return { arriving: blocked ? "listo" : "telefono", settled: "telefono" };
  }
  if (last.ask && confirming.includes(last.ask.kind)) return { settled: "confirma" };
  return {};
}

export function fromEarlier(messages: readonly ChatMessage[], selected: string | null): boolean {
  const reply = messages.findLast((message) => message.senderType === "assistant");
  return selected !== null && reply !== undefined && reply.messageId !== selected;
}

export function pickIds(asked: ChatMessage | null, shown: PanelView | null): ReadonlySet<string> | null {
  const ask = asked?.ask;
  if (!asked || ask?.kind !== "which_one" || shown?.id !== asked.messageId) return null;
  const { spec } = shown;
  const ids =
    spec.kind === "movements" || spec.kind === "history"
      ? new Set(spec.rows.map((row) => row.transactionId))
      : spec.kind === "cards"
        ? new Set(spec.cards)
        : null;
  if (!ids) return null;
  return ask.options.every((option) => ids.has(option.id)) ? new Set(ask.options.map((option) => option.id)) : null;
}
