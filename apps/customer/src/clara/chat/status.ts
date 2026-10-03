import { useI18n } from "../../i18n";
import type { MessageKey } from "../../i18n/en";

const statusKeys: Record<string, MessageKey> = {
  cards: "clara.chat.status.cards",
  movements: "clara.chat.status.movements",
  cases: "clara.chat.status.cases",
  memory: "clara.chat.status.memory",
  policies: "clara.chat.status.policies",
};

export function statusKey(status: string | null): MessageKey {
  return (status && statusKeys[status]) || "clara.chat.thinking";
}

export function useStatusText(status: string | null): string {
  const { t } = useI18n();
  return t(statusKey(status));
}
