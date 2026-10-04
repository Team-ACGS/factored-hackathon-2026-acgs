import { describe, expect, it } from "vitest";

import {
  askOf,
  emptyConversation,
  liveTurn,
  openAsk,
  reduce,
  saysOf,
  sourcesOf,
  thinkingLeft,
  turnLeft,
  THINKING_CAP_MS,
  visibleMessages,
  type Action,
  type Conversation,
  type ServerMessage,
  type StatusEvent,
  viewOf,
} from "./conversation";

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

describe("clara's parts", () => {
  const citation = { chunk_id: "pe-dispute-lifecycle#3", title: "Ciclo de una aclaración", page: 4, url: "https://docs.test/pe.pdf#page=4" };

  it("renders each say with its sources and skips parts it does not know", () => {
    const parts = [
      { type: "say", text: "Tu aclaración está en revisión.", facts: ["f6"], citations: [] },
      { type: "view", view: "movements", items: [{ product_id: "p1", transaction_id: "t1" }] },
      { type: "say", text: "La revisión toma hasta diez días.", facts: ["p1"], citations: [citation] },
    ];
    const [message] = visibleMessages(run({ type: "loaded", roomId: room, messages: [server("m-002", { sender_type: "assistant", parts })] }));

    expect(message?.says).toEqual([
      { text: "Tu aclaración está en revisión.", citations: [] },
      {
        text: "La revisión toma hasta diez días.",
        citations: [{ chunkId: citation.chunk_id, title: citation.title, page: 4, url: citation.url }],
      },
    ]);
  });

  it("never links a source outside https", () => {
    const parts = [{ type: "say", text: "Hola.", citations: [{ ...citation, url: "javascript:alert(1)" }] }];

    expect(saysOf({ text: "Hola.", parts })[0]?.citations[0]?.url).toBeNull();
  });

  it("renders a message without parts from its text, one paragraph per block", () => {
    expect(saysOf({ text: "Hola.\n\n¿En qué te ayudo?" })).toEqual([
      { text: "Hola.", citations: [] },
      { text: "¿En qué te ayudo?", citations: [] },
    ]);
  });
});

describe("clara thinking", () => {
  const sent = Date.parse("2026-09-27T20:00:00.001Z");
  const asked = () => visibleMessages(run({ type: "loaded", roomId: room, messages: [server("m-001")] }));

  it("lasts from the customer's message until a reply, at most thirty seconds", () => {
    expect(thinkingLeft(asked(), sent + 10_000)).toBe(20_000);
    expect(thinkingLeft(asked(), sent + THINKING_CAP_MS)).toBe(0);
  });

  it("starts the full window when the local clock is behind the message", () => {
    expect(thinkingLeft(asked(), sent - 5_000)).toBe(THINKING_CAP_MS);
  });

  it("stops when Clara answers or the message failed", () => {
    const answered = run({ type: "loaded", roomId: room, messages: [server("m-001"), server("m-002", { sender_type: "assistant" })] });
    const failed = run(sending("m-003"), { type: "failed", messageId: "m-003" });

    expect(thinkingLeft(visibleMessages(answered), sent)).toBe(0);
    expect(thinkingLeft(visibleMessages(failed), sent)).toBe(0);
  });
});

