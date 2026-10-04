import { cn } from "@clara/ui/lib/cn";
import { useInfiniteQuery, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { AlertCircle, ChevronRight, Globe, Headset, Siren, Smartphone, Store } from "lucide-react";
import type { ReactNode } from "react";

import { useNow } from "../../app/use-now";
import { materialOf } from "../../bank/card-display";
import { CardFace, CardUsage } from "../../bank/card-face";
import { caseOfTransaction, stageKey, stepsOf } from "../../bank/cases";
import { formatMoney } from "../../bank/format";
import { cardTypeKey, isCredit, labelOf } from "../../bank/labels";
import { entriesOf, isPending } from "../../bank/ledger";
import { MovementContent, movementRowClass } from "../../bank/movement-row";
import { chargeOf, useRow, useRows } from "../../bank/rows";
import { bankQueries } from "../../bank/services";
import type { Card, Case, Transaction } from "../../bank/types";
import type { Row } from "../../chat/conversation";
import { useI18n } from "../../i18n";
import { isBlocked } from "../overlay";
import type { ViewSpec } from "./panel-state";
import { BackLink, box, Caption, ChargeHead, OkPill, Source, Timeline, type TimelineItem } from "./parts";
import { cardLabel, whenText } from "./text";

const CARD_MOVEMENTS = 8;

export interface Pick {
  ids: ReadonlySet<string>;
  selected: string | null;
  choose: (transactionId: string) => void;
}

export interface Navigation {
  open: (spec: ViewSpec) => void;
  back: (() => void) | null;
  disabled: boolean;
  pick?: Pick | null;
}

interface ViewProps<K extends ViewSpec["kind"]> {
  spec: Extract<ViewSpec, { kind: K }>;
  nav: Navigation;
}

export function PanelView({ spec, nav }: { spec: ViewSpec; nav: Navigation }) {
  const content = (() => {
    switch (spec.kind) {
      case "movements":
        return <MovementsView spec={spec} nav={nav} />;
      case "cards":
        return <CardsView spec={spec} nav={nav} />;
      case "card":
        return <CardView spec={spec} nav={nav} />;
      case "movement":
        return <MovementView spec={spec} nav={nav} />;
      case "charge":
        return <ChargeView spec={spec} nav={nav} />;
      case "history":
        return <HistoryView spec={spec} nav={nav} />;
      case "case":
        return <CaseView spec={spec} nav={nav} />;
      case "handoff":
        return <HandoffView spec={spec} nav={nav} />;
    }
  })();
  return (
    <div className="chat-view mx-auto grid max-w-[620px] gap-4">
      {nav.back && <Back nav={nav} />}
      {content}
    </div>
  );
}

function Back({ nav }: { nav: Navigation }) {
  const { t } = useI18n();
  return nav.back ? <BackLink label={t("clara.chat.view.back")} disabled={nav.disabled} onClick={nav.back} /> : null;
}

function useCards(): Card[] {
  return useSuspenseQuery(bankQueries.cards()).data;
}

function useCases(): Case[] {
  return useQuery(bankQueries.cases()).data ?? [];
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-8 items-center gap-2 rounded-full border border-line bg-surface px-3 text-[13px] font-semibold text-ink-2">
      {children}
    </span>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <span className="text-[12.5px] text-ink-3">{children}</span>;
}

function MovementRows({ rows, nav }: { rows: readonly Row[]; nav: Navigation }) {
  const { locale, t } = useI18n();
  const now = useNow();
  const cases = useCases();
  const loaded = useRows(rows.map((row) => ({ product_id: row.productId, transaction_id: row.transactionId })));

  return (
    <div className={cn(box, "overflow-hidden")}>
      {rows.map((row, index) => {
        const tx = loaded[index];
        if (!tx) {
          return (
            <div key={row.transactionId} className={cn(movementRowClass, "sm:px-[18px]")} aria-busy>
              <span className="chat-skeleton size-9 rounded-xl sm:size-10" />
              <span className="grid gap-2">
                <span className="chat-skeleton h-3 w-[55%]" />
                <span className="chat-skeleton h-2.5 w-[35%]" />
              </span>
              <span className="chat-skeleton h-3 w-[70px]" />
            </div>
          );
        }
        const meta = [whenText(tx.transaction_date, now, locale, t), labelOf(t, "channel", tx.channel)]
          .filter(Boolean)
          .join(" · ");
        const pickable = nav.pick?.ids.has(row.transactionId) ?? false;
        const picked = pickable && nav.pick?.selected === row.transactionId;
        return (
          <button
            key={row.transactionId}
            type="button"
            disabled={nav.disabled}
            aria-pressed={pickable ? picked : undefined}
            className={cn(
              movementRowClass,
              "text-[13px] first:rounded-t-[19px] last:rounded-b-[19px] sm:px-[18px] sm:py-[13px]",
              picked && "relative z-[1] bg-surface shadow-[inset_0_0_0_2px_var(--color-ink)] hover:bg-surface",
            )}
            onClick={() => (pickable ? nav.pick?.choose(row.transactionId) : nav.open({ kind: "movement", row }))}
          >
            <MovementContent
              entry={tx}
              meta={meta}
              inClaim={caseOfTransaction(cases, tx.transaction_id) !== undefined}
              tone="clara"
            />
          </button>
        );
      })}
    </div>
  );
}

function MovementsView({ spec, nav }: ViewProps<"movements">) {
  const { t } = useI18n();
  const { count, period, last4 } = spec.readings;
  const picking = spec.rows.some((row) => nav.pick?.ids.has(row.transactionId));
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Pill>{count ?? t("clara.chat.view.movements.shown", { count: String(spec.rows.length) })}</Pill>
        {last4 && <Pill>{last4}</Pill>}
        {period && spec.readings.merchant && <Pill>{period}</Pill>}
      </div>
      <MovementRows rows={spec.rows} nav={nav} />
      {!picking && <Hint>{t("clara.chat.view.movements.hint")}</Hint>}
      <Source />
    </>
  );
}

