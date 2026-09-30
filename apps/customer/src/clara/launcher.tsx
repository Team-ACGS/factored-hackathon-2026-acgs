import { ClaraEntity } from "@clara/ui/components/clara-entity";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUp, ChevronRight, Clock, CreditCard, Store, X } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";

import { useNow } from "../app/use-now";
import { brand } from "../bank/brand";
import { formatMoney } from "../bank/format";
import type { Transaction } from "../bank/types";
import { useI18n } from "../i18n";
import { claimStage, type Claim } from "./claims";
import { chargeTopic, type Topic } from "./topics";

const GREETING_MS = 1900;
const CLOSE_MS = 300;
const LEAVE_MS = 420;
const MAX_DRAFT = 300;

type Phase = "open" | "closing" | "leaving";

interface LauncherProps {
  note: Transaction | undefined;
  claim: Claim | undefined;
  onClosed: () => void;
  onTopic: (topic: Topic | null) => void;
}

const stagger = (index: number) => ({ "--i": index }) as CSSProperties;

export function Launcher({ note, claim, onClosed, onTopic }: LauncherProps) {
  const { locale, t } = useI18n();
  const [phase, setPhase] = useState<Phase>("open");
  const [greeted, setGreeted] = useState(false);
  const [draft, setDraft] = useState("");
  const now = useNow();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const greeting = setTimeout(() => setGreeted(true), GREETING_MS);
    return () => {
      clearTimeout(greeting);
      clearTimeout(timer.current);
    };
  }, []);

  function close() {
    if (phase !== "open") return;
    setPhase("closing");
    timer.current = setTimeout(onClosed, CLOSE_MS);
  }

  function go(topic: Topic | null) {
    if (phase !== "open") return;
    setPhase("leaving");
    timer.current = setTimeout(() => {
      onClosed();
      onTopic(topic);
    }, LEAVE_MS);
  }

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (text) go({ kind: "text", text });
  }

  const typing = draft.trim() !== "";
  const state = phase === "leaving" ? "revisa" : typing ? "escucha" : note && greeted ? "confirma" : "hola";
  const noteAt = note ? new Date(note.transaction_date) : null;
  const noteCaption =
    noteAt &&
    (noteAt.toDateString() === new Date(now).toDateString()
      ? t("clara.noteToday", { time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(noteAt) })
      : t("clara.noteOn", {
          date: new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(noteAt),
        }));
  let index = 0;
  const next = () => stagger(index++);

  return (
    <Dialog.Root open onOpenChange={(open) => !open && close()}>
      <Dialog.Portal>
        <Dialog.Overlay data-phase={phase} className="launcher-scrim fixed inset-0 z-[70] bg-[rgb(14_24_21/0.18)]" />
        <Dialog.Content
          data-phase={phase}
          aria-describedby={undefined}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            (event.currentTarget as HTMLElement | null)?.focus({ preventScroll: true });
          }}
          className="launcher fixed inset-x-2 bottom-[calc(8px+env(safe-area-inset-bottom))] z-[80] grid max-h-[calc(100dvh-40px)] justify-items-center gap-3.5 overflow-y-auto rounded-[30px] px-5 pt-[22px] pb-5 text-center outline-none min-[561px]:inset-x-auto min-[561px]:right-5 min-[561px]:bottom-[calc(20px+env(safe-area-inset-bottom))] min-[561px]:w-[392px]"
        >
          <Dialog.Title className="sr-only">{t("clara.tip")}</Dialog.Title>
          <Dialog.Close className="absolute top-3.5 right-3.5 z-[2] grid size-[34px] place-items-center rounded-full bg-[rgb(23_36_34/0.06)] hover:bg-[rgb(23_36_34/0.12)]">
            <X className="size-[18px]" aria-hidden />
            <span className="sr-only">{t("clara.close")}</span>
          </Dialog.Close>

          <div className="relative -mt-1 -mb-2.5 size-[176px]">
            <ClaraEntity
              state={state}
              motion={phase === "leaving" ? "thinking" : undefined}
              className="launcher-entity absolute inset-0 size-full"
            />
            <span className="launcher-burst" />
            <span className="launcher-burst" />
          </div>

          <h2 className="launcher-stagger font-serif text-[28px] leading-[1.1] font-medium" style={next()}>
            {t("clara.hello")}
          </h2>
          <p className="launcher-stagger -mt-2 text-sm text-ink-2" style={next()}>
            {t("clara.intro", { bank: brand.name })}
          </p>

          {note && (
            <div
              className="launcher-stagger grid w-full gap-2.5 rounded-[20px] border border-line bg-white/85 px-4 py-3.5 text-left"
              style={next()}
            >
              <span className="flex items-center gap-2 text-xs font-semibold tracking-[0.04em] text-ink-3 uppercase">
                <i className="size-2 rounded-full bg-badge" aria-hidden />
                {noteCaption}
              </span>
              <p className="font-serif text-[16.5px] leading-[1.45]">
                {t("clara.note", {
                  merchant: note.merchant_name,
                  amount: formatMoney(note.amount, note.currency, locale),
                })}
              </p>
              <button
                type="button"
                onClick={() => go(chargeTopic(note))}
                className="h-10 justify-self-start rounded-full bg-ink px-[18px] text-sm font-semibold text-white"
              >
                {t("clara.noteAction")}
              </button>
            </div>
          )}

          <div className="grid w-full gap-2">
            <Shortcut
              style={next()}
              icon={<Store className="size-[18px]" />}
              title={t("clara.shortcut.unrecognized")}
              hint={t("clara.shortcut.unrecognizedHint")}
              onClick={() => go({ kind: "unrecognized" })}
            />
            <Shortcut
              style={next()}
              icon={<CreditCard className="size-[18px]" />}
              title={t("clara.shortcut.cards")}
              hint={t("clara.shortcut.cardsHint")}
              onClick={() => go({ kind: "cards" })}
            />
            <Shortcut
              style={next()}
              icon={<Clock className="size-[18px]" />}
              title={t("clara.shortcut.claim")}
              hint={
                claim
                  ? t("clara.shortcut.claimOf", {
                      merchant: claim.merchant_name,
                      status: t(`claim.status.${claimStage(claim, now)}`).toLocaleLowerCase(locale),
                    })
                  : t("clara.shortcut.claimHint")
              }
              onClick={() =>
                go({ kind: "claim", claim_id: claim?.claim_id ?? null, merchant_name: claim?.merchant_name ?? null })
              }
            />
          </div>

          <form
            onSubmit={send}
            className="launcher-stagger flex w-full gap-2 rounded-full border border-line bg-white py-1.5 pr-1.5 pl-4 focus-within:border-[#c9d4e3]"
            style={next()}
          >
            <input
              type="text"
              value={draft}
              maxLength={MAX_DRAFT}
              placeholder={t("clara.ask")}
              aria-label={t("clara.ask")}
              onChange={(event) => setDraft(event.target.value)}
              className="min-w-0 flex-1 bg-transparent text-[14.5px] outline-none"
            />
            <button
              type="submit"
              aria-label={t("clara.send")}
              disabled={!typing}
              className="grid size-[38px] place-items-center rounded-full bg-ink text-white disabled:bg-muted disabled:text-ink-3"
            >
              <ArrowUp className="size-[18px]" aria-hidden />
            </button>
          </form>

          <button
            type="button"
            onClick={() => go(null)}
            className="launcher-stagger text-[13.5px] font-semibold text-ink-2 hover:text-ink"
            style={next()}
          >
            {t("clara.fullChat")} →
          </button>
          <span className="launcher-stagger text-[11.5px] text-ink-3" style={next()}>
            {t("clara.disclosure", { bank: brand.name })}
          </span>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface ShortcutProps {
  icon: ReactNode;
  title: string;
  hint: string;
  style: CSSProperties;
  onClick: () => void;
}

function Shortcut({ icon, title, hint, style, onClick }: ShortcutProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={style}
      className="launcher-stagger grid w-full grid-cols-[38px_minmax(0,1fr)_18px] items-center gap-3 rounded-[18px] border border-[rgb(23_36_34/0.08)] bg-white/70 px-3 py-2.5 text-left transition-[background,transform,border-color] duration-150 hover:-translate-y-px hover:border-[rgb(23_36_34/0.18)] hover:bg-white"
    >
      <span className="grid size-[38px] place-items-center rounded-xl bg-[#edf4fd] text-[#2f67b5]" aria-hidden>
        {icon}
      </span>
      <span>
        <b className="block text-[14.5px]">{title}</b>
        <span className="text-[12.5px] text-ink-3">{hint}</span>
      </span>
      <ChevronRight className="size-[18px] text-ink-3" aria-hidden />
    </button>
  );
}
