import { useEffect, useState } from "react";

import { claraSession } from "../clara/store";
import { topicInput, topicMessage } from "../clara/topics";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";
import { choice, liveTurn, MAX_TEXT_LENGTH, thinkingLeft, turnLeft, type AskOption, type ChatMessage } from "./conversation";
import { clock } from "./services";
import { useChat } from "./use-chat";


export interface LiveChat {
  loaded: boolean;
  messages: ChatMessage[];
  thinking: boolean;
  status: string | null;
  statusAt: number | null;
  notice: MessageKey | null;
  reconnecting: boolean;
  send: (text: string) => void;
  choose: (asked: ChatMessage, option: AskOption, note?: string) => void;
  retry: (messageId: string) => void;
  reload: () => void;
}

export function useLiveChat(customerId: string): LiveChat {
  const { locale, t } = useI18n();
  const { loaded, send, state, messages, problem, reconnecting, retry, reload } = useChat(customerId);
  const [tick, setNow] = useState(() => clock.now());
  const now = Math.max(tick, state.turn?.at ?? 0);
  const left = Math.max(thinkingLeft(messages, now), turnLeft(state, now));

  useEffect(() => {
    if (!loaded) return;
    const topic = claraSession.takeTopic();
    if (topic) void send(topicMessage(topic, t, locale).slice(0, MAX_TEXT_LENGTH), topicInput(topic));
  }, [loaded, send, t, locale]);

  useEffect(() => {
    if (left <= 0) return;
    const timer = setTimeout(() => setNow(clock.now()), left);
    return () => clearTimeout(timer);
  }, [left]);

  return {
    loaded,
    messages,
    thinking: loaded && left > 0,
    status: liveTurn(state, now)?.status ?? null,
    statusAt: liveTurn(state, now)?.at ?? null,
    notice: problem === "load" ? "chat.loadFailed" : null,
    reconnecting: reconnecting && loaded,
    send: (text) => void send(text.slice(0, MAX_TEXT_LENGTH)),
    choose: (asked, option, note) => void send(...choice(asked, option, note)),
    retry: (messageId) => {
      const message = messages.find((item) => item.messageId === messageId);
      if (message) void retry(message);
    },
    reload,
  };
}
