import type { EntityMode, EntityState } from "@clara/ui/lib/entity";

import type { ChatMessage, Readings, Row, ViewPart } from "../../chat/conversation";

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

export type PanelMode = "hero" | "docked" | "searching";

export function panelMode(shown: PanelView | null, thinking: boolean): PanelMode {
  if (thinking) return "searching";
  return shown ? "docked" : "hero";
}

export function entityMode(mode: PanelMode): EntityMode {
  if (mode === "searching") return "dot";
  return mode === "docked" ? "dock" : "hero";
}

export function faceOf(mode: PanelMode, typing: boolean, asking: boolean): EntityState {
  if (mode === "searching") return "revisa";
  if (asking) return "confirma";
  if (mode === "docked") return "orden";
  return typing ? "escucha" : "hola";
}
