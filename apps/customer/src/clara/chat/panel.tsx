import { ClaraEntity } from "@clara/ui/components/clara-entity";
import type { EntityState } from "@clara/ui/lib/entity";
import { ChevronDown } from "lucide-react";
import { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";

import { brand } from "../../bank/brand";
import type { AskOption, ChatMessage } from "../../chat/conversation";
import type { LiveChat } from "../../chat/live";
import { useI18n } from "../../i18n";
import { useViewMeta } from "./meta";
import { entityMode, type PanelMode, type PanelView } from "./panel-state";
import { useStatusText } from "./status";
import { PanelView as ViewBody, type Navigation } from "./views";

interface PanelProps {
  chat: LiveChat;
  shown: PanelView | null;
  mode: PanelMode;
  face: EntityState;
  asked: ChatMessage | null;
  nav: Navigation;
  sheet: "open" | "closed";
  onCloseSheet: () => void;
}

const LEAVE_MS = 200;

function useLeaving(target: PanelView | null): { shown: PanelView | null; leaving: boolean } {
  const [previous, setPrevious] = useState(target);
  const [leaving, setLeaving] = useState<PanelView | null>(null);
  if ((previous?.id ?? null) !== (target?.id ?? null)) {
    setPrevious(target);
    if (!leaving && previous && target) setLeaving(previous);
  }
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => setLeaving(null), LEAVE_MS);
    return () => clearTimeout(timer);
  }, [leaving]);
  return leaving ? { shown: leaving, leaving: true } : { shown: target, leaving: false };
}

function useLastAsk(asked: ChatMessage | null): ChatMessage | null {
  const [last, setLast] = useState(asked);
  if (asked && asked.messageId !== last?.messageId) setLast(asked);
  return asked ?? last;
}

export function ChatPanel({ chat, shown: target, mode, face, asked, nav, sheet, onCloseSheet }: PanelProps) {
  const { t } = useI18n();
  const { shown, leaving } = useLeaving(target);
  const bar = useLastAsk(asked);
  const body = useRef<HTMLDivElement>(null);
  const docked = mode !== "hero" || shown !== null || asked !== null;

  useLayoutEffect(() => {
    if (body.current) body.current.scrollTop = 0;
  }, [shown?.id]);

  return (
    <aside
      className="chat-panel"
      aria-label={t("clara.chat.panel")}
      data-docked={docked || undefined}
      data-bar={asked ? true : undefined}
      data-sheet={sheet}
    >
      <div className="chat-entity" data-mode={entityMode(mode)}>
        <ClaraEntity
          state={face}
          mode={entityMode(mode)}
          motion={mode === "searching" ? "thinking" : undefined}
          label={t("clara.name")}
        />
      </div>
      <button
        type="button"
        onClick={onCloseSheet}
        aria-label={t("clara.chat.hidePanel")}
        className="absolute top-3.5 right-3.5 z-[5] grid size-[34px] place-items-center rounded-full bg-[rgb(23_36_34/0.06)] hover:bg-[rgb(23_36_34/0.12)] min-[901px]:hidden"
      >
        <ChevronDown className="size-[18px]" aria-hidden />
      </button>
      <div className="chat-head">
        {mode === "searching" ? (
          <Searching status={chat.status} />
        ) : (
          shown && (
            <Suspense fallback={null}>
              <Head view={shown} />
            </Suspense>
          )
        )}
      </div>
      {!docked && (
        <div className="chat-hero">
          <h2 className="font-serif text-[clamp(24px,3vw,30px)] leading-[1.15] font-medium">{t("clara.hello")}</h2>
          <p className="max-w-[44ch] text-ink-2">{t("clara.chat.heroText", { bank: brand.name })}</p>
        </div>
      )}
      <div ref={body} className="chat-body" data-leaving={leaving || undefined}>
        {shown && (
          <Suspense fallback={null}>
            <ViewBody key={shown.id} spec={shown.spec} nav={nav} />
          </Suspense>
        )}
      </div>
      {bar?.ask && (
        <ActionBar
          prompt={bar.ask.prompt}
          options={bar.ask.options}
          gone={!asked}
          onChoose={(option) => chat.choose(bar, option)}
        />
      )}
    </aside>
  );
}

function Searching({ status }: { status: string | null }) {
  const text = useStatusText(status);
  return (
    <span className="flex items-center gap-2 text-sm text-ink-2" role="status">
      <span className="chat-shimmer">{text}</span>
    </span>
  );
}

function Head({ view }: { view: PanelView }) {
  const meta = useViewMeta(view.spec);
  return (
    <>
      <span className="text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase">{meta.kicker}</span>
      <span className="truncate text-[19px] font-semibold">{meta.title}</span>
    </>
  );
}

const optionClass =
  "chat-option inline-flex h-11 max-w-full items-center gap-2.5 rounded-full border border-[rgb(23_36_34/0.12)] bg-white/80 px-4 text-[14.5px] font-semibold transition-[border-color,background,box-shadow] duration-150 hover:border-[rgb(23_36_34/0.25)] hover:bg-white focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none";

interface ActionBarProps {
  prompt: string | null;
  options: readonly AskOption[];
  gone: boolean;
  onChoose: (option: AskOption) => void;
}

function ActionBar({ prompt, options, gone, onChoose }: ActionBarProps) {
  const { t } = useI18n();
  return (
    <div
      className="chat-bar"
      role="group"
      aria-label={t("clara.chat.actions")}
      aria-hidden={gone || undefined}
      data-gone={gone || undefined}
      inert={gone}
    >
      {prompt && <span className="text-[13.5px] font-semibold text-ink-2">{prompt}</span>}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {options.map((option) => (
          <button key={option.id} type="button" className={optionClass} onClick={() => onChoose(option)}>
            <span className="truncate">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
