import { cn } from "@clara/ui/lib/cn";
import { Check, ChevronLeft } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { brand } from "../../bank/brand";
import type { Card, Transaction } from "../../bank/types";
import { useI18n } from "../../i18n";
import { cardLabel, whenText } from "./text";
import { useMoney } from "./use-money";

export const box = "rounded-[20px] border border-line bg-surface shadow-clara";

const staggered = (index: number) => ({ "--i": index }) as CSSProperties;

export function Caption({ children }: { children: ReactNode }) {
  return <span className="text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase">{children}</span>;
}

export function Source({ claim = false, index }: { claim?: boolean; index?: number }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-3" style={index === undefined ? undefined : staggered(index)}>
      <i className="size-[7px] rounded-full bg-[#1f9f7c]" aria-hidden />
      {t(claim ? "clara.chat.claimData" : "clara.chat.accountData", { bank: brand.name })}
    </span>
  );
}

export function OkPill({ children, tone = "ok" }: { children: ReactNode; tone?: "ok" | "info" | "warm" }) {
  return (
    <span
      className={cn(
        "inline-flex h-[26px] w-fit items-center gap-1.5 rounded-full px-2.5 text-[12.5px] font-bold",
        tone === "ok" && "bg-ok-soft text-ok",
        tone === "info" && "bg-info-soft text-info",
        tone === "warm" && "bg-[#fbe1e6] text-[#a8465a]",
      )}
    >
      {tone === "ok" && <Check className="size-3.5" strokeWidth={2.6} aria-hidden />}
      {children}
    </span>
  );
}

export function BackLink({ label, onClick, disabled }: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex w-fit items-center gap-1 py-1 text-sm font-semibold text-ink-2 hover:text-ink disabled:pointer-events-none disabled:opacity-40"
    >
      <ChevronLeft className="size-[18px]" aria-hidden />
      {label}
    </button>
  );
}

export function ChargeHead({ tx, card, now }: { tx: Transaction; card: Card | undefined; now: number }) {
  const { locale, t } = useI18n();
  const money = useMoney();
  const struck = tx.transaction_status === "Declined" || tx.transaction_status === "Reversed";
  const when = whenText(tx.transaction_date, now, locale, t);
  return (
    <div className={cn(box, "flex flex-wrap items-start justify-between gap-4 p-[22px]")}>
      <div className="grid min-w-0 gap-0.5">
        <h3 className="text-xl font-semibold [overflow-wrap:anywhere]">{tx.merchant_name}</h3>
        <span className="text-[13.5px] text-ink-3">
          {when.charAt(0).toLocaleUpperCase(locale) + when.slice(1)}
          {card && ` · ${cardLabel(card, t)}`}
        </span>
      </div>
      <span
        className={cn(
          "text-[34px] leading-none font-semibold tracking-tight tabular-nums",
          struck && "text-ink-3 line-through",
        )}
      >
        {money(tx)}
      </span>
    </div>
  );
}

export function Ticks({ items, stagger }: { items: readonly string[]; stagger?: number }) {
  return (
    <ul className="grid gap-2.5">
      {items.map((item, index) => (
        <li
          key={item}
          className={cn("grid grid-cols-[22px_1fr] gap-2.5 text-[14.5px] text-ink-2", stagger !== undefined && "chat-stg")}
          style={stagger === undefined ? undefined : staggered(stagger + index)}
        >
          <Check className="size-5 text-[#1f9f7c]" aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export interface TimelineItem {
  state: "done" | "now" | "todo";
  title: string;
  sub?: string;
}

export function Timeline({ items, stagger }: { items: readonly TimelineItem[]; stagger?: number }) {
  return (
    <ol className="grid">
      {items.map((item, index) => (
        <li
          key={item.title}
          className={cn(
            "relative grid grid-cols-[22px_1fr] gap-3 pb-4 before:absolute before:top-[22px] before:bottom-0 before:left-2.5 before:w-0.5 before:bg-line last:pb-0 last:before:hidden",
            stagger !== undefined && "chat-stg",
          )}
          style={stagger === undefined ? undefined : staggered(stagger + index)}
        >
          <span
            className={cn(
              "grid size-[22px] place-items-center rounded-full border-2 border-line bg-surface",
              item.state === "done" && "border-[#1f9f7c] bg-[#1f9f7c] text-white",
              item.state === "now" && "border-[#4c8fe6]",
            )}
          >
            {item.state === "done" && <Check className="size-3" strokeWidth={3} aria-hidden />}
            {item.state === "now" && <i className="chat-now-dot size-2 rounded-full bg-[#4c8fe6]" />}
          </span>
          <span>
            <b className="block text-[14.5px] font-semibold">{item.title}</b>
            {item.sub && <span className="text-[13px] text-ink-3">{item.sub}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function Steps({ labels, done, running }: { labels: readonly string[]; done: number; running: boolean }) {
  return (
    <div className={cn(box, "grid gap-3.5 p-[22px]")}>
      {labels.map((label, index) => {
        const state = index < done ? "done" : index === done && running ? "run" : "todo";
        return (
          <div
            key={label}
            className={cn(
              "grid grid-cols-[26px_1fr] items-center gap-3 text-[15px] transition-colors duration-300",
              state === "todo" ? "text-ink-3" : "text-ink",
            )}
          >
            <span
              className={cn(
                "grid size-[26px] place-items-center rounded-full border-2 border-line transition-all duration-300",
                state === "run" && "chat-step-run",
                state === "done" && "border-[#1f9f7c] bg-[#1f9f7c] text-white",
              )}
            >
              {state === "done" && <Check className="size-3.5" strokeWidth={3} aria-hidden />}
            </span>
            <span>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