function CardState({ card }: { card: Card }) {
  const { t } = useI18n();
  const blocked = isBlocked(card);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[13px] font-semibold before:size-2 before:rounded-full before:bg-current",
        blocked ? "text-danger" : "text-ok",
      )}
    >
      {blocked ? t("card.blocked") : t("card.active")}
    </span>
  );
}

function CardsView({ spec, nav }: ViewProps<"cards">) {
  const { t } = useI18n();
  const cards = useCards();
  const shown = spec.cards.flatMap((id) => cards.find((card) => card.product_id === id) ?? []);
  const picking = spec.cards.some((id) => nav.pick?.ids.has(id));
  return (
    <>
      {shown.map((card) => {
        const name = cardLabel(card, t);
        const pickable = nav.pick?.ids.has(card.product_id) ?? false;
        const picked = pickable && nav.pick?.selected === card.product_id;
        return (
          <button
            key={card.product_id}
            type="button"
            disabled={nav.disabled || (picking && !pickable)}
            aria-pressed={pickable ? picked : undefined}
            aria-label={pickable ? name : t("clara.chat.view.card.label", { card: name })}
            className={cn(
              box,
              "grid w-full grid-cols-[130px_minmax(0,1fr)_16px] items-center gap-3.5 p-4 text-left transition-[border-color,translate,opacity] duration-150 hover:-translate-y-0.5 hover:border-[#c9d9f0] disabled:opacity-55 disabled:hover:translate-y-0 disabled:hover:border-line sm:grid-cols-[200px_minmax(0,1fr)_20px] sm:gap-5",
              picked && "border-ink shadow-[inset_0_0_0_1px_var(--color-ink)] hover:border-ink",
            )}
            onClick={() =>
              pickable ? nav.pick?.choose(card.product_id) : nav.open({ kind: "card", productId: card.product_id })
            }
          >
            <CardFace tone="clara" card={card} material={materialOf(cards, card.product_id)} />
            <span className="grid min-w-0 gap-2.5">
              <span className="text-base font-semibold">{name}</span>
              <CardState card={card} />
              <CardUsage card={card} tone="clara" />
            </span>
            {!pickable && <ChevronRight className="size-[18px] text-ink-3" aria-hidden />}
          </button>
        );
      })}
      {!picking && <Hint>{t("clara.chat.view.cards.hint")}</Hint>}
      <Source />
    </>
  );
}

