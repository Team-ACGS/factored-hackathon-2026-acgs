export type SenderType = "customer" | "assistant" | "agent";
export type Delivery = "pending" | "sent" | "failed";

export interface ServerMessage {
  room_id: string;
  message_id: string;
  sender_type: SenderType;
  text: string;
  sent_at: string;
  created_at: string;
}

export interface ChatMessage {
  roomId: string;
  messageId: string;
  senderType: SenderType;
  text: string;
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

function fromServer(message: ServerMessage): ChatMessage {
  return {
    roomId: message.room_id,
    messageId: message.message_id,
    senderType: message.sender_type,
    text: message.text,
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
