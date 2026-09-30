import { ClaraEntity } from "@clara/ui/components/clara-entity";
import type { EntityMode, EntityState } from "@clara/ui/lib/entity";
import { cn } from "@clara/ui/lib/cn";
import { ChevronDown, Clock, CreditCard, HelpCircle, Store } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { brand } from "../../bank/brand";
import { useI18n } from "../../i18n";
import type { Bar, BarIcon } from "./bar";
import type { ClaraChat } from "./contract";
import { agent } from "./engine";
import type { Context } from "./insight";
import { viewMeta } from "./meta";
import { box } from "./parts";
import { currentView, type ChatState, type Skeleton, type View } from "./state";
import { PanelView } from "./views";

interface PanelProps {
  chat: ClaraChat;
  ctx: Context;
  bar: Bar | null;
  face: EntityState;
  sheet: "open" | "closed";
  onCloseSheet: () => void;
}

function entityModeOf(mode: ClaraChat["state"]["panel"]["mode"]): EntityMode {
  if (mode === "searching") return "dot";
  if (mode === "docked") return "dock";
  return "hero";
}

type Content = { kind: "view"; view: View } | { kind: "skeleton"; skeleton: Skeleton } | null;

const LEAVE_MS = 200;

function contentOf(state: ChatState): Content {
  const panel = state.panel;
  if (panel.mode === "searching" && panel.skeleton) return { kind: "skeleton", skeleton: panel.skeleton };
  const view = currentView(state);
  return view && (panel.mode === "docked" || panel.mode === "searching") ? { kind: "view", view } : null;
}

function contentKey(content: Content): string {
  if (!content) return "none";
  return content.kind === "view" ? `view:${content.view.id}` : `skeleton:${content.skeleton}`;
}

function useLeaving(target: Content): { shown: Content; leaving: boolean } {
  const [previous, setPrevious] = useState(target);
  const [leaving, setLeaving] = useState<Content>(null);
  if (contentKey(previous) !== contentKey(target)) {
    setPrevious(target);
    if (!leaving && previous?.kind === "view" && target) setLeaving(previous);
  }
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => setLeaving(null), LEAVE_MS);
    return () => clearTimeout(timer);
  }, [leaving]);
  return leaving ? { shown: leaving, leaving: true } : { shown: target, leaving: false };
}

function useLastBar(bar: Bar | null): Bar | null {
  const [last, setLast] = useState(bar);
  if (bar && (!last || barKey(bar) !== barKey(last))) setLast(bar);
  return bar ?? last;
}

export function ChatPanel({ chat, ctx, bar, face, sheet, onCloseSheet }: PanelProps) {
  const { t } = useI18n();
  const { state } = chat;
  const panel = state.panel;
  const { shown, leaving } = useLeaving(contentOf(state));
  const shownBar = useLastBar(bar);
  const body = useRef<HTMLDivElement>(null);
  const shownKey = contentKey(shown);
  const view = shown?.kind === "view" ? shown.view : currentView(state);
  const meta = view ? viewMeta(view.spec, ctx, t) : null;
  const docked = panel.mode === "docked" || panel.mode === "searching";

  useLayoutEffect(() => {
    if (body.current) body.current.scrollTop = 0;
  }, [shownKey]);

  return (
    <aside
      className="chat-panel"
      aria-label={t("clara.chat.panel")}
      data-docked={docked || undefined}
      data-bar={bar ? true : undefined}
      data-sheet={sheet}
    >
      <div className="chat-entity" data-mode={entityModeOf(panel.mode)}>
        <ClaraEntity
          state={face}
          mode={entityModeOf(panel.mode)}
          motion={state.thinking ? "thinking" : undefined}
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
        {panel.mode === "searching" ? (
          <span className="flex items-center gap-2 text-sm text-ink-2" role="status">
            <span className="chat-shimmer">{panel.status}</span>
          </span>
        ) : (
          meta && (
            <>
              <span className="text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase">{meta.kicker}</span>
              <span className="truncate text-[19px] font-semibold">{meta.title}</span>
            </>
          )
        )}
      </div>
      {!docked && (
        <div className="chat-hero">
          {panel.mode === "calling" ? (
            <>
              <h2 className="font-serif text-[clamp(24px,3vw,30px)] leading-[1.15] font-medium">
                {t("clara.chat.calling", { name: agent.name })}
              </h2>
              <p className="max-w-[44ch] text-ink-2">{t("clara.chat.callingText", { bank: brand.name })}</p>
            </>
          ) : (
            <>
              <h2 className="font-serif text-[clamp(24px,3vw,30px)] leading-[1.15] font-medium">{t("clara.hello")}</h2>
              <p className="max-w-[44ch] text-ink-2">{t("clara.chat.heroText", { bank: brand.name })}</p>
            </>
          )}
        </div>
      )}
      <div ref={body} className="chat-body" data-leaving={leaving || undefined}>
        {shown?.kind === "skeleton" && <SkeletonView kind={shown.skeleton} />}
        {shown?.kind === "view" && <PanelView key={shown.view.id} view={shown.view} chat={chat} ctx={ctx} />}
      </div>
      {shownBar && <ActionBar bar={shownBar} gone={!bar} chat={chat} />}
    </aside>
  );
}

function barKey(bar: Bar): string {
  return bar.kind === "pick" ? `pick:${bar.pick.target}` : `${bar.prompt}:${bar.options.map((option) => option.id).join()}`;
}

