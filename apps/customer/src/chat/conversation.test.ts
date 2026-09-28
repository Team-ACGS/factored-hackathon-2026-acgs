import { describe, expect, it } from "vitest";

import { emptyConversation, reduce, visibleMessages, type Action, type Conversation, type ServerMessage } from "./conversation";

const room = "0199a0b0-0000-7000-8000-000000000001";

function server(id: string, overrides: Partial<ServerMessage> = {}): ServerMessage {
  return {
    room_id: room,
    message_id: id,
    sender_type: "customer",
    text: `text of ${id}`,
    sent_at: `2026-09-27T20:00:00.${id.slice(-3)}Z`,
    created_at: "2026-09-27T20:00:01.000Z",
    ...overrides,
  };
}

function run(...actions: Action[]): Conversation {
  return actions.reduce(reduce, emptyConversation);
}

function sending(id: string): Action {
  return { type: "sending", roomId: room, messageId: id, text: `text of ${id}`, sentAt: server(id).sent_at };
}

describe("conversation", () => {
  it("shows a sent message as pending until the API confirms it", () => {
    const pending = run(sending("m-001"));
    const confirmed = reduce(pending, { type: "confirmed", message: server("m-001") });

    expect(visibleMessages(pending).map((message) => message.delivery)).toEqual(["pending"]);
    expect(visibleMessages(confirmed).map((message) => message.delivery)).toEqual(["sent"]);
  });

  it("marks a pending message sent when its push arrives before the API answers", () => {
    const state = run(sending("m-001"), { type: "received", message: server("m-001") }, { type: "failed", messageId: "m-001" });

    expect(visibleMessages(state).map((message) => message.delivery)).toEqual(["sent"]);
  });

  it("keeps one copy of a message delivered by history, push and confirmation", () => {
    const state = run(
      { type: "received", message: server("m-002") },
      { type: "loaded", roomId: room, messages: [server("m-001"), server("m-002")] },
      sending("m-003"),
      { type: "received", message: server("m-003") },
      { type: "confirmed", message: server("m-003") },
    );

    expect(visibleMessages(state).map((message) => message.messageId)).toEqual(["m-001", "m-002", "m-003"]);
  });

  it("keeps pushes that arrive before the history and orders everything by time", () => {
    const echo = server("m-001", { message_id: "m-001-echo", sender_type: "assistant" });
    const state = run(
      { type: "received", message: echo },
      { type: "loaded", roomId: room, messages: [server("m-001")] },
    );

    expect(visibleMessages(state).map((message) => message.messageId)).toEqual(["m-001", "m-001-echo"]);
  });

  it("shows only the open room", () => {
    const state = run(
      { type: "received", message: server("m-009", { room_id: "another-room" }) },
      { type: "loaded", roomId: room, messages: [server("m-001")] },
    );

    expect(visibleMessages(state).map((message) => message.messageId)).toEqual(["m-001"]);
  });

  it("opens the room of the first message when the customer has none", () => {
    const state = run({ type: "loaded", roomId: null, messages: [] }, sending("m-001"));

    expect(state.roomId).toBe(room);
    expect(visibleMessages(state)).toHaveLength(1);
  });

  it("drops a discarded message", () => {
    const state = run(sending("m-001"), { type: "failed", messageId: "m-001" }, { type: "discarded", messageId: "m-001" });

    expect(state.messages).toEqual({});
  });
});
