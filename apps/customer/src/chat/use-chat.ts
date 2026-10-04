import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { retryDelay, watchReturn } from "./catch-up";
import { emptyConversation, reduce, visibleMessages, type ChatInput, type ChatMessage } from "./conversation";
import { idTime, mintId } from "./clock";
import { subscribeToRooms } from "./realtime";
import { api, clock } from "./services";

const SAME_ID_RETRY_WINDOW_MS = 90_000;

export type ChatProblem = "load" | null;

export function useChat(customerId: string) {
  const [state, dispatch] = useReducer(reduce, emptyConversation);
  const [problem, setProblem] = useState<ChatProblem>(null);
  const [attempt, setAttempt] = useState(0);
  const [reconnecting, setReconnecting] = useState(false);

  const failures = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reconnect = useCallback(() => {
    if (retryTimer.current !== null) clearTimeout(retryTimer.current);
    retryTimer.current = null;
    setReconnecting(true);
    setAttempt((count) => count + 1);
  }, []);

  const retryLater = useCallback(() => {
    if (retryTimer.current !== null) return;
    setReconnecting(true);
    retryTimer.current = setTimeout(reconnect, retryDelay(failures.current));
    failures.current += 1;
  }, [reconnect]);

  useEffect(() => watchReturn(document, window, reconnect), [reconnect]);

  useEffect(
    () => () => {
      if (retryTimer.current !== null) clearTimeout(retryTimer.current);
    },
    [],
  );

  useEffect(() => {
    let active = true;
    let unsubscribe: () => void = () => {};

    async function open() {
      try {
        unsubscribe = await subscribeToRooms(customerId, {
          onMessage: (message) => dispatch({ type: "received", message }),
          onStatus: (event) => dispatch({ type: "status", event, at: clock.now() }),
          onError: () => active && retryLater(),
        });
        if (!active) return unsubscribe();
        const requestedAt = Date.now();
        const latest = await api.latestRoom();
        clock.sync(latest.server_time, requestedAt, Date.now());
        const turn = latest.turn
          ? { messageId: latest.turn.message_id, round: 0, status: latest.turn.status, at: clock.now() }
          : null;
        if (!active) return;
        dispatch({ type: "loaded", roomId: latest.room?.room_id ?? null, messages: latest.messages, turn });
        failures.current = 0;
        setProblem(null);
        setReconnecting(false);
      } catch {
        if (!active) return;
        setProblem("load");
        setReconnecting(false);
      }
    }

    void open();
    return () => {
      active = false;
      unsubscribe();
    };
  }, [customerId, attempt, retryLater]);

  const deliver = useCallback(async (roomId: string, messageId: string, text: string, input?: ChatInput) => {
    dispatch({ type: "sending", roomId, messageId, text, sentAt: new Date(idTime(messageId)).toISOString(), input });
    try {
      const message = await api.send({ room_id: roomId, message_id: messageId, text, ...(input ? { input } : {}) });
      dispatch({ type: "confirmed", message });
    } catch {
      dispatch({ type: "failed", messageId });
    }
  }, []);

  const send = useCallback(
    (text: string, input?: ChatInput) => {
      const roomId = state.roomId ?? mintId(clock);
      return deliver(roomId, mintId(clock), text, input);
    },
    [deliver, state.roomId],
  );

  const retry = useCallback(
    (message: ChatMessage) => {
      if (clock.now() - idTime(message.messageId) < SAME_ID_RETRY_WINDOW_MS) {
        return deliver(message.roomId, message.messageId, message.text, message.input);
      }
      dispatch({ type: "discarded", messageId: message.messageId });
      return deliver(message.roomId, mintId(clock), message.text, message.input);
    },
    [deliver],
  );

  return {
    loaded: state.loaded,
    state,
    messages: visibleMessages(state),
    problem,
    reconnecting,
    send,
    retry,
    reload: () => {
      setProblem(null);
      setAttempt((count) => count + 1);
    },
  };
}