describe("clara's views and asks", () => {
  it("reads the rows, cards and cases of a view with the readings Clara rendered", () => {
    const movements = viewOf({
      parts: [
        { type: "view", view: "movements", items: [{ product_id: "p1", transaction_id: "t1" }], readings: { count: "32 movimientos", odd: 3 } },
      ],
    });
    const cards = viewOf({ parts: [{ type: "view", view: "cards", items: [{ product_id: "p1" }, { product_id: "p2" }] }] });
    const cases = viewOf({ parts: [{ type: "view", view: "case", items: [{ complaint_id: "c1" }] }] });

    expect(movements).toEqual({
      kind: "movements",
      rows: [{ productId: "p1", transactionId: "t1" }],
      cards: [],
      cases: [],
      readings: { count: "32 movimientos" },
    });
    expect(cards?.cards).toEqual(["p1", "p2"]);
    expect(cases?.cases).toEqual(["c1"]);
    expect(viewOf({ parts: [{ type: "view", view: "ledger", items: [] }] })).toBeNull();
  });

  it("puts the bank's alert first among the reasons of a charge", () => {
    const charge = viewOf({
      parts: [
        {
          type: "view",
          view: "charge",
          items: [{ product_id: "p1", transaction_id: "t1" }],
          readings: {
            reasons: [
              { reason: "new_merchant", text: "es tu primera compra en este comercio" },
              { reason: "score_high", text: "el sistema de alertas del banco emitió una alerta" },
            ],
          },
        },
      ],
    });

    expect(charge?.readings.reasons?.map(({ reason }) => reason)).toEqual(["score_high", "new_merchant"]);
  });

  it("reads an ask's options and ignores asks it does not know", () => {
    const parts = [
      { type: "ask", ask: "block_card", options: [{ id: "p1", label: "Bloquear" }] },
      { type: "ask", ask: "which_one", prompt: "¿Cuál es?", options: [{ id: "t1", label: "Primax · S/ 120.00" }, { id: 4 }] },
    ];

    expect(askOf({ parts })).toEqual({ kind: "which_one", prompt: "¿Cuál es?", options: [{ id: "t1", label: "Primax · S/ 120.00" }] });
  });

  it("keeps the ask open only while it is Clara's latest message", () => {
    const ask = { type: "ask", ask: "show", options: [{ id: "movements", label: "Ver esos movimientos" }] };
    const asked = run({ type: "loaded", roomId: room, messages: [server("m-001"), server("m-002", { sender_type: "assistant", parts: [ask] })] });
    const tapped = reduce(asked, sending("m-003"));

    expect(openAsk(visibleMessages(asked))?.messageId).toBe("m-002");
    expect(openAsk(visibleMessages(tapped))).toBeNull();
  });

  it("dedupes the sources of an answer by document and page", () => {
    const source = { chunkId: "a", title: "Ciclo de una aclaración", page: 4, url: "https://docs.test/a.pdf#page=4" };
    const says = [
      { text: "Uno.", citations: [source, { ...source, chunkId: "b" }] },
      { text: "Dos.", citations: [{ ...source, chunkId: "c", page: 5 }] },
    ];

    expect(sourcesOf(says).map((citation) => citation.chunkId)).toEqual(["a", "c"]);
  });
});

describe("clara's status", () => {
  const at = Date.parse("2026-09-27T20:00:05.000Z");
  const event = (round: number, status: string, id = "m-001"): StatusEvent => ({
    type: "status",
    room_id: room,
    message_id: id,
    round,
    status,
  });
  const asked = () => run({ type: "loaded", roomId: room, messages: [server("m-001")] });
  const statusOf = (state: Conversation, now = at) => liveTurn(state, now)?.status ?? null;

  it("shows the latest round's status while the turn runs", () => {
    const state = [event(1, "movements"), event(2, "policies"), event(1, "cards")].reduce(
      (current, item) => reduce(current, { type: "status", event: item, at }),
      asked(),
    );

    expect(statusOf(state)).toBe("policies");
  });

  it("drops a status that arrives after the reply or for another message", () => {
    const answered = reduce(asked(), { type: "received", message: server("m-002", { sender_type: "assistant" }) });

    expect(statusOf(reduce(answered, { type: "status", event: event(1, "movements"), at }))).toBeNull();
    expect(statusOf(reduce(asked(), { type: "status", event: event(1, "movements", "m-000"), at }))).toBeNull();
  });

  it("gives up on a turn when no newer status or reply arrives within thirty seconds", () => {
    const state = reduce(asked(), { type: "status", event: event(1, "movements"), at });

    expect(turnLeft(state, at + 10_000)).toBe(20_000);
    expect(statusOf(state, at + THINKING_CAP_MS)).toBeNull();
    expect(turnLeft(state, at + THINKING_CAP_MS)).toBe(0);
  });

  it("shows the status of a turn already running when the chat reloads, until the reply", () => {
    const reloaded = run({
      type: "loaded",
      roomId: room,
      messages: [server("m-001")],
      turn: { messageId: "m-001", round: 0, status: "cases", at },
    });
    const answered = reduce(reloaded, { type: "received", message: server("m-002", { sender_type: "assistant" }) });

    expect([statusOf(reloaded), turnLeft(reloaded, at) > 0]).toEqual(["cases", true]);
    expect([statusOf(answered), turnLeft(answered, at)]).toEqual([null, 0]);
  });
});

describe("a tap", () => {
  it("keeps its ask and option on the pending message, also after it fails, so a retry sends them again", () => {
    const input = { ask_id: "m-002", option: "t1" };
    const state = run({ ...(sending("m-003") as Extract<Action, { type: "sending" }>), input }, { type: "failed", messageId: "m-003" });

    expect(visibleMessages(state)[0]).toMatchObject({ delivery: "failed", input });
  });
});
