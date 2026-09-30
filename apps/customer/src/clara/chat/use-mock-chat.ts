import { useEffect, useMemo, useSyncExternalStore } from "react";

import { useI18n } from "../../i18n";
import { resetClaraDemo } from "../services";
import { claraSession } from "../store";
import { topicInput, topicMessage } from "../topics";
import type { ClaraChat } from "./contract";
import { claraChat } from "./services";

const noop = () => undefined;

export function useMockChat(_customerId: string): ClaraChat {
  const { locale, t } = useI18n();
  const state = useSyncExternalStore(claraChat.subscribe, claraChat.current);

  useEffect(() => {
    claraChat.start();
    const topic = claraSession.takeTopic();
    if (topic) claraChat.input(topicInput(topic), topicMessage(topic, t, locale));
  }, [t, locale]);

  return useMemo(
    () => ({
      state,
      notice: null,
      send: claraChat.send,
      select: claraChat.select,
      confirm: claraChat.confirm,
      pick: claraChat.pick,
      cancelPick: claraChat.cancelPick,
      confirmPick: claraChat.confirmPick,
      navigate: claraChat.navigate,
      restore: claraChat.restore,
      retry: noop,
      reload: noop,
      reset: () => {
        resetClaraDemo();
        claraChat.start();
      },
    }),
    [state],
  );
}
