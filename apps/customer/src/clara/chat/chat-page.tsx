import { ClaraEntity } from "@clara/ui/components/clara-entity";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ArrowUp, ChevronUp } from "lucide-react";
import { Suspense, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import { PendingPage } from "../../app/app-layout";
import { useNow } from "../../app/use-now";
import { brand } from "../../bank/brand";
import { isPending } from "../../bank/ledger";
import { LedgersOf } from "../../bank/ledgers-of";
import { bankQueries } from "../../bank/services";
import type { Transaction } from "../../bank/types";
import { useI18n } from "../../i18n";
import { useClaraSession } from "../store";
import { barOf } from "./bar";
import type { ClaraChat } from "./contract";
import { Conversation } from "./conversation";
import type { Context } from "./insight";
import { viewMeta } from "./meta";
import { ChatPanel } from "./panel";
import { useClaraChat } from "./seam";
import { currentView } from "./state";

const MAX_TEXT = 600;

export function ClaraChatPage({ customerId }: { customerId: string }) {
  const chat = useClaraChat(customerId);
  return (
    <Suspense fallback={<PendingPage />}>
      <ChatData>{(ctx) => <ChatLayout chat={chat} ctx={ctx} />}</ChatData>
    </Suspense>
  );
}

function ChatData({ children }: { children: (ctx: Context) => ReactNode }) {
  const { data: profile } = useSuspenseQuery(bankQueries.profile());
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const session = useClaraSession();
  const now = useNow();
  return (
    <LedgersOf productIds={cards.map((card) => card.product_id)}>
      {(ledgers) =>
        children({
          profile,
          cards,
          entries: ledgers.flat().filter((entry): entry is Transaction => !isPending(entry)),
          session,
          now,
        })
      }
    </LedgersOf>
  );
}

function ChatLayout({ chat, ctx }: { chat: ClaraChat; ctx: Context }) {
  const { t } = useI18n();
  const { state } = chat;
  const [draft, setDraft] = useState("");
  const [sheet, setSheet] = useState<"open" | "closed">("open");
  const trigger = `${state.current ?? "hero"}:${state.panel.mode}`;
  const [seen, setSeen] = useState(trigger);
  const input = useRef<HTMLTextAreaElement>(null);

  if (seen !== trigger) {
    setSeen(trigger);
    setSheet("open");
  }

  const typing = draft.trim() !== "";
  const face = typing && !state.busy && state.panel.mode !== "searching" ? "escucha" : state.face;
  const bar = barOf(state, ctx, t);
  const view = currentView(state);
  const peek =
    state.panel.mode === "searching"
      ? state.panel.status
      : view && state.panel.mode === "docked"
        ? viewMeta(view.spec, ctx, t).title
        : t("clara.chat.showPanel");

  function resize() {
    const element = input.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 140)}px`;
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text) return;
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
    <div className="chat-app">
      <section className="flex min-h-0 flex-col" aria-label={t("clara.chat.label")}>
        <Conversation chat={chat} ctx={ctx} onReference={() => setSheet("open")} />
        <div className="flex-none px-5 pb-[calc(16px+env(safe-area-inset-bottom))]">
          <div className="mx-auto grid max-w-[680px] gap-2.5">
            {state.chips.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {state.chips.map((chip, index) => (
                  <button
                    key={chip.label}
                    type="button"
                    style={{ animationDelay: `${index * 60}ms` }}
                    className="chat-rise h-9 rounded-full border border-line bg-surface px-3.5 text-[13.5px] font-semibold transition-colors hover:border-[#4c8fe6] hover:bg-[#edf4fd]"
                    onClick={() => chat.send(chip.label)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}
            <button
              type="button"
              className="chat-peek grid-cols-[40px_minmax(0,1fr)_18px] items-center gap-3 rounded-[20px] border border-line bg-surface px-3 py-2 text-left shadow-bank"
              onClick={() => setSheet("open")}
              aria-label={t("clara.chat.showPanel")}
            >
              <ClaraEntity state={face} motion={state.thinking ? "thinking" : "idle"} className="size-10" />
              <span className={state.panel.mode === "searching" ? "chat-shimmer truncate text-sm" : "truncate text-sm font-semibold"}>
                {peek}
              </span>
              <ChevronUp className="size-[18px] text-ink-3" aria-hidden />
            </button>
            <form
              onSubmit={submit}
              className="flex items-end gap-2.5 rounded-3xl border border-line bg-surface py-3 pr-3 pl-[18px] shadow-bank transition-colors focus-within:border-[#c9d4e3]"
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
                disabled={!typing}
                className="grid size-[38px] flex-none place-items-center rounded-xl bg-ink text-white disabled:cursor-default disabled:bg-muted disabled:text-ink-3"
              >
                <ArrowUp className="size-[18px]" aria-hidden />
              </button>
            </form>
            <p className="text-center text-xs text-ink-3">
              {t("clara.chat.fine", { bank: brand.name })}{" "}
              <button type="button" className="underline underline-offset-[3px] hover:text-ink" onClick={chat.reset}>
                {t("demo.reset")}
              </button>
            </p>
          </div>
        </div>
      </section>
      <div className="chat-scrim fixed inset-0 z-[55] bg-[rgb(14_24_21/0.18)]" data-sheet={sheet} onClick={() => setSheet("closed")} />
      <ChatPanel chat={chat} ctx={ctx} bar={bar} face={face} sheet={sheet} onCloseSheet={() => setSheet("closed")} />
    </div>
  );
}
