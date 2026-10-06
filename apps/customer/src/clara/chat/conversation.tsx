import { ClaraEntity, ClaraGlyph } from "@clara/ui/components/clara-entity";
import { cn } from "@clara/ui/lib/cn";
import { AlertCircle, ArrowUpRight, ChevronDown, FileText, Loader2, UserRound } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";

import { brand } from "../../bank/brand";
import { sourcesOf, type ChatMessage, type Citation } from "../../chat/conversation";
import type { LiveChat } from "../../chat/live";
import { useI18n } from "../../i18n";
import { useViewMeta } from "./meta";
import type { PanelView } from "./panel-state";
import { useStatusText } from "./status";

interface ConversationProps {
  chat: LiveChat;
  typing: boolean;
  views: readonly PanelView[];
  current: string | null;
  onReference: (id: string) => void;
}

export function Conversation({ chat, typing, views, current, onReference }: ConversationProps) {
  const { t } = useI18n();
  const scroller = useRef<HTMLDivElement>(null);
  const empty = chat.loaded && chat.messages.length === 0;
  const status = useStatusText(chat.status);

  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [chat.messages, chat.thinking, chat.status]);

  return (
    <div ref={scroller} className="min-h-0 flex-1 scroll-smooth overflow-y-auto px-4 pt-6 pb-6 sm:px-5">
      <div className="mx-auto flex min-h-full max-w-[680px] flex-col gap-[18px]" aria-live="polite">
        {chat.notice && (
          <p role="status" className="flex flex-wrap items-center justify-center gap-2 text-center text-sm text-ink-3">
            {t(chat.notice)}
            <button type="button" className="font-semibold text-ink underline underline-offset-[3px]" onClick={chat.reload}>
              {t("chat.reload")}
            </button>
          </p>
        )}
        {!chat.loaded && !chat.notice && (
          <div className="grid flex-1 place-items-center">
            <Loader2 className="size-6 animate-spin text-ink-3" aria-hidden />
          </div>
        )}
        {empty && (
          <div className="chat-rise grid flex-1 content-center justify-items-center gap-4 pb-10 text-center min-[901px]:hidden">
            <ClaraEntity state={typing ? "escucha" : "hola"} motion="idle" className="size-[112px]" />
            <p className="max-w-[360px] font-serif text-[19px] leading-[1.45] text-balance">
              {t("clara.chat.heroText", { bank: brand.name })}
            </p>
          </div>
        )}
        {chat.messages.map((message) => (
          <MessageRow
            key={message.messageId}
            message={message}
            view={views.find((view) => view.id === message.messageId) ?? null}
            current={current === message.messageId}
            onRetry={() => chat.retry(message.messageId)}
            onReference={() => onReference(message.messageId)}
          />
        ))}
        {chat.thinking && (
          <div className="chat-rise flex items-center gap-3 text-[14.5px]" role="status">
            <span className="chat-spin-glyph relative grid size-[26px] flex-none place-items-center">
              <ClaraGlyph />
            </span>
            <span key={status} className="chat-shimmer chat-rise">
              {status}
            </span>
            <span className="chat-dots inline-flex gap-1" aria-hidden>
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

interface MessageRowProps {
  message: ChatMessage;
  view: PanelView | null;
  current: boolean;
  onRetry: () => void;
  onReference: () => void;
}

function MessageRow({ message, view, current, onRetry, onReference }: MessageRowProps) {
  const { t } = useI18n();
  switch (message.senderType) {
    case "customer":
      return (
        <div className="chat-me flex flex-col items-end gap-1">
          <p className="max-w-[80%] rounded-[20px_20px_6px_20px] border border-line bg-surface px-4 py-2.5 whitespace-pre-wrap [overflow-wrap:anywhere]">
            {message.text}
          </p>
          {message.delivery === "failed" && (
            <span className="flex items-center gap-1 text-xs text-danger">
              <AlertCircle className="size-3" aria-hidden />
              {t("chat.failed")}
              <button type="button" className="font-semibold underline underline-offset-2" onClick={onRetry}>
                {t("chat.retry")}
              </button>
            </span>
          )}
        </div>
      );
    case "agent":
      return (
        <div className="chat-msg grid grid-cols-[26px_minmax(0,1fr)] gap-3">
          <span className="mt-0.5 grid size-[26px] place-items-center rounded-full bg-info-soft text-info" aria-hidden>
            <UserRound className="size-[15px]" />
          </span>
          <div>
            <small className="mb-0.5 block text-xs text-ink-3">{t("clara.chat.agent.team")}</small>
            <p className="text-[15.5px] whitespace-pre-wrap">{message.text}</p>
          </div>
        </div>
      );
    case "assistant": {
      const sources = sourcesOf(message.says);
      return (
        <div className="chat-msg grid grid-cols-[26px_minmax(0,1fr)] items-start gap-3">
          <ClaraGlyph />
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] justify-items-start gap-3">
            {message.says.map((say, index) => (
              <p key={index} className="font-serif text-[17px] leading-[1.55] whitespace-pre-wrap [overflow-wrap:anywhere]">
                {say.text}
              </p>
            ))}
            {view && (
              <Suspense fallback={null}>
                <Reference view={view} current={current} asking={message.ask !== null} onOpen={onReference} />
              </Suspense>
            )}
            {sources.length > 0 && <HowIKnow sources={sources} />}
          </div>
        </div>
      );
    }
  }
}

function Reference({ view, current, asking, onOpen }: { view: PanelView; current: boolean; asking: boolean; onOpen: () => void }) {
  const { t } = useI18n();
  const meta = useViewMeta(view.spec);
  const button = (
    <button
      type="button"
      className={cn(
        "flex h-[30px] w-fit items-center gap-1.5 rounded-full border border-[#d6e4f7] bg-[#edf4fd] pr-3 pl-2.5 text-[13px] font-semibold text-[#2f67b5] transition-colors hover:bg-[#dfeafb]",
        current && "min-[901px]:hidden",
      )}
      onClick={onOpen}
    >
      <ArrowUpRight className="size-[15px]" aria-hidden />
      {meta.label}
    </button>
  );
  if (!current) return button;
  return (
    <>
      {button}
      <span className="flex h-[30px] w-fit items-center gap-1.5 text-[13px] font-medium text-ink-2 max-[900px]:hidden">
        <i className="chat-ref-dot size-2 flex-none rounded-full bg-[#4c8fe6]" aria-hidden />
        {t(asking ? "clara.chat.hint.answer" : "clara.chat.hint.current")}
      </span>
    </>
  );
}

function HowIKnow({ sources }: { sources: readonly Citation[] }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <div className="grid justify-items-start gap-2">
      <button
        type="button"
        aria-expanded={open}
        className="flex h-[30px] items-center gap-1 text-[13px] font-semibold text-ink-2 hover:text-ink"
        onClick={() => setOpen((shown) => !shown)}
      >
        {t("clara.chat.howIKnow")}
        <ChevronDown className={cn("size-4 transition-transform duration-200", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="chat-rise flex flex-wrap gap-2">
          {sources.map((citation) => (
            <SourceChip key={citation.chunkId} citation={citation} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceChip({ citation }: { citation: Citation }) {
  const { t } = useI18n();
  const body = (
    <>
      <FileText className="size-[15px] flex-none text-[#2f67b5]" aria-hidden />
      <span className="truncate">{citation.title}</span>
      {citation.page !== null && (
        <span className="flex-none font-normal text-ink-3">{t("clara.chat.source.page", { page: String(citation.page) })}</span>
      )}
    </>
  );
  const chip =
    "inline-flex h-[30px] max-w-full items-center gap-1.5 rounded-full border border-line bg-surface pr-3 pl-2.5 text-[13px] font-semibold text-ink-2";
  if (!citation.url) return <span className={chip}>{body}</span>;
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={t("clara.chat.source.open", { title: citation.title })}
      className={`${chip} transition-colors hover:border-[#c9d4e3] hover:bg-[#edf4fd] hover:text-[#2f67b5] focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none`}
    >
      {body}
    </a>
  );
}
