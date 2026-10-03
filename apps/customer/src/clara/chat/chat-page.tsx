import { ClaraEntity } from "@clara/ui/components/clara-entity";
import { ArrowUp, ChevronUp } from "lucide-react";
import { Suspense, useReducer, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { brand } from "../../bank/brand";
import { openAsk } from "../../chat/conversation";
import { useLiveChat, type LiveChat } from "../../chat/live";
import { useI18n } from "../../i18n";
import { Conversation } from "./conversation";
import { useViewMeta } from "./meta";
import { ChatPanel } from "./panel";
import {
  faceOf,
  initialPanel,
  panelMode,
  panelViews,
  reducePanel,
  shownView,
  type PanelView,
} from "./panel-state";
import { useStatusText } from "./status";

const MAX_TEXT = 600;

export function ClaraChatPage({ customerId }: { customerId: string }) {
  return <ChatScreen chat={useLiveChat(customerId)} />;
}

export function ChatScreen({ chat }: { chat: LiveChat }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [panel, dispatch] = useReducer(reducePanel, initialPanel);
  const [sheet, setSheet] = useState<"open" | "closed">("closed");
  const input = useRef<HTMLTextAreaElement>(null);
  const views = panelViews(chat.messages);
  const latest = views.at(-1)?.id ?? null;
  const asked = chat.thinking ? null : openAsk(chat.messages);

  const [seenAsk, setSeenAsk] = useState<string | null>(null);

  if (panel.following !== latest) {
    dispatch({ type: "follow", id: latest });
    if (latest !== null && chat.loaded) setSheet("open");
  }
  if (asked && asked.messageId !== seenAsk) {
    setSeenAsk(asked.messageId);
    setSheet("open");
  }

  const shown = shownView(panel, views);
  const mode = panelMode(shown, chat.thinking, asked !== null);
  const typing = draft.trim() !== "";
  const face = faceOf(mode, typing, asked !== null);

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

  const nav = {
    open: (spec: PanelView["spec"]) => dispatch({ type: "open", spec }),
    back: panel.trail.length > 0 ? () => dispatch({ type: "back" }) : null,
    disabled: chat.thinking,
  };

  return (
    <div className="chat-app">
      <section className="flex min-h-0 flex-col" aria-label={t("clara.chat.label")}>
        <Conversation
          chat={chat}
          typing={typing}
          views={views}
          current={panel.selected}
          onReference={(id) => {
            dispatch({ type: "restore", id });
            setSheet("open");
          }}
        />
        <div className="flex-none px-4 pb-[calc(16px+env(safe-area-inset-bottom))] sm:px-5">
          <div className="mx-auto grid max-w-[680px] gap-2.5">
            {(shown || chat.thinking || asked) && (
              <button
                type="button"
                className="chat-peek grid-cols-[40px_minmax(0,1fr)_18px] items-center gap-3 rounded-[20px] border border-line bg-surface px-3 py-2 text-left shadow-bank"
                onClick={() => setSheet("open")}
                aria-label={t("clara.chat.showPanel")}
              >
                <ClaraEntity state={face} motion={chat.thinking ? "thinking" : undefined} className="size-10" />
                <Peek shown={shown} thinking={chat.thinking} status={chat.status} asking={asked !== null} />
                <ChevronUp className="size-[18px] text-ink-3" aria-hidden />
              </button>
            )}
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
      <div
        className="chat-scrim fixed inset-0 z-[55] bg-[rgb(14_24_21/0.18)]"
        data-sheet={sheet}
        onClick={() => setSheet("closed")}
      />
      <ChatPanel
        chat={chat}
        shown={shown}
        mode={mode}
        face={face}
        asked={asked}
        nav={nav}
        sheet={sheet}
        onCloseSheet={() => setSheet("closed")}
      />
    </div>
  );
}

function Peek({
  shown,
  thinking,
  status,
  asking,
}: {
  shown: PanelView | null;
  thinking: boolean;
  status: string | null;
  asking: boolean;
}) {
  const { t } = useI18n();
  const text = useStatusText(status);
  if (thinking) return <span className="chat-shimmer truncate text-sm">{text}</span>;
  if (asking) return <span className="truncate text-sm font-semibold">{t("clara.chat.peek.answer")}</span>;
  return shown ? (
    <Suspense fallback={<span />}>
      <PeekTitle view={shown} />
    </Suspense>
  ) : (
    <span className="truncate text-sm font-semibold">{t("clara.chat.showPanel")}</span>
  );
}

function PeekTitle({ view }: { view: PanelView }) {
  const meta = useViewMeta(view.spec);
  return <span className="truncate text-sm font-semibold">{meta.title || meta.kicker}</span>;
}
