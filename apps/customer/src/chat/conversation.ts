export type SenderType = "customer" | "assistant" | "agent";
export type Delivery = "pending" | "sent" | "failed";

export const THINKING_CAP_MS = 30_000;

export interface ServerMessage {
  room_id: string;
  message_id: string;
  sender_type: SenderType;
  text: string;
  sent_at: string;
  created_at: string;
  parts?: unknown;
}

export interface Citation {
  chunkId: string;
  title: string;
  page: number | null;
  url: string | null;
}

export interface Say {
  text: string;
  citations: Citation[];
}

export const viewKinds = ["movements", "cards", "card", "movement", "charge", "history", "case"] as const;
export type ViewKind = (typeof viewKinds)[number];

export interface Row {
  productId: string;
  transactionId: string;
}

export interface Reason {
  reason: string;
  text: string;
}

export interface Readings {
  count?: string;
  period?: string;
  last4?: string;
  merchant?: string;
  typical_amount?: string;
  explanation?: string;
  habit?: string;
  compared?: string;
  reasons?: Reason[];
}

export interface ViewPart {
  kind: ViewKind;
  rows: Row[];
  cards: string[];
  cases: string[];
  readings: Readings;
}

export interface AskOption {
  id: string;
  label: string;
}

export interface AskPart {
  kind: "which_one" | "show";
  prompt: string | null;
  options: AskOption[];
}

export interface ChatMessage {
  roomId: string;
  messageId: string;
  senderType: SenderType;
  text: string;
  says: Say[];
  view: ViewPart | null;
  ask: AskPart | null;
  sentAt: string;
  createdAt: string | null;
  delivery: Delivery;
}

export interface TurnStatus {
  messageId: string;
  round: number;
  status: string | null;
}

export interface Conversation {
  loaded: boolean;
  roomId: string | null;
  messages: Readonly<Record<string, ChatMessage>>;
  turn: TurnStatus | null;
}

export interface StatusEvent {
  type: "status";
  room_id: string;
  message_id: string;
  round: number;
  status: string;
}

export type Action =
  | { type: "loaded"; roomId: string | null; messages: ServerMessage[]; turn?: TurnStatus | null }
  | { type: "received"; message: ServerMessage }
  | { type: "status"; event: StatusEvent }
  | { type: "sending"; roomId: string; messageId: string; text: string; sentAt: string }
  | { type: "confirmed"; message: ServerMessage }
  | { type: "failed"; messageId: string }
  | { type: "discarded"; messageId: string };

export const emptyConversation: Conversation = { loaded: false, roomId: null, messages: {}, turn: null };

const senderTypes: readonly string[] = ["customer", "assistant", "agent"];

