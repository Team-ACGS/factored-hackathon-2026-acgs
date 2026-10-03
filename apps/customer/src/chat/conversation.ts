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

export interface ChatMessage {
  roomId: string;
  messageId: string;
  senderType: SenderType;
  text: string;
  says: Say[];
  sentAt: string;
  createdAt: string | null;
  delivery: Delivery;
}

export interface Conversation {
  loaded: boolean;
  roomId: string | null;
  messages: Readonly<Record<string, ChatMessage>>;
}

export type Action =
  | { type: "loaded"; roomId: string | null; messages: ServerMessage[] }
  | { type: "received"; message: ServerMessage }
  | { type: "sending"; roomId: string; messageId: string; text: string; sentAt: string }
  | { type: "confirmed"; message: ServerMessage }
  | { type: "failed"; messageId: string }
  | { type: "discarded"; messageId: string };

export const emptyConversation: Conversation = { loaded: false, roomId: null, messages: {} };

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
      };
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

export function visibleMessages(state: Conversation): ChatMessage[] {
  return Object.values(state.messages)
    .filter((message) => message.roomId === state.roomId)
    .sort((a, b) => a.sentAt.localeCompare(b.sentAt) || a.messageId.localeCompare(b.messageId));
}
