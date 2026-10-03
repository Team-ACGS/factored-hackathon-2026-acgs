import { ArrowUp } from "lucide-react";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { brand } from "../../bank/brand";
import { useLiveChat, type LiveChat } from "../../chat/live";
import { useI18n } from "../../i18n";
import { Conversation } from "./conversation";

const MAX_TEXT = 600;

export function ClaraChatPage({ customerId }: { customerId: string }) {
  return <ChatScreen chat={useLiveChat(customerId)} />;
}

export function ChatScreen({ chat }: { chat: LiveChat }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const typing = draft.trim() !== "";

  function resize() {
    const element = input.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 140)}px`;
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || !chat.loaded) return;
    setDraft("");
    chat.send(text);
    requestAnimationFrame(resize);
  }

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label={t("clara.chat.label")}>
      <Conversation chat={chat} typing={typing} />
      <div className="flex-none px-4 pb-[calc(16px+env(safe-area-inset-bottom))] sm:px-5">
        <div className="mx-auto grid max-w-[680px] gap-2.5">
          <form
            onSubmit={submit}
            className="flex items-end gap-2.5 rounded-3xl border border-line bg-surface py-3 pr-3 pl-[18px] shadow-clara transition-colors duration-200 focus-within:border-[#c9d4e3]"
          >
            <textarea
              ref={input}
              rows={1}
              value={draft}
              maxLength={MAX_TEXT}
              placeholder={t("clara.ask")}
              aria-label={t("clara.ask")}
              onChange={(event) => {
                setDraft(event.target.value);
                resize();
              }}
              onKeyDown={onKey}
              className="max-h-[140px] min-w-0 flex-1 resize-none bg-transparent py-1.5 text-[15.5px] leading-normal outline-none"
            />
            <button
              type="submit"
              aria-label={t("clara.send")}
              disabled={!typing || !chat.loaded}
              className="grid size-[38px] flex-none place-items-center rounded-xl bg-ink text-white disabled:cursor-default disabled:bg-muted disabled:text-ink-3"
            >
              <ArrowUp className="size-[18px]" aria-hidden />
            </button>
          </form>
          <p className="text-center text-xs text-ink-3">{t("clara.chat.fine", { bank: brand.name })}</p>
        </div>
      </div>
    </section>
  );
}
