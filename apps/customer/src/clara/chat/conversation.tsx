import { ClaraGlyph } from "@clara/ui/components/clara-entity";
import { AlertCircle, ArrowUpRight } from "lucide-react";
import { useEffect, useRef } from "react";

import { useI18n } from "../../i18n";
import type { ClaraChat } from "./contract";
import { agent } from "./engine";
import type { Context } from "./insight";
import { viewMeta } from "./meta";
import { referenceOf } from "./references";
import type { Entry } from "./state";
import { revealed } from "./text";

interface ConversationProps {
  chat: ClaraChat;
  ctx: Context;
  onReference: () => void;
}

export function Conversation({ chat, ctx, onReference }: ConversationProps) {
  const { t } = useI18n();
  const { state } = chat;
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [state.entries, state.thinking, state.humanTyping]);

  return (
    <div ref={scroller} className="min-h-0 flex-1 scroll-smooth overflow-y-auto px-5 pt-4 pb-6">
      <div className="mx-auto flex max-w-[680px] flex-col gap-[18px]" aria-live="polite">
        {chat.notice && (
          <p role="status" className="flex flex-wrap items-center justify-center gap-2 text-center text-sm text-ink-3">
            {t(chat.notice)}
            <button type="button" className="font-semibold text-ink underline underline-offset-[3px]" onClick={chat.reload}>
              {t("chat.reload")}
            </button>
          </p>
        )}
        {state.entries.map((entry) => (
          <EntryRow key={entry.id} entry={entry} chat={chat} ctx={ctx} onReference={onReference} />
        ))}
        {state.thinking && (
          <div className="chat-rise flex items-center gap-3 text-[14.5px]">
            <span className="chat-spin-glyph relative mt-0.5">
              <ClaraGlyph />
            </span>
            <span className="chat-shimmer">{state.thinking}</span>
            <Dots />
          </div>
        )}
        {state.humanTyping && (
          <div className="chat-rise flex items-center gap-3 text-[14.5px]">
            <Avatar />
            <span className="chat-shimmer">{t("clara.chat.agent.typing", { name: agent.name })}</span>
            <Dots />
          </div>
        )}
      </div>
    </div>
  );
}

function Dots() {
  return (
    <span className="chat-dots inline-flex gap-1" aria-hidden>
      <i />
      <i />
      <i />
    </span>
  );
}

function Avatar() {
  return (
    <span className="mt-0.5 grid size-[26px] flex-none place-items-center rounded-full bg-info-soft text-[10.5px] font-bold text-info" aria-hidden>
      {agent.initials}
    </span>
  );
}

function EntryRow({ entry, chat, ctx, onReference }: { entry: Entry; chat: ClaraChat; ctx: Context; onReference: () => void }) {
  const { t } = useI18n();
  switch (entry.kind) {
    case "me":
      return (
        <div className="chat-me flex flex-col items-end gap-1">
          <p className="max-w-[80%] rounded-[20px_20px_6px_20px] border border-line bg-surface px-4 py-2.5 whitespace-pre-wrap [overflow-wrap:anywhere]">
            {entry.text}
          </p>
          {entry.failed && (
            <span className="flex items-center gap-1 text-xs text-danger">
              <AlertCircle className="size-3" aria-hidden />
              {t("chat.failed")}
              <button type="button" className="font-semibold underline underline-offset-2" onClick={() => chat.retry(entry.id)}>
                {t("chat.retry")}
              </button>
            </span>
          )}
        </div>
      );
    case "system":
      return (
        <div className="chat-msg flex w-full items-center gap-2.5 text-[12.5px] text-ink-3 before:h-px before:flex-1 before:bg-line after:h-px after:flex-1 after:bg-line">
          {entry.text}
        </div>
      );
    case "human":
      return (
        <div className="chat-msg grid grid-cols-[26px_minmax(0,1fr)] gap-3">
          <Avatar />
          <div>
            <small className="mb-0.5 block text-xs text-ink-3">
              {agent.name} · {t("clara.chat.agent.team")}
            </small>
            <p className="text-[15.5px]">{entry.text}</p>
          </div>
        </div>
      );
    case "clara": {
      const streaming = entry.shown < entry.words;
      const ref = entry.ref && !streaming ? referenceOf(entry.ref, chat.state) : null;
      return (
        <div className="chat-msg grid grid-cols-[26px_minmax(0,1fr)] items-start gap-3">
          <span className="mt-0.5">
            <ClaraGlyph />
          </span>
          <div>
            <p className="font-serif text-[17px] leading-[1.55]">
              {revealed(entry.segments, entry.shown).map((segment, index) =>
                segment.strong ? (
                  <b key={index} className="chat-strong">
                    {segment.text}
                  </b>
                ) : (
                  <span key={index}>{segment.text}</span>
                ),
              )}
              {streaming && <span className="chat-caret" aria-hidden />}
            </p>
            {ref?.state === "current" && (
              <span className="mt-2.5 flex h-[30px] w-fit items-center gap-1.5 text-[13px] font-medium text-ink-2">
                <i className="chat-ref-dot size-2 flex-none rounded-full bg-[#4c8fe6]" aria-hidden />
                {t(ref.hint ?? "clara.chat.hint.current")}
              </span>
            )}
            {ref?.state === "past" && (
              <button
                type="button"
                className="mt-2.5 flex h-[30px] w-fit items-center gap-1.5 rounded-full border border-[#d6e4f7] bg-[#edf4fd] pr-3 pl-2.5 text-[13px] font-semibold text-[#2f67b5] transition-colors hover:bg-[#dfeafb]"
                onClick={() => {
                  chat.restore(ref.view.id);
                  onReference();
                }}
              >
                <ArrowUpRight className="size-[15px]" aria-hidden />
                {viewMeta(ref.view.spec, ctx, t).label}
              </button>
            )}
          </div>
        </div>
      );
    }
  }
}
