import { cn } from "@clara/ui/lib/cn";
import { useLayoutEffect, useRef, useState } from "react";

import { MAX_NOTE_LENGTH, type AskOption, type AskPart } from "../../chat/conversation";
import { useI18n } from "../../i18n";

const optionClass =
  "chat-option inline-flex h-11 max-w-full items-center gap-2.5 rounded-full border border-[rgb(23_36_34/0.12)] bg-white/80 px-4 text-[14.5px] font-semibold transition-[border-color,background,box-shadow] duration-150 hover:border-[rgb(23_36_34/0.25)] hover:bg-white focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none";

const confirmClass =
  "h-[46px] min-w-0 rounded-full bg-ink px-6 text-[14.5px] font-semibold text-white transition-opacity duration-200 focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none disabled:cursor-default disabled:opacity-30 max-[900px]:flex-1 min-[901px]:min-w-[240px]";

interface ActionBarProps {
  ask: AskPart;
  gone: boolean;
  inView: boolean;
  picked: AskOption | null;
  onCancelPick: () => void;
  onChoose: (option: AskOption, note?: string) => void;
  onHeight: (height: number) => void;
}

export function ActionBar({ ask, gone, inView, picked, onCancelPick, onChoose, onHeight }: ActionBarProps) {
  const { t } = useI18n();
  const element = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const target = element.current;
    if (!target) return;
    const observer = new ResizeObserver(() => onHeight(target.offsetHeight));
    observer.observe(target);
    return () => observer.disconnect();
  }, [onHeight]);

  return (
    <div
      ref={element}
      className="chat-bar"
      role="group"
      aria-label={t("clara.chat.actions")}
      aria-hidden={gone || undefined}
      data-gone={gone || undefined}
      inert={gone}
    >
      {ask.kind === "show" ? (
        <Direct ask={ask} onChoose={onChoose} />
      ) : inView ? (
        <InView ask={ask} picked={picked} onCancel={onCancelPick} onChoose={onChoose} />
      ) : (
        <Choices ask={ask} onChoose={onChoose} />
      )}
    </div>
  );
}

function Prompt({ children }: { children: string }) {
  return <span className="text-[13.5px] font-semibold text-ink-2">{children}</span>;
}

function Direct({ ask, onChoose }: { ask: AskPart; onChoose: (option: AskOption) => void }) {
  return (
    <>
      {ask.prompt && <Prompt>{ask.prompt}</Prompt>}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {ask.options.map((option) => (
          <button key={option.id} type="button" className={optionClass} onClick={() => onChoose(option)}>
            <span className="truncate">{option.label}</span>
          </button>
        ))}
      </div>
    </>
  );
}

interface InViewProps {
  ask: AskPart;
  picked: AskOption | null;
  onCancel: () => void;
  onChoose: (option: AskOption) => void;
}

function InView({ ask, picked, onCancel, onChoose }: InViewProps) {
  const { t } = useI18n();
  if (!picked) {
    return (
      <>
        {ask.prompt && <Prompt>{ask.prompt}</Prompt>}
        <span className="text-[14.5px] text-ink-2">{t("clara.chat.bar.pickHint")}</span>
      </>
    );
  }
  return (
    <>
      <Prompt>{t("clara.chat.bar.isThis")}</Prompt>
      <span className="max-w-full truncate text-[15px] font-semibold">{picked.label}</span>
      <div className="flex w-full flex-wrap items-center justify-center gap-2">
        <button type="button" className={optionClass} onClick={onCancel}>
          {t("clara.chat.bar.cancel")}
        </button>
        <button type="button" className={confirmClass} onClick={() => onChoose(picked)}>
          {t("clara.chat.bar.thisOne")}
        </button>
      </div>
    </>
  );
}

function Choices({ ask, onChoose }: { ask: AskPart; onChoose: (option: AskOption, note?: string) => void }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<AskOption | null>(null);
  const [note, setNote] = useState("");
  return (
    <>
      {ask.prompt && <Prompt>{ask.prompt}</Prompt>}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {ask.options.map((option) => {
          const pressed = selected?.id === option.id;
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={pressed}
              className={cn(optionClass, pressed && "border-ink bg-white shadow-[0_0_0_1px_var(--color-ink)] hover:border-ink")}
              onClick={() => setSelected(option)}
            >
              <span
                className={cn(
                  "size-4 flex-none rounded-full border-2 border-[rgb(23_36_34/0.3)] transition-[border] duration-150",
                  pressed && "border-[5px] border-ink",
                )}
                aria-hidden
              />
              <span className="truncate">{option.label}</span>
            </button>
          );
        })}
      </div>
      {ask.note && (
        <textarea
          rows={2}
          value={note}
          maxLength={MAX_NOTE_LENGTH}
          placeholder={t("clara.chat.bar.note")}
          aria-label={t("clara.chat.bar.note")}
          onChange={(event) => setNote(event.target.value)}
          className="w-full max-w-[460px] resize-none rounded-2xl border border-[rgb(23_36_34/0.12)] bg-white/80 px-4 py-2.5 text-left text-[14.5px] leading-snug outline-none placeholder:text-ink-3 focus:border-[rgb(23_36_34/0.3)] focus:bg-white"
        />
      )}
      <div className="flex w-full flex-wrap items-center justify-center gap-2">
        {selected && (
          <button
            type="button"
            className={optionClass}
            onClick={() => {
              setSelected(null);
              setNote("");
            }}
          >
            {t("clara.chat.bar.cancel")}
          </button>
        )}
        <button
          type="button"
          className={confirmClass}
          disabled={!selected}
          onClick={() => selected && onChoose(selected, note.trim() || undefined)}
        >
          {selected ? t("clara.chat.bar.confirm", { option: selected.label }) : t("clara.chat.bar.choose")}
        </button>
      </div>
    </>
  );
}