export function isServerMessage(value: unknown): value is ServerMessage {
  if (typeof value !== "object" || value === null) return false;
  const fields = value as Record<string, unknown>;
  return (
    ["room_id", "message_id", "text", "sent_at", "created_at"].every((name) => typeof fields[name] === "string") &&
    typeof fields.sender_type === "string" &&
    senderTypes.includes(fields.sender_type)
  );
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function citationOf(value: unknown): Citation | null {
  const fields = record(value);
  if (!fields || typeof fields.chunk_id !== "string" || typeof fields.title !== "string") return null;
  return {
    chunkId: fields.chunk_id,
    title: fields.title,
    page: typeof fields.page === "number" ? fields.page : null,
    url: typeof fields.url === "string" && fields.url.startsWith("https://") ? fields.url : null,
  };
}

export function saysOf(message: Pick<ServerMessage, "text" | "parts">): Say[] {
  if (!Array.isArray(message.parts)) {
    return message.text
      .split(/\n{2,}/)
      .filter((text) => text.trim() !== "")
      .map((text) => ({ text, citations: [] }));
  }
  return message.parts.flatMap((part): Say[] => {
    const fields = record(part);
    if (!fields || fields.type !== "say" || typeof fields.text !== "string") return [];
    const citations = Array.isArray(fields.citations) ? fields.citations.map(citationOf) : [];
    return [{ text: fields.text, citations: citations.filter((citation) => citation !== null) }];
  });
}

export function isStatusEvent(value: unknown): value is StatusEvent {
  const fields = record(value);
  return (
    fields !== null &&
    fields.type === "status" &&
    typeof fields.room_id === "string" &&
    typeof fields.message_id === "string" &&
    typeof fields.round === "number" &&
    typeof fields.status === "string"
  );
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
}

function readingsOf(value: unknown): Readings {
  const fields = record(value) ?? {};
  const readings: Readings = {};
  for (const name of ["count", "period", "last4", "merchant", "typical_amount", "explanation", "habit", "compared"] as const) {
    const text = fields[name];
    if (typeof text === "string") readings[name] = text;
  }
  if (Array.isArray(fields.reasons)) {
    readings.reasons = fields.reasons.flatMap((entry): Reason[] => {
      const reason = record(entry);
      return reason && typeof reason.reason === "string" && typeof reason.text === "string"
        ? [{ reason: reason.reason, text: reason.text }]
        : [];
    });
  }
  return readings;
}

export function viewOf(message: Pick<ServerMessage, "parts">): ViewPart | null {
  if (!Array.isArray(message.parts)) return null;
  for (const part of message.parts) {
    const fields = record(part);
    const kind = fields?.view;
    if (!fields || fields.type !== "view" || typeof kind !== "string" || !viewKinds.includes(kind as ViewKind)) continue;
    const items = Array.isArray(fields.items) ? fields.items.map(record).filter((item) => item !== null) : [];
    const rows = items.flatMap((item): Row[] =>
      typeof item.product_id === "string" && typeof item.transaction_id === "string"
        ? [{ productId: item.product_id, transactionId: item.transaction_id }]
        : [],
    );
    const cards = items.flatMap((item) =>
      typeof item.product_id === "string" && item.transaction_id === undefined ? [item.product_id] : [],
    );
    const cases = strings(items.map((item) => item.complaint_id));
    return { kind: kind as ViewKind, rows, cards, cases, readings: readingsOf(fields.readings) };
  }
  return null;
}

export function askOf(message: Pick<ServerMessage, "parts">): AskPart | null {
  if (!Array.isArray(message.parts)) return null;
  for (const part of message.parts) {
    const fields = record(part);
    if (!fields || fields.type !== "ask" || (fields.ask !== "which_one" && fields.ask !== "show")) continue;
    const options = (Array.isArray(fields.options) ? fields.options : []).flatMap((entry): AskOption[] => {
      const option = record(entry);
      return option && typeof option.id === "string" && typeof option.label === "string"
        ? [{ id: option.id, label: option.label }]
        : [];
    });
    if (options.length === 0) continue;
    return { kind: fields.ask, prompt: typeof fields.prompt === "string" ? fields.prompt : null, options };
  }
  return null;
}

export function sourcesOf(says: readonly Say[]): Citation[] {
  const seen = new Map<string, Citation>();
  for (const citation of says.flatMap((say) => say.citations)) {
    const key = `${citation.title}#${citation.page ?? ""}`;
    if (!seen.has(key)) seen.set(key, citation);
  }
  return [...seen.values()];
}

export function thinkingLeft(messages: readonly ChatMessage[], now: number): number {
  const last = messages.at(-1);
  if (!last || last.senderType !== "customer" || last.delivery === "failed") return 0;
  const sent = Date.parse(last.sentAt);
  return Math.max(0, sent + THINKING_CAP_MS - Math.max(now, sent));
}

function fromServer(message: ServerMessage): ChatMessage {
  return {
    roomId: message.room_id,
    messageId: message.message_id,
    senderType: message.sender_type,
    text: message.text,
    says: saysOf(message),
    view: viewOf(message),
    ask: askOf(message),
    sentAt: message.sent_at,
    createdAt: message.created_at,
    delivery: "sent",
  };
}

function withMessages(state: Conversation, messages: ChatMessage[]): Conversation {
  const next = { ...state.messages };
  for (const message of messages) {
    next[message.messageId] = message;
  }
  return { ...state, messages: next };
}

export function reduce(state: Conversation, action: Action): Conversation {
  switch (action.type) {
    case "loaded":
      return {
        ...withMessages(state, action.messages.map(fromServer)),
        loaded: true,
        roomId: state.roomId ?? action.roomId,
        turn: state.turn ?? action.turn ?? null,
      };
    case "status": {
      const { event } = action;
      const last = visibleMessages(state).at(-1);
      if (last?.messageId !== event.message_id || last.senderType !== "customer") return state;
      if (state.turn?.messageId === event.message_id && state.turn.round > event.round) return state;
      return { ...state, turn: { messageId: event.message_id, round: event.round, status: event.status } };
    }
    case "received":
    case "confirmed":
      return withMessages(state, [fromServer(action.message)]);
    case "sending":
      return {
        ...withMessages(state, [
          {
            roomId: action.roomId,
            messageId: action.messageId,
            senderType: "customer",
            text: action.text,
            says: [],
            view: null,
            ask: null,
            sentAt: action.sentAt,
            createdAt: null,
            delivery: "pending",
          },
        ]),
        roomId: state.roomId ?? action.roomId,
      };
    case "failed": {
      const message = state.messages[action.messageId];
      if (!message || message.delivery === "sent") return state;
      return withMessages(state, [{ ...message, delivery: "failed" }]);
    }
    case "discarded": {
      const { [action.messageId]: _discarded, ...messages } = state.messages;
      return { ...state, messages };
    }
  }
}

export function currentStatus(state: Conversation): string | null {
  const last = visibleMessages(state).at(-1);
  return last && state.turn?.messageId === last.messageId && last.senderType === "customer" ? state.turn.status : null;
}

export function turnInProgress(state: Conversation): boolean {
  const last = visibleMessages(state).at(-1);
  return last !== undefined && last.senderType === "customer" && state.turn?.messageId === last.messageId;
}

export function openAsk(messages: readonly ChatMessage[]): ChatMessage | null {
  const last = messages.at(-1);
  return last?.senderType === "assistant" && last.ask ? last : null;
}

export function visibleMessages(state: Conversation): ChatMessage[] {
  return Object.values(state.messages)
    .filter((message) => message.roomId === state.roomId)
    .sort((a, b) => a.sentAt.localeCompare(b.sentAt) || a.messageId.localeCompare(b.messageId));
}
