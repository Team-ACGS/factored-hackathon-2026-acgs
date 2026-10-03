import { useEffect, useState } from "react";

import { claraSession } from "../clara/store";
import { topicMessage } from "../clara/topics";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";
import { thinkingLeft, type AskOption, type ChatMessage } from "./conversation";
import { clock } from "./services";
import { useChat } from "./use-chat";

const MAX_TEXT_LENGTH = 2000;

export interface LiveChat {
  loaded: boolean;
  messages: ChatMessage[];
  thinking: boolean;
  status: string | null;
  notice: MessageKey | null;
  send: (text: string) => void;
  choose: (asked: ChatMessage, option: AskOption) => void;
  retry: (messageId: string) => void;
  reload: () => void;
}

export function useLiveChat(customerId: string): LiveChat {
  const { locale, t } = useI18n();
  const { loaded, send, messages, status, inTurn, problem, retry, reload } = useChat(customerId);
  const [now, setNow] = useState(() => clock.now());
  const left = thinkingLeft(messages, now);

  useEffect(() => {
    if (!loaded) return;
    const topic = claraSession.takeTopic();
    if (topic) void send(topicMessage(topic, t, locale).slice(0, MAX_TEXT_LENGTH));
  }, [loaded, send, t, locale]);

  useEffect(() => {
    if (left <= 0) return;
    const timer = setTimeout(() => setNow(clock.now()), left);
    return () => clearTimeout(timer);
  }, [left]);

  return {
    loaded,
    messages,
    thinking: loaded && (left > 0 || inTurn),
    status,
    notice: problem === "load" ? "chat.loadFailed" : problem === "live" ? "chat.liveUpdatesLost" : null,
    send: (text) => void send(text.slice(0, MAX_TEXT_LENGTH)),
    choose: (asked, option) => void send(option.label.slice(0, MAX_TEXT_LENGTH), { ask_id: asked.messageId, option: option.id }),
    retry: (messageId) => {
      const message = messages.find((item) => item.messageId === messageId);
      if (message) void retry(message);
    },
    reload,
  };
}