function CardView({ spec, nav }: ViewProps<"card">) {
  const { locale, t } = useI18n();
  const cards = useCards();
  const card = cards.find((item) => item.product_id === spec.productId);
  const ledger = useInfiniteQuery(bankQueries.ledger(spec.productId));
  if (!card) return null;
  const money = (amount: number | string) => formatMoney(String(amount), card.currency, locale);
  const stats: [string, string][] =
    isCredit(card) && card.credit_limit
      ? [
          [t("card.available"), money(Number(card.credit_limit) - Number(card.current_balance ?? 0))],
          [t("clara.chat.view.card.limit"), money(card.credit_limit)],
          [t("clara.chat.view.card.type"), t(cardTypeKey(card))],
        ]
      : [
          [t("card.available"), money(card.current_balance ?? 0)],
          [t("clara.chat.view.card.type"), t(cardTypeKey(card))],
        ];
  const rows = entriesOf(ledger.data)
    .filter((entry): entry is Transaction => !isPending(entry))
    .slice(0, CARD_MOVEMENTS)
    .map((entry) => ({ productId: entry.product_id, transactionId: entry.transaction_id }));
  return (
    <>
      <div className={cn(box, "grid gap-[18px] p-5")}>
        <div className="grid items-center gap-5 sm:grid-cols-[200px_minmax(0,1fr)]">
          <CardFace card={card} material={materialOf(cards, card.product_id)} className="max-w-[240px]" />
          <div className="grid min-w-0 gap-2.5">
            <CardState card={card} />
            <CardUsage card={card} tone="clara" />
          </div>
        </div>
        <div className={cn("grid gap-2 sm:gap-2.5", stats.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2")}>
          {stats.map(([term, value]) => (
            <div
              key={term}
              className="flex min-w-0 items-baseline justify-between gap-3 rounded-[14px] bg-muted px-3.5 py-2.5 sm:grid sm:justify-start sm:gap-0.5 sm:py-3"
            >
              <span className="text-[12.5px] text-ink-3">{term}</span>
              <b className="text-[15px] font-semibold [overflow-wrap:anywhere] tabular-nums sm:text-base">{value}</b>
            </div>
          ))}
        </div>
      </div>
      {rows.length > 0 && (
        <>
          <Caption>{t("clara.chat.view.card.movements")}</Caption>
          <MovementRows rows={rows} nav={nav} />
        </>
      )}
      <Source />
    </>
  );
}

function useCharge(row: Row) {
  const cards = useCards();
  const tx = useRow({ product_id: row.productId, transaction_id: row.transactionId });
  return { tx, card: cards.find((card) => card.product_id === row.productId) };
}

function MovementView({ spec }: ViewProps<"movement">) {
  const { locale, t } = useI18n();
  const now = useNow();
  const cases = useCases();
  const { tx, card } = useCharge(spec.row);
  if (!tx) return <DetailSkeleton />;
  const claim = caseOfTransaction(cases, tx.transaction_id);
  const place = [tx.transaction_city, new Intl.DisplayNames([locale], { type: "region" }).of(tx.transaction_country)]
    .filter(Boolean)
    .join(", ");
  const facts: [string, string | null][] = [
    [t("transaction.status"), claim ? t("pill.claim") : t(`status.${tx.transaction_status}`)],
    [t("transaction.category"), labelOf(t, "category", tx.transaction_category)],
    [t("transaction.channel"), labelOf(t, "channel", tx.channel)],
    [t("transaction.location"), place],
    [t("transaction.card"), card ? cardLabel(card, t) : null],
  ];
  return (
    <>
      <ChargeHead tx={tx} card={card} now={now} />
      <div className={cn(box, "px-5 py-1.5")}>
        <dl className="grid">
          {facts
            .filter(([, value]) => value)
            .map(([term, value]) => (
              <div key={term} className="flex justify-between gap-4 py-2.5 text-sm [&+&]:border-t [&+&]:border-line">
                <dt className="text-ink-3">{term}</dt>
                <dd className="text-right">{value}</dd>
              </div>
            ))}
        </dl>
      </div>
      {claim && (
        <p className="text-[13px] text-ink-3">
          {t("transaction.inClaim")} <span className="font-mono">{claim.case_id}</span>
        </p>
      )}
      <Source />
    </>
  );
}

const reasonIcons: Record<string, typeof Store> = {
  new_merchant: Store,
  foreign_country: Globe,
  unusual_channel: Smartphone,
  score_high: Siren,
};

function ChargeView({ spec }: ViewProps<"charge">) {
  const { locale, t } = useI18n();
  const now = useNow();
  const { tx, card } = useCharge(spec.row);
  const { explanation, reasons = [], habit } = spec.readings;
  if (!tx) return <DetailSkeleton />;
  return (
    <>
      <ChargeHead tx={tx} card={card} now={now} />
      {explanation && (
        <div className={cn(box, "grid gap-2.5 p-5")}>
          <OkPill tone="info">{t("clara.chat.view.charge.reading")}</OkPill>
          <p className="text-ink-2">{explanation.charAt(0).toLocaleUpperCase(locale) + explanation.slice(1)}.</p>
        </div>
      )}
      {reasons.length > 0 && (
        <>
          <Caption>{t("clara.chat.view.charge.signals")}</Caption>
          {reasons.map(({ reason, text }) => {
            const Icon = reasonIcons[reason] ?? AlertCircle;
            return (
              <div
                key={reason}
                className="grid grid-cols-[36px_minmax(0,1fr)] items-center gap-3 rounded-[14px] bg-[#fdf0f2] px-3.5 py-3"
              >
                <span className="grid size-9 place-items-center rounded-[10px] bg-white text-[#a8465a]">
                  <Icon className="size-[18px]" aria-hidden />
                </span>
                <b className="text-[14.5px] font-semibold">{text.charAt(0).toLocaleUpperCase(locale) + text.slice(1)}</b>
              </div>
            );
          })}
        </>
      )}
      {habit && (
        <div className={cn(box, "grid gap-1.5 px-5 py-[18px]")}>
          <b className="text-[14.5px]">{t("clara.chat.view.charge.habit")}</b>
          <p className="text-[14px] text-ink-2">{habit}</p>
        </div>
      )}
      <Source />
    </>
  );
}

function HistoryView({ spec, nav }: ViewProps<"history">) {
  const { t } = useI18n();
  const { merchant, count, typical_amount, period } = spec.readings;
  return (
    <>
      <div className={cn(box, "flex flex-wrap items-end justify-between gap-4 p-[22px]")}>
        <div className="grid min-w-0 gap-0.5">
          <h3 className="text-xl font-semibold [overflow-wrap:anywhere]">{merchant}</h3>
          {period && <span className="text-[13.5px] text-ink-3">{period}</span>}
        </div>
        <div className="grid justify-items-end gap-0.5 text-right">
          {count && <b className="text-base font-semibold">{count}</b>}
          {typical_amount && (
            <span className="text-[13.5px] text-ink-3">
              {t("clara.chat.view.history.typical", { amount: typical_amount })}
            </span>
          )}
        </div>
      </div>
      <Caption>{t("clara.chat.view.history.purchases")}</Caption>
      <MovementRows rows={spec.rows} nav={nav} />
      <Source />
    </>
  );
}

function CaseView({ spec }: ViewProps<"case">) {
  const cases = useCases();
  const shown = spec.cases.flatMap((id) => cases.find((item) => item.complaint_id === id) ?? []);
  if (shown.length === 0) return <DetailSkeleton />;
  return (
    <>
      {shown.map((item) => (
        <CaseCard key={item.complaint_id} item={item} />
      ))}
      <Source claim={shown.every((item) => item.type === "claim")} />
    </>
  );
}

function CaseCard({ item }: { item: Case }) {
  const { locale, t } = useI18n();
  const charge = useRow(chargeOf(item));
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  const items: TimelineItem[] = stepsOf(item).map(({ step, state, at }) => ({
    state,
    title: t(stageKey(item, step)),
    sub:
      at === null
        ? undefined
        : state === "now" && step !== "opened"
          ? t("claim.since", { date: day.format(new Date(at)) })
          : day.format(new Date(at)),
  }));
  return (
    <div className={cn(box, "grid gap-3.5 p-[22px]")}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="grid gap-1.5">
          <Caption>{t(`case.type.${item.type}`)}</Caption>
          {charge && (
            <h3 className="text-[19px] font-semibold">
              {charge.merchant_name} ·{" "}
              <span className="tabular-nums">{formatMoney(charge.amount, charge.currency, locale)}</span>
            </h3>
          )}
        </div>
        <span className="font-mono text-base font-medium">{item.case_id}</span>
      </div>
      <Timeline items={items} stagger={1} />
      {item.summary_points && item.summary_points.length > 0 && <Known item={item} />}
    </div>
  );
}

function HandoffView({ spec, nav }: ViewProps<"handoff">) {
  const { t } = useI18n();
  const subject = spec.subject;
  return (
    <>
      {spec.points.length > 0 && (
        <div className={cn(box, "grid gap-2.5 p-[22px]")}>
          <b className="text-[14.5px]">{t("clara.chat.view.handoff.points")}</b>
          <Points points={spec.points} />
        </div>
      )}
      {subject?.kind === "case" && <CaseView spec={subject} nav={nav} />}
      {subject?.kind === "charge" && <ChargeView spec={subject} nav={nav} />}
      {subject?.kind === "card" && <CardView spec={subject} nav={nav} />}
    </>
  );
}

function Points({ points }: { points: string[] }) {
  return (
    <ul className="grid gap-1.5">
      {points.map((point) => (
        <li key={point} className="grid grid-cols-[14px_minmax(0,1fr)] gap-2 text-[14px] text-ink-2">
          <span className="mt-[9px] size-1.5 rounded-full bg-ink-3" aria-hidden />
          <span>{point}</span>
        </li>
      ))}
    </ul>
  );
}

function Known({ item }: { item: Case }) {
  const { t } = useI18n();
  const points = item.summary_points ?? [];
  const handedOff = item.type !== "claim";
  return (
    <div className="grid gap-2.5 border-t border-line pt-3.5">
      <b className="text-[14.5px]">{t(handedOff ? "clara.chat.view.case.known" : "clara.chat.view.case.recorded")}</b>
      <Points points={points} />
      {handedOff && (
        <p className="flex items-center gap-2 rounded-[14px] bg-muted px-3.5 py-3 text-[13.5px] font-semibold text-ink-2">
          <Headset className="size-[17px] flex-none" aria-hidden />
          {t("clara.chat.view.case.contact")}
        </p>
      )}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="chat-skeletons grid gap-4" aria-hidden>
      <div className={cn(box, "grid gap-2 p-[22px]")}>
        <span className="chat-skeleton h-[18px] w-[60%]" />
        <span className="chat-skeleton h-3 w-[40%]" />
      </div>
      <span className="chat-skeleton h-[62px] w-full rounded-[14px]" />
      <span className="chat-skeleton h-[130px] w-full rounded-[20px]" />
    </div>
  );
}
