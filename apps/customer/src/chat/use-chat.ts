import { useCallback, useEffect, useReducer, useState } from "react";

import { emptyConversation, reduce, visibleMessages, type ChatMessage } from "./conversation";
import { idTime, mintId } from "./clock";
import { subscribeToRooms } from "./realtime";
import { api, clock } from "./services";

const SAME_ID_RETRY_WINDOW_MS = 90_000;

export type ChatProblem = "load" | "live" | null;

export function useChat(customerId: string) {
  const [state, dispatch] = useReducer(reduce, emptyConversation);
  const [problem, setProblem] = useState<ChatProblem>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    let unsubscribe: () => void = () => {};

    async function open() {
      try {
        unsubscribe = await subscribeToRooms(
          customerId,
          (message) => dispatch({ type: "received", message }),
          () => active && setProblem("live"),
        );
        if (!active) return unsubscribe();
        const requestedAt = Date.now();
        const latest = await api.latestRoom();
        clock.sync(latest.server_time, requestedAt, Date.now());
        if (active) dispatch({ type: "loaded", roomId: latest.room?.room_id ?? null, messages: latest.messages });
      } catch {
        if (active) setProblem("load");
      }
    }

    void open();
    return () => {
      active = false;
      unsubscribe();
    };
  }, [customerId, attempt]);

  const deliver = useCallback(async (roomId: string, messageId: string, text: string) => {
    dispatch({ type: "sending", roomId, messageId, text, sentAt: new Date(idTime(messageId)).toISOString() });
    try {
      const message = await api.send({ room_id: roomId, message_id: messageId, text });
      dispatch({ type: "confirmed", message });
    } catch {
      dispatch({ type: "failed", messageId });
    }
  }, []);

  const send = useCallback(
    (text: string) => {
      const roomId = state.roomId ?? mintId(clock);
      return deliver(roomId, mintId(clock), text);
    },
    [deliver, state.roomId],
  );

  const retry = useCallback(
    (message: ChatMessage) => {
      if (clock.now() - idTime(message.messageId) < SAME_ID_RETRY_WINDOW_MS) {
        return deliver(message.roomId, message.messageId, message.text);
      }
      dispatch({ type: "discarded", messageId: message.messageId });
      return deliver(message.roomId, mintId(clock), message.text);
    },
    [deliver],
  );

  return {
    loaded: state.loaded,
    messages: visibleMessages(state),
    problem,
    send,
    retry,
    reload: () => {
      setProblem(null);
      setAttempt((count) => count + 1);
    },
  };
}
