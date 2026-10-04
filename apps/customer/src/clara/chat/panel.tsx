import { ClaraEntity } from "@clara/ui/components/clara-entity";
import type { EntityState, WorkingLook } from "@clara/ui/lib/entity";
import { ChevronDown, Search, Waves } from "lucide-react";
import { Suspense, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import { brand } from "../../bank/brand";
import type { ChatMessage } from "../../chat/conversation";
import type { LiveChat } from "../../chat/live";
import { useI18n } from "../../i18n";
import { ActionBar } from "./action-bar";
import { useViewMeta } from "./meta";
import { entityMode, type PanelMode, type PanelView } from "./panel-state";
import { useStatusText } from "./status";
import { PanelView as ViewBody, type Navigation } from "./views";

interface PanelProps {
  chat: LiveChat;
  shown: PanelView | null;
  mode: PanelMode;
  face: EntityState;
  look: WorkingLook | undefined;
  earlier: boolean;
  asked: ChatMessage | null;
  nav: Navigation;
  sheet: "open" | "closed";
  onCloseSheet: () => void;
  onCancelPick: () => void;
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

export function ChatPanel(props: PanelProps) {
  const { chat, shown: target, mode, face, look, earlier, asked, nav, sheet, onCloseSheet, onCancelPick } = props;
  const { t } = useI18n();
  const { shown, leaving } = useLeaving(target);
  const bar = useLastAsk(asked);
  const body = useRef<HTMLDivElement>(null);
  const [workWidth, setWorkWidth] = useState(0);
  const [barHeight, setBarHeight] = useState(0);
  const docked = mode !== "hero" || shown !== null;
  const working = mode === "working";

  useLayoutEffect(() => {
    if (body.current) body.current.scrollTop = 0;
  }, [shown?.id]);

  return (
    <aside
      className="chat-panel"
      aria-label={t("clara.chat.panel")}
      data-docked={docked || undefined}
      data-working={working || undefined}
      data-bar={asked ? true : undefined}
      data-sheet={sheet}
      style={{ "--work-text": `${workWidth}px`, "--bar-height": `${barHeight}px` } as CSSProperties}
    >
      <div className="chat-entity" data-mode={entityMode(mode)}>
        <ClaraEntity
          state={face}
          mode={entityMode(mode)}
          motion={working ? "thinking" : undefined}
          look={look}
          label={t("clara.name")}
        />
      </div>
      {working && <WorkStatus status={chat.status} listening={face === "escucha"} onWidth={setWorkWidth} />}
      <button
        type="button"
        onClick={onCloseSheet}
        aria-label={t("clara.chat.hidePanel")}
        className="absolute top-3.5 right-3.5 z-[5] grid size-[34px] place-items-center rounded-full bg-[rgb(23_36_34/0.06)] hover:bg-[rgb(23_36_34/0.12)] min-[901px]:hidden"
      >
        <ChevronDown className="size-[18px]" aria-hidden />
      </button>
      <div className="chat-head" aria-hidden={working || undefined}>
        {shown && (
          <Suspense fallback={null}>
            <Head view={shown} earlier={earlier} />
          </Suspense>
        )}
      </div>
      {!docked && (
        <div className="chat-hero">
          <h2 className="font-serif text-[clamp(24px,3vw,30px)] leading-[1.15] font-medium">{t("clara.hello")}</h2>
          <p className="max-w-[44ch] text-ink-2">{t("clara.chat.heroText", { bank: brand.name })}</p>
        </div>
      )}
      <div
        ref={body}
        className="chat-body"
        data-leaving={leaving || undefined}
        aria-hidden={working || undefined}
        inert={working}
      >
        {shown && (
          <Suspense fallback={null}>
            <ViewBody key={shown.id} spec={shown.spec} nav={nav} />
          </Suspense>
        )}
      </div>
      {bar?.ask && (
        <ActionBar
          key={bar.messageId}
          ask={bar.ask}
          gone={!asked}
          inView={Boolean(asked && nav.pick)}
          card={shown?.spec.kind === "cards"}
          picked={bar.ask.options.find((option) => option.id === nav.pick?.selected) ?? null}
          onCancelPick={onCancelPick}
          onChoose={(option, note) => chat.choose(bar, option, note)}
          onHeight={setBarHeight}
        />
      )}
    </aside>
  );
}

interface WorkStatusProps {
  status: string | null;
  listening: boolean;
  onWidth: (width: number) => void;
}

function WorkStatus({ status, listening, onWidth }: WorkStatusProps) {
  const text = useStatusText(status);
  const element = useRef<HTMLDivElement>(null);
  const Badge = listening ? Waves : Search;

  useLayoutEffect(() => {
    const target = element.current;
    if (!target) return;
    const observer = new ResizeObserver(() => onWidth(target.offsetWidth));
    observer.observe(target);
    return () => observer.disconnect();
  }, [onWidth]);

  return (
    <div ref={element} className="chat-work" role="status">
      <span className="chat-work-badge" aria-hidden>
        <Badge className="size-[15px]" strokeWidth={2.4} />
      </span>
      <span className="chat-shimmer text-[15px] leading-snug">{text}</span>
    </div>
  );
}

function Head({ view, earlier }: { view: PanelView; earlier: boolean }) {
  const { t } = useI18n();
  const meta = useViewMeta(view.spec);
  return (
    <>
      <span className="truncate text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase">
        {meta.kicker}
        {earlier && (
          <span className="font-normal tracking-normal normal-case"> · {t("clara.chat.earlier")}</span>
        )}
      </span>
      <span className="line-clamp-2 text-[17px] leading-tight font-semibold sm:text-[19px]">{meta.title}</span>
    </>
  );
}
