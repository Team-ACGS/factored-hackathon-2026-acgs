import { useEffect, useMemo, useState } from "react";

import { resetClaraDemo } from "../clara/services";
import type { ClaraChat } from "../clara/chat/contract";
import { initialChat, type BarChoice, type Entry } from "../clara/chat/state";
import { claraSession } from "../clara/store";
import { topicMessage } from "../clara/topics";
import { useI18n } from "../i18n";
import type { ChatMessage } from "./conversation";
import { useChat } from "./use-chat";

const MAX_TEXT_LENGTH = 2000;
const noop = () => undefined;

function entryOf(message: ChatMessage): Entry {
  const id = message.messageId;
  if (message.senderType === "customer") return { id, kind: "me", text: message.text, failed: message.delivery === "failed" };
  if (message.senderType === "agent") return { id, kind: "human", text: message.text };
  const words = message.text.match(/\S+/g)?.length ?? 0;
  return { id, kind: "clara", segments: [{ text: message.text }], words, shown: words };
}

export function useLiveChat(customerId: string): ClaraChat {
  const { locale, t } = useI18n();
  const chat = useChat(customerId);
  const [selected, setSelected] = useState<string | null>(null);
  const { loaded, send, messages, problem, retry, reload } = chat;

  useEffect(() => {
    if (!loaded) return;
    const topic = claraSession.takeTopic();
    if (topic) void send(topicMessage(topic, t, locale).slice(0, MAX_TEXT_LENGTH));
  }, [loaded, send, t, locale]);

  return useMemo(
    () => ({
      state: { ...initialChat, entries: messages.map(entryOf), selected, busy: !loaded },
      notice: problem === "load" ? "chat.loadFailed" : problem === "live" ? "chat.liveUpdatesLost" : null,
      send: (text: string) => void send(text.slice(0, MAX_TEXT_LENGTH)),
      select: setSelected,
      confirm: (choice: BarChoice) => {
        if (selected !== choice.id) return;
        setSelected(null);
        void send(choice.echo);
      },
      pick: noop,
      cancelPick: noop,
      confirmPick: noop,
      navigate: noop,
      restore: noop,
      retry: (entryId: string) => {
        const message = messages.find((item) => item.messageId === entryId);
        if (message) void retry(message);
      },
      reload,
      reset: resetClaraDemo,
    }),
    [messages, selected, loaded, problem, send, retry, reload],
  );
}