const icons: Record<BarIcon, typeof Store> = { store: Store, card: CreditCard, clock: Clock, question: HelpCircle };

const optionClass =
  "chat-option inline-flex h-11 items-center gap-2.5 rounded-full border border-[rgb(23_36_34/0.12)] bg-white/80 px-4 text-[14.5px] font-semibold transition-[border-color,background,box-shadow] duration-150 hover:border-[rgb(23_36_34/0.25)] hover:bg-white aria-pressed:border-ink aria-pressed:bg-white aria-pressed:shadow-[0_0_0_1px_var(--color-ink)]";

const confirmClass =
  "chat-confirm h-[46px] w-full rounded-full bg-ink px-6 text-[14.5px] font-semibold text-white transition-opacity duration-200 disabled:cursor-default disabled:opacity-30 sm:w-auto sm:min-w-[240px]";

function ActionBar({ bar, gone, chat }: { bar: Bar; gone: boolean; chat: ClaraChat }) {
  const { t } = useI18n();
  const frame = {
    className: "chat-bar",
    role: "group",
    "aria-label": t("clara.chat.actions"),
    "aria-hidden": gone || undefined,
    "data-gone": gone || undefined,
    inert: gone,
  };
  if (bar.kind === "pick") {
    return (
      <div {...frame}>
        <span className="text-[13.5px] font-semibold text-ink-2">{bar.pick.prompt}</span>
        <span className="-mt-1.5 text-base font-semibold">{bar.pick.label}</span>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <button type="button" className={optionClass} onClick={chat.cancelPick}>
            {t("clara.chat.cancel")}
          </button>
          <button type="button" className={confirmClass} onClick={chat.confirmPick}>
            {bar.pick.cta}
          </button>
        </div>
      </div>
    );
  }
  const selected = bar.options.find((option) => option.id === chat.state.selected);
  return (
    <div {...frame}>
      <span className="text-[13.5px] font-semibold text-ink-2">{bar.prompt}</span>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {bar.options.map((option) => {
          const Icon = option.icon ? icons[option.icon] : null;
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={option.id === chat.state.selected}
              className={optionClass}
              onClick={() => chat.select(option.id)}
            >
              {Icon && (
                <span className="-ml-2 grid size-7 place-items-center rounded-full bg-[#edf4fd] text-[#2f67b5]" aria-hidden>
                  <Icon className="size-4" />
                </span>
              )}
              {option.label}
            </button>
          );
        })}
      </div>
      <button
        key={selected?.id ?? "none"}
        type="button"
        className={confirmClass}
        disabled={!selected}
        onClick={() => selected && chat.confirm(selected)}
      >
        {selected ? t("clara.chat.confirm", { choice: selected.label }) : t("clara.chat.choose")}
      </button>
    </div>
  );
}

function Bone({ className }: { className: string }) {
  return <span className={cn("chat-skeleton", className)} />;
}

function SkeletonView({ kind }: { kind: Skeleton }) {
  const rows = (count: number) => Array.from({ length: count }, (_, index) => index);
  return (
    <div className="chat-skeletons mx-auto grid max-w-[620px] gap-4" aria-hidden>
      {kind === "list" && (
        <>
          <div className="flex gap-2">
            <Bone className="h-8 w-[190px] rounded-full" />
            <Bone className="h-8 w-[150px] rounded-full" />
          </div>
          <div className={cn(box, "overflow-hidden")}>
            {rows(5).map((row) => (
              <div key={row} className="grid grid-cols-[40px_minmax(0,1fr)_70px] items-center gap-3.5 px-[18px] py-4 [&+&]:border-t [&+&]:border-line">
                <Bone className="size-10 rounded-xl" />
                <span className="grid gap-2">
                  <Bone className="h-3 w-[55%]" />
                  <Bone className="h-2.5 w-[35%]" />
                </span>
                <Bone className="h-3 w-[70px]" />
              </div>
            ))}
          </div>
        </>
      )}
      {kind === "cards" &&
        rows(3).map((row) => (
          <div key={row} className={cn(box, "grid grid-cols-[130px_minmax(0,1fr)] items-center gap-5 p-4 sm:grid-cols-[200px_minmax(0,1fr)]")}>
            <Bone className="aspect-[1.586] w-full rounded-[14px]" />
            <span className="grid gap-2">
              <Bone className="h-3.5 w-[60%]" />
              <Bone className="h-2.5 w-[25%]" />
              <Bone className="h-1.5 w-full" />
            </span>
          </div>
        ))}
      {kind === "detail" && (
        <>
          <div className={cn(box, "grid gap-2 p-[22px]")}>
            <Bone className="h-[18px] w-[60%]" />
            <Bone className="h-3 w-[40%]" />
          </div>
          {rows(3).map((row) => (
            <Bone key={row} className="h-[62px] w-full rounded-[14px]" />
          ))}
          <Bone className="h-[130px] w-full rounded-[20px]" />
        </>
      )}
      {kind === "timeline" && (
        <div className={cn(box, "grid gap-[18px] p-[22px]")}>
          {rows(4).map((row) => (
            <div key={row} className="grid grid-cols-[22px_minmax(0,1fr)] items-center gap-3.5">
              <Bone className="size-[22px] rounded-full" />
              <span className="grid gap-2">
                <Bone className="h-3 w-1/2" />
                <Bone className="h-2.5 w-[30%]" />
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
