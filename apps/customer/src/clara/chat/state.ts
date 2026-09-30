import type { EntityState } from "@clara/ui/lib/entity";

export interface Segment {
  text: string;
  strong?: boolean;
}

export type HintKey = "clara.chat.hint.answer" | "clara.chat.hint.confirm";

export interface Reference {
  viewId: string;
  hint?: HintKey;
}

export type Entry =
  | { id: string; kind: "me"; text: string; failed?: boolean }
  | { id: string; kind: "clara"; segments: Segment[]; words: number; shown: number; ref?: Reference }
  | { id: string; kind: "human"; text: string }
  | { id: string; kind: "system"; text: string };

export type Origin = "card" | "list";

export type ViewSpec =
  | { kind: "movements"; transactionIds: string[]; candidate: string | null }
  | { kind: "cards" }
  | { kind: "card"; productId: string }
  | { kind: "movement"; productId: string; transactionId: string; origin: Origin }
  | { kind: "charge"; productId: string; transactionId: string }
  | { kind: "history"; productId: string; transactionId: string }
  | { kind: "calm"; productId: string; transactionId: string }
  | { kind: "blockConfirm"; productId: string; transactionId: string | null; lost: boolean }
  | { kind: "blockSteps"; productId: string }
  | { kind: "blockResult"; productId: string; transactionId: string | null; caseId: string }
  | { kind: "claimConfirm"; productId: string; transactionId: string }
  | { kind: "claimSteps" }
  | { kind: "claimReceipt"; claimId: string }
  | { kind: "claimStatus"; claimId: string }
  | { kind: "agent"; productId: string; transactionId: string | null; lost: boolean; caseId: string };

export type ViewKind = ViewSpec["kind"];

export interface View {
  id: string;
  spec: ViewSpec;
  face: EntityState;
}

export type Skeleton = "list" | "cards" | "detail" | "timeline";

export type Panel =
  | { mode: "hero" }
  | { mode: "docked" }
  | { mode: "searching"; status: string; skeleton: Skeleton | null }
  | { mode: "calling" };

export type AskKind = "isThis" | "fuiste" | "recognize" | "haveCard" | "claim" | "block";

export interface Ask {
  kind: AskKind;
  viewId: string;
  productId: string;
  transactionId: string | null;
  lost?: boolean;
}

export type Flow = "unrecognized" | "cards";

export type Input =
  | { type: "greet" }
  | { type: "text"; text: string }
  | { type: "flow"; flow: Flow }
  | { type: "claims"; claimId: string | null }
  | { type: "charge"; productId: string; transactionId: string }
  | { type: "card"; productId: string }
  | { type: "movement"; productId: string; transactionId: string; origin: Origin }
  | { type: "unrecognized"; productId: string; transactionId: string }
  | { type: "notAttempted"; productId: string; transactionId: string }
  | { type: "answer"; ask: AskKind; yes: boolean; target?: Ask }
  | { type: "reply" };

export interface BarChoice {
  id: string;
  input: Input;
  echo: string;
}

export interface Chip {
  label: string;
  input: Input;
}

export interface PanelPick {
  prompt: string;
  label: string;
  cta: string;
  echo: string;
  input: Input;
  target: string;
}

export interface Human {
  name: string;
  initials: string;
}

export interface ChatState {
  entries: Entry[];
  views: View[];
  current: string | null;
  panel: Panel;
  face: EntityState;
  ask: Ask | null;
  steps: Record<string, number>;
  thinking: string | null;
  humanTyping: boolean;
  human: Human | null;
  chips: Chip[];
  queue: Input[];
  inflight: Input | null;
  busy: boolean;
  selected: string | null;
  pick: PanelPick | null;
  sequence: number;
}

export type PersistedChat = Omit<ChatState, "thinking" | "humanTyping" | "busy" | "selected" | "pick">;

export const initialChat: ChatState = {
  entries: [],
  views: [],
  current: null,
  panel: { mode: "hero" },
  face: "hola",
  ask: null,
  steps: {},
  thinking: null,
  humanTyping: false,
  human: null,
  chips: [],
  queue: [],
  inflight: null,
  busy: false,
  selected: null,
  pick: null,
  sequence: 0,
};

export function settled(state: ChatState): PersistedChat {
  const { thinking: _thinking, humanTyping: _typing, busy: _busy, selected: _selected, pick: _pick, ...kept } = state;
  const panel: Panel =
    state.panel.mode === "searching" || state.panel.mode === "calling"
      ? state.current
        ? { mode: "docked" }
        : { mode: "hero" }
      : state.panel;
  return {
    ...kept,
    panel,
    entries: state.entries.map((entry) => (entry.kind === "clara" ? { ...entry, shown: entry.words } : entry)),
  };
}

export function restored(persisted: PersistedChat): ChatState {
  const queue = persisted.inflight ? [persisted.inflight, ...persisted.queue] : persisted.queue;
  return {
    ...initialChat,
    ...persisted,
    queue,
    inflight: null,
    thinking: null,
    humanTyping: false,
    busy: false,
    selected: null,
    pick: null,
  };
}

export function currentView(state: Pick<ChatState, "views" | "current">): View | undefined {
  return state.views.find((view) => view.id === state.current);
}
