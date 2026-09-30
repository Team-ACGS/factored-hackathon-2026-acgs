import type { ChatState, HintKey, Reference, View } from "./state";

export type ReferenceState = { state: "current"; hint: HintKey | null } | { state: "past"; view: View };

export function referenceOf(ref: Reference, chat: Pick<ChatState, "views" | "current" | "ask">): ReferenceState | null {
  const view = chat.views.find((item) => item.id === ref.viewId);
  if (!view) return null;
  if (chat.current !== ref.viewId) return { state: "past", view };
  const asking = chat.ask?.viewId === ref.viewId && ref.hint !== undefined;
  return { state: "current", hint: asking && ref.hint ? ref.hint : null };
}
