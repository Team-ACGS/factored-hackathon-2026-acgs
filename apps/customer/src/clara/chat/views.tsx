import { cn } from "@clara/ui/lib/cn";
import { ChevronRight, Globe, Moon, ShieldAlert, Smartphone, Store } from "lucide-react";
import type { ReactNode } from "react";

import { brand } from "../../bank/brand";
import { materialOf, useLockTime } from "../../bank/card-display";
import { CardFace, CardUsage } from "../../bank/card-face";
import { formatExpiration, formatMoney } from "../../bank/format";
import { cardTypeKey, countryName, isCredit, labelOf } from "../../bank/labels";
import { MovementContent, movementRowClass } from "../../bank/movement-row";
import type { Card, Transaction } from "../../bank/types";
import { useI18n } from "../../i18n";
import { claimSteps } from "../claims";
import { cardLock, claimForTransaction, findClaim } from "../overlay";
import type { ClaraChat } from "./contract";
import { agent } from "./engine";
import {
  cardOf,
  findEntry,
  homeShare,
  hourOf,
  isBlockedCard,
  isRecognized,
  reasonsOf,
  usualHours,
  type Context,
  type Reason,
} from "./insight";
import { BackLink, box, Caption, ChargeHead, OkPill, Source, Steps, Ticks, Timeline, type TimelineItem } from "./parts";
import type { View, ViewSpec } from "./state";
import { cardLabel, hourText, whenText } from "./text";
import { triage } from "./triage";
import { useMoney } from "./use-money";

interface ViewProps<K extends ViewSpec["kind"]> {
  spec: Extract<ViewSpec, { kind: K }>;
  view: View;
  chat: ClaraChat;
  ctx: Context;
}

const CARD_MOVEMENTS = 8;

export function PanelView({ view, chat, ctx }: { view: View; chat: ClaraChat; ctx: Context }) {
  const spec = view.spec;
  const content = (() => {
    switch (spec.kind) {
      case "movements":
        return <MovementsView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "cards":
        return <CardsView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "card":
        return <CardView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "movement":
        return <MovementView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "charge":
        return <ChargeView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "history":
        return <HistoryView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "calm":
        return <CalmView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "blockConfirm":
        return <BlockConfirmView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "blockSteps":
        return <StepsView view={view} chat={chat} kind="block" />;
      case "claimSteps":
        return <StepsView view={view} chat={chat} kind="claim" />;
      case "blockResult":
        return <BlockResultView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "claimConfirm":
        return <ClaimConfirmView spec={spec} view={view} chat={chat} ctx={ctx} />;
      case "claimReceipt":
        return <ClaimView claimId={spec.claimId} ctx={ctx} receipt />;
      case "claimStatus":
        return <ClaimView claimId={spec.claimId} ctx={ctx} receipt={false} />;
      case "agent":
        return <AgentView spec={spec} view={view} chat={chat} ctx={ctx} />;
    }
  })();
  return <div className="chat-view mx-auto grid max-w-[620px] gap-4">{content}</div>;
}

function useRowMeta() {
  const { locale, t } = useI18n();
  return (tx: Transaction, now: number) =>
    [whenText(tx.transaction_date, now, locale, t), labelOf(t, "channel", tx.channel)].filter(Boolean).join(" · ");
}

function MovementRows({
  entries,
  chat,
  ctx,
  origin,
  candidate,
}: {
  entries: readonly Transaction[];
  chat: ClaraChat;
  ctx: Context;
  origin: "card" | "list";
  candidate: string | null;
}) {
  const { t } = useI18n();
  const money = useMoney();
  const meta = useRowMeta();
  const picked = chat.state.pick?.target;

  return (
    <div className={cn(box, "overflow-hidden")}>
      {entries.map((tx) => {
        const outcome = triage(tx, ctx).outcome;
        const suspect = tx.transaction_id === candidate && outcome === "protect";
        const decided = tx.transaction_id === candidate && !suspect;
        const tag = suspect ? (
          <FlagTag tone="warm">{t("clara.chat.view.flag.suspect")}</FlagTag>
        ) : decided && isBlockedCard(tx.product_id, ctx) ? (
          <FlagTag tone="info">{t("clara.chat.view.flag.blocked")}</FlagTag>
        ) : decided && isRecognized(tx.transaction_id, ctx.session) ? (
          <FlagTag tone="ok">{t("clara.chat.view.flag.mine")}</FlagTag>
        ) : null;
        return (
          <button
            key={tx.transaction_id}
            type="button"
            className={cn(
              movementRowClass,
              suspect && "bg-[linear-gradient(90deg,#fdf0f2,#ffffff_80%)] hover:bg-[linear-gradient(90deg,#fbe5ea,#ffffff_80%)]",
              picked === tx.transaction_id && "shadow-[inset_0_0_0_2px_var(--color-ink)]",
            )}
            onClick={() =>
              chat.pick({
                prompt: t("clara.chat.pick.movement"),
                label: `${tx.merchant_name} · ${money(tx)}`,
                cta: t("clara.chat.pick.movementCta"),
                echo: t(outcome === "protect" ? "clara.chat.pick.flaggedEcho" : "clara.chat.pick.movementEcho", {
                  merchant: tx.merchant_name,
                }),
                input: { type: "movement", productId: tx.product_id, transactionId: tx.transaction_id, origin },
                target: tx.transaction_id,
              })
            }
          >
            <MovementContent
              entry={tx}
              meta={meta(tx, ctx.now)}
              inClaim={claimForTransaction(tx.transaction_id, ctx.session) !== undefined}
              tag={tag}
            />
          </button>
        );
      })}
    </div>
  );
}

function FlagTag({ tone, children }: { tone: "warm" | "info" | "ok"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "mt-1 flex h-[22px] w-fit items-center rounded-full px-[9px] text-[11.5px] font-bold",
        tone === "warm" && "bg-[#fbe1e6] text-[#a8465a]",
        tone === "info" && "bg-info-soft text-info",
        tone === "ok" && "bg-ok-soft text-ok",
      )}
    >
      {children}
    </span>
  );
}

function Pill({ tone = "plain", children }: { tone?: "plain" | "warm"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-full border px-3 text-[13px] font-semibold",
        tone === "plain" ? "border-line bg-surface text-ink-2" : "border-[#f5d3da] bg-[#fdf0f2] text-[#a8465a]",
      )}
    >
      {children}
    </span>
  );
}

function MovementsView({ spec, chat, ctx }: ViewProps<"movements">) {
  const { t } = useI18n();
  const entries = spec.transactionIds.flatMap((id) => findEntry(ctx, id) ?? []);
  const candidate = spec.candidate ? findEntry(ctx, spec.candidate) : undefined;
  const open = candidate !== undefined && triage(candidate, ctx).outcome === "protect";
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Pill>{t("clara.chat.view.movements.count", { count: String(entries.length) })}</Pill>
        {candidate &&
          (open ? (
            <Pill tone="warm">{t("clara.chat.view.movements.toConfirm")}</Pill>
          ) : (
            <Pill>{t("clara.chat.view.movements.reviewed")}</Pill>
          ))}
      </div>
      <MovementRows entries={entries} chat={chat} ctx={ctx} origin="list" candidate={spec.candidate} />
      <span className="text-[12.5px] text-ink-3">{t("clara.chat.view.movements.hint")}</span>
      <Source />
    </>
  );
}

function CardState({ card, ctx }: { card: Card; ctx: Context }) {
  const { t } = useI18n();
  const lockTime = useLockTime();
  const lock = cardLock(card, ctx.session);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[13px] font-semibold before:size-2 before:rounded-full before:bg-current",
        lock.blocked ? "text-danger" : "text-ok",
      )}
    >
      {lock.blocked
        ? lock.since
          ? t("card.blockedSince", { time: lockTime(lock.since) })
          : t("card.blocked")
        : t("card.active")}
    </span>
  );
}

function CardsView({ chat, ctx }: ViewProps<"cards">) {
  const { t } = useI18n();
  const picked = chat.state.pick?.target;
  return (
    <>
      {ctx.cards.map((card) => {
        const name = cardLabel(card, t);
        return (
          <button
            key={card.product_id}
            type="button"
            aria-label={t("clara.chat.view.card.label", { card: name })}
            className={cn(
              box,
              "grid w-full grid-cols-[130px_minmax(0,1fr)_16px] items-center gap-3.5 p-4 text-left transition-[border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-[#c9d9f0] sm:grid-cols-[200px_minmax(0,1fr)_20px] sm:gap-5",
              picked === card.product_id && "shadow-[0_0_0_2px_var(--color-ink)]",
            )}
            onClick={() =>
              chat.pick({
                prompt: t("clara.chat.pick.card"),
                label: name,
                cta: t("clara.chat.pick.cardCta"),
                echo: t("clara.chat.pick.cardEcho", { card: name }),
                input: { type: "card", productId: card.product_id },
                target: card.product_id,
              })
            }
          >
            <CardFace card={card} material={materialOf(ctx.cards, card.product_id)} lock={cardLock(card, ctx.session)} />
            <span className="grid min-w-0 gap-2.5">
              <span className="text-base font-semibold">{name}</span>
              <CardState card={card} ctx={ctx} />
              <CardUsage card={card} className="chat-usage" />
            </span>
            <ChevronRight className="size-[18px] text-ink-3" aria-hidden />
          </button>
        );
      })}
      <span className="text-[12.5px] text-ink-3">{t("clara.chat.view.cards.hint")}</span>
      <Source />
    </>
  );
}

function CardView({ spec, chat, ctx }: ViewProps<"card">) {
  const { locale, t } = useI18n();
  const card = cardOf(ctx, spec.productId);
  if (!card) return null;
  const money = (amount: number | string) => formatMoney(String(amount), card.currency, locale);
  const stats: [string, string][] =
    isCredit(card) && card.credit_limit
      ? [
          [t("card.available"), money(Number(card.credit_limit) - Number(card.current_balance ?? 0))],
          [t("clara.chat.view.card.limit"), money(card.credit_limit)],
          [t("clara.chat.view.card.expires"), formatExpiration(card.expiration_date)],
        ]
      : [
          [t("card.available"), money(card.current_balance ?? 0)],
          [t("clara.chat.view.card.type"), t(cardTypeKey(card))],
          [t("clara.chat.view.card.expires"), formatExpiration(card.expiration_date)],
        ];
  const entries = ctx.entries
    .filter((entry) => entry.product_id === card.product_id)
    .sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))
    .slice(0, CARD_MOVEMENTS);
  return (
    <>
      <BackLink label={t("clara.chat.view.cards.title")} onClick={() => chat.navigate({ kind: "cards" }, "orden")} />
      <div className={cn(box, "grid gap-[18px] p-5")}>
        <div className="grid items-center gap-5 sm:grid-cols-[200px_minmax(0,1fr)]">
          <CardFace
            card={card}
            material={materialOf(ctx.cards, card.product_id)}
            lock={cardLock(card, ctx.session)}
            className="max-w-[240px]"
          />
          <div className="grid min-w-0 gap-2.5">
            <CardState card={card} ctx={ctx} />
            <CardUsage card={card} className="chat-usage" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2.5">
          {stats.map(([term, value]) => (
            <div key={term} className="grid gap-0.5 rounded-[14px] bg-muted px-3.5 py-3">
              <span className="text-[12.5px] text-ink-3">{term}</span>
              <b className="text-base font-semibold tabular-nums">{value}</b>
            </div>
          ))}
        </div>
      </div>
      <Caption>{t("clara.chat.view.card.movements")}</Caption>
      <MovementRows entries={entries} chat={chat} ctx={ctx} origin="card" candidate={null} />
      <Source />
    </>
  );
}

function backTo(spec: { productId: string; origin: "card" | "list" }, chat: ClaraChat, ctx: Context, t: ReturnType<typeof useI18n>["t"]) {
  if (spec.origin === "card") {
    const card = cardOf(ctx, spec.productId);
    return card ? (
      <BackLink label={cardLabel(card, t)} onClick={() => chat.navigate({ kind: "card", productId: card.product_id }, "orden")} />
    ) : null;
  }
  const list = [...chat.state.views].reverse().find((view) => view.spec.kind === "movements");
  return list ? (
    <BackLink label={t("clara.chat.view.movement.movements")} onClick={() => chat.navigate(list.spec, "orden")} />
  ) : null;
}

function MovementView({ spec, chat, ctx }: ViewProps<"movement">) {
  const { locale, t } = useI18n();
  const tx = findEntry(ctx, spec.transactionId);
  if (!tx) return null;
  const card = cardOf(ctx, tx.product_id);
  const verdict = triage(tx, ctx);
  const claim = claimForTransaction(tx.transaction_id, ctx.session);
  const [pill, text, tone]: [string, string, "ok" | "info"] = (() => {
    switch (verdict.outcome) {
      case "inClaim":
        return [
          t("clara.chat.view.movement.inClaim"),
          t("clara.chat.view.movement.inClaimText", { claimId: claim?.claim_id ?? "" }),
          "info",
        ];
      case "blocked":
        return [t("clara.chat.view.movement.blocked"), t("clara.chat.view.movement.blockedText"), "info"];
      case "refunded":
        return [t("clara.chat.view.movement.refunded"), t("clara.chat.view.movement.refundedText"), "ok"];
      case "neverCharged":
        return [t("clara.chat.view.movement.neverCharged"), t("clara.chat.view.movement.neverChargedText"), "ok"];
      case "hold":
        return [t("clara.chat.view.movement.hold"), t("clara.chat.view.movement.holdText"), "ok"];
      case "recognized":
        return [t("clara.chat.view.movement.recognized"), t("clara.chat.view.movement.recognizedText"), "ok"];
      case "history":
        return [t("clara.chat.view.movement.history"), t("clara.chat.view.movement.historyText"), "ok"];
      default:
        return [t("clara.chat.view.movement.question"), t("clara.chat.view.movement.questionText"), "ok"];
    }
  })();
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long" }).format(Date.parse(tx.transaction_date));
  return (
    <>
      {backTo(spec, chat, ctx, t)}
      <ChargeHead tx={tx} card={card} now={ctx.now} />
      <div className={cn(box, "grid gap-2.5 p-5")}>
        <OkPill tone={tone}>{pill}</OkPill>
        <p className="text-ink-2">{text}</p>
        {verdict.stale && <p className="text-[13.5px] text-ink-3">{t("clara.chat.view.movement.stale", { date: day })}</p>}
      </div>
      <div className={cn(box, "px-5 py-1.5")}>
        <dl className="grid">
          {(
            [
              [t("transaction.category"), labelOf(t, "category", tx.transaction_category)],
              [t("transaction.status"), claim ? t("pill.claim") : t(`status.${tx.transaction_status}`)],
              [t("transaction.card"), card ? cardLabel(card, t) : null],
            ] as const
          )
            .filter(([, value]) => value)
            .map(([term, value]) => (
              <div key={term} className="flex justify-between gap-4 py-2.5 text-sm [&+&]:border-t [&+&]:border-line">
                <dt className="text-ink-3">{term}</dt>
                <dd className="text-right">{value}</dd>
              </div>
            ))}
        </dl>
      </div>
      <Source />
    </>
  );
}

const reasonIcons: Record<Reason, typeof Store> = {
  newMerchant: Store,
  country: Globe,
  hour: Moon,
  channel: Smartphone,
  score: ShieldAlert,
};

function ChargeView({ spec, ctx }: ViewProps<"charge">) {
  const { locale, t } = useI18n();
  const tx = findEntry(ctx, spec.transactionId);
  if (!tx) return null;
  const card = cardOf(ctx, tx.product_id);
  const band = usualHours(tx, ctx);
  const at = new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(Date.parse(tx.transaction_date));
  const share = homeShare(tx, ctx);
  const home = ctx.profile.country ? countryName(ctx.profile.country, locale) : "";
  const reason = (kind: Reason): [string, string] => {
    switch (kind) {
      case "newMerchant":
        return [t("clara.chat.view.charge.newMerchant"), t("clara.chat.view.charge.newMerchantText")];
      case "country":
        return [
          t("clara.chat.view.charge.country", { country: countryName(tx.transaction_country, locale) }),
          t("clara.chat.view.charge.countryText", {
            home: String(share.home),
            total: String(share.total),
            homeCountry: home,
          }),
        ];
      case "hour":
        return [
          t("clara.chat.view.charge.hour", { time: at }),
          t("clara.chat.view.charge.hourText", {
            from: band ? hourText(band.from, locale) : "",
            to: band ? hourText(band.to, locale) : "",
          }),
        ];
      case "channel":
        return [
          t("clara.chat.view.charge.channel", {
            channel: (labelOf(t, "channel", tx.channel) ?? tx.channel).toLocaleLowerCase(locale),
          }),
          t("clara.chat.view.charge.channelText"),
        ];
      case "score":
        return [t("clara.chat.view.charge.score"), t("clara.chat.view.charge.scoreText")];
    }
  };
  return (
    <>
      <ChargeHead tx={tx} card={card} now={ctx.now} />
      <Caption>{t("clara.chat.view.charge.why")}</Caption>
      {reasonsOf(tx, ctx).map((kind) => {
        const Icon = reasonIcons[kind];
        const [title, text] = reason(kind);
        return (
          <div key={kind} className="grid grid-cols-[36px_minmax(0,1fr)] items-center gap-3 rounded-[14px] bg-[#fdf0f2] px-3.5 py-3">
            <span className="grid size-9 place-items-center rounded-[10px] bg-white text-[#a8465a]">
              <Icon className="size-[18px]" aria-hidden />
            </span>
            <span>
              <b className="block text-[14.5px]">{title}</b>
              <span className="text-[13px] text-ink-2">{text}</span>
            </span>
          </div>
        );
      })}
      {band && <HoursChart tx={tx} band={band} at={at} />}
      <Source />
    </>
  );
}

function HoursChart({ tx, band, at }: { tx: Transaction; band: NonNullable<ReturnType<typeof usualHours>>; at: string }) {
  const { locale, t } = useI18n();
  const x = (hour: number) => 20 + (hour / 24) * 520;
  const charge = hourOf(tx.transaction_date);
  return (
    <div className={cn(box, "grid gap-2.5 px-5 py-[18px]")}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <b className="text-[14.5px]">{t("clara.chat.view.charge.hours")}</b>
        <span className="inline-flex items-center gap-1.5 text-xs text-ink-3">
          <i className="size-[7px] rounded-full bg-[#1f9f7c]" aria-hidden />
          {t("clara.chat.view.charge.hoursRange")}
        </span>
      </div>
      <svg
        viewBox="0 0 560 92"
        role="img"
        className="block h-auto w-full overflow-visible"
        aria-label={t("clara.chat.view.charge.hoursLabel", {
          from: hourText(band.from, locale),
          to: hourText(band.to, locale),
          time: at,
        })}
      >
        <rect x={x(band.from)} y="30" width={Math.max(0, x(band.to) - x(band.from))} height="32" rx="16" fill="#e2f0ea" />
        <line x1="20" y1="46" x2="540" y2="46" stroke="#e3e8e5" strokeWidth="2" />
        {[0, 6, 12, 18, 24].map((hour) => (
          <text key={hour} x={x(hour)} y="86" textAnchor="middle" fontSize="12" fill="#7a8986">
            {hourText(hour, locale)}
          </text>
        ))}
        {band.hours.map((hour, index) => (
          <circle key={index} cx={x(hour).toFixed(1)} cy="46" r="5" fill="#1f9f7c" opacity=".55" />
        ))}
        <circle cx={x(charge)} cy="46" r="15" fill="#e0677c" opacity=".18">
          <animate attributeName="r" values="9;17;9" dur="2s" repeatCount="indefinite" />
        </circle>
        <circle cx={x(charge)} cy="46" r="7" fill="#e0677c" />
        <text x={x(charge)} y="18" textAnchor="middle" fontSize="12.5" fontWeight="700" fill="#a8465a">
          {at}
        </text>
      </svg>
    </div>
  );
}

function HistoryView({ spec, chat, ctx }: ViewProps<"history">) {
  const { t } = useI18n();
  const tx = findEntry(ctx, spec.transactionId);
  if (!tx) return null;
  const prior = triage(tx, ctx).prior.slice(0, 5);
  return (
    <>
      <ChargeHead tx={tx} card={cardOf(ctx, tx.product_id)} now={ctx.now} />
      <Caption>{t("clara.chat.view.history.earlier", { merchant: tx.merchant_name })}</Caption>
      <MovementRows entries={prior} chat={chat} ctx={ctx} origin="list" candidate={null} />
      <Source />
    </>
  );
}

function CalmView({ spec, chat, ctx }: ViewProps<"calm">) {
  const { t } = useI18n();
  const tx = findEntry(ctx, spec.transactionId);
  const list = [...chat.state.views].reverse().find((view) => view.spec.kind === "movements");
  return (
    <>
      {list && <BackLink label={t("clara.chat.view.movement.movements")} onClick={() => chat.navigate(list.spec, "orden")} />}
      <div className={cn(box, "grid gap-2.5 p-5")}>
        <OkPill>{t("clara.chat.view.calm.kicker")}</OkPill>
        <h3 className="text-[19px] font-semibold">{t("clara.chat.view.calm.heading")}</h3>
        <p className="text-ink-2">{t("clara.chat.view.calm.text", { merchant: tx?.merchant_name ?? "" })}</p>
      </div>
    </>
  );
}

function otherCardsLine(card: Card, ctx: Context, t: ReturnType<typeof useI18n>["t"]): string | null {
  const others = ctx.cards
    .filter((item) => item.product_id !== card.product_id && !isBlockedCard(item.product_id, ctx))
    .map((item) => cardLabel(item, t));
  if (others.length === 0) return null;
  const joined =
    others.length === 1
      ? (others[0] ?? "")
      : `${others.slice(0, -1).join(", ")} ${t("clara.chat.view.blockConfirm.and")} ${others[others.length - 1] ?? ""}`;
  return t(others.length === 1 ? "clara.chat.view.blockConfirm.other" : "clara.chat.view.blockConfirm.others", {
    cards: joined,
  });
}

function BlockConfirmView({ spec, ctx }: ViewProps<"blockConfirm">) {
  const { t } = useI18n();
  const card = cardOf(ctx, spec.productId);
  if (!card) return null;
  const lock = cardLock(card, ctx.session);
  const others = otherCardsLine(card, ctx, t);
  return (
    <div className={cn(box, "grid gap-[18px] p-[22px]")}>
      <div className="grid items-center gap-5 sm:grid-cols-[180px_minmax(0,1fr)]">
        <CardFace card={card} material={materialOf(ctx.cards, card.product_id)} lock={lock} className="max-w-[240px]" />
        <div className="grid gap-2">
          <h3 className="text-xl font-semibold">
            {lock.blocked
              ? t("clara.chat.view.blockConfirm.already")
              : t("clara.chat.view.blockConfirm.heading", { card: cardLabel(card, t) })}
          </h3>
          <p className="text-[14.5px] text-ink-2">
            {t(spec.lost ? "clara.chat.view.blockConfirm.textLost" : "clara.chat.view.blockConfirm.text")}
          </p>
        </div>
      </div>
      <Ticks
        items={[
          t("clara.chat.view.blockConfirm.rejected"),
          ...(others ? [others] : []),
          t("clara.chat.view.blockConfirm.person"),
        ]}
      />
    </div>
  );
}

function StepsView({ view, chat, kind }: { view: View; chat: ClaraChat; kind: "block" | "claim" }) {
  const { t } = useI18n();
  const labels =
    kind === "block"
      ? [
          t("clara.chat.view.blockSteps.one"),
          t("clara.chat.view.blockSteps.two", { bank: brand.name }),
          t("clara.chat.view.blockSteps.three"),
        ]
      : [
          t("clara.chat.view.claimSteps.one"),
          t("clara.chat.view.claimSteps.two", { bank: brand.name }),
          t("clara.chat.view.claimSteps.three"),
        ];
  const done = chat.state.steps[view.id] ?? labels.length;
  return <Steps labels={labels} done={done} running={chat.state.busy && chat.state.current === view.id} />;
}

function BlockResultView({ spec, ctx }: ViewProps<"blockResult">) {
  const { t } = useI18n();
  const lockTime = useLockTime();
  const money = useMoney();
  const card = cardOf(ctx, spec.productId);
  if (!card) return null;
  const lock = cardLock(card, ctx.session);
  const tx = spec.transactionId ? findEntry(ctx, spec.transactionId) : undefined;
  const items: TimelineItem[] = [
    { state: "done", title: t("clara.chat.view.blockResult.blocked"), sub: lock.since ? lockTime(lock.since) : undefined },
    {
      state: "done",
      title: t("clara.chat.view.blockResult.opened"),
      sub: tx
        ? t("clara.chat.view.blockResult.openedCharge", { merchant: tx.merchant_name, amount: money(tx) })
        : t("clara.chat.view.blockResult.openedCard", { card: cardLabel(card, t) }),
    },
    { state: "now", title: t("clara.chat.view.blockResult.review"), sub: t("clara.chat.view.blockResult.reviewNow") },
    { state: "todo", title: t("clara.chat.view.blockResult.next"), sub: t("clara.chat.view.blockResult.nextText") },
  ];
  return (
    <>
      <div className={cn(box, "grid items-center gap-5 p-[22px] sm:grid-cols-[180px_minmax(0,1fr)]")}>
        <CardFace card={card} material={materialOf(ctx.cards, card.product_id)} lock={lock} animateLock className="max-w-[240px]" />
        <div className="grid gap-2">
          <OkPill>{t("clara.chat.view.confirmed")}</OkPill>
          <h3 className="text-xl font-semibold">{t("clara.chat.view.blockResult.heading")}</h3>
          <p className="text-[14.5px] text-ink-2">{t("clara.chat.view.blockResult.text")}</p>
        </div>
      </div>
      <div className={cn(box, "grid gap-3.5 p-[22px]")}>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <Caption>{t("clara.chat.view.blockResult.case")}</Caption>
          <span className="font-mono text-base font-medium">{spec.caseId}</span>
        </div>
        <Timeline items={items} />
        <p className="text-[13px] text-ink-3">{t("clara.chat.view.refundNote")}</p>
      </div>
      <Source />
    </>
  );
}

function ClaimConfirmView({ spec, ctx }: ViewProps<"claimConfirm">) {
  const { t } = useI18n();
  const tx = findEntry(ctx, spec.transactionId);
  const card = cardOf(ctx, spec.productId);
  if (!tx) return null;
  return (
    <>
      <ChargeHead tx={tx} card={card} now={ctx.now} />
      <div className={cn(box, "grid gap-[18px] p-[22px]")}>
        <h3 className="text-xl font-semibold">{t("clara.chat.view.claimConfirm.heading")}</h3>
        <Ticks
          items={[
            t("clara.chat.view.claimConfirm.review"),
            t("clara.chat.view.claimConfirm.card", { card: card ? cardLabel(card, t) : "" }),
            t("clara.chat.view.claimConfirm.refund"),
          ]}
        />
      </div>
      <Source />
    </>
  );
}

function ClaimView({ claimId, ctx, receipt }: { claimId: string; ctx: Context; receipt: boolean }) {
  const { locale, t } = useI18n();
  const money = useMoney();
  const claim = findClaim(claimId, ctx.session);
  if (!claim) return null;
  const card = cardOf(ctx, claim.product_id);
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  const items: TimelineItem[] = claimSteps(claim, ctx.now).map((step) => {
    const date = day.format(Date.parse(step.at));
    return {
      state: step.state,
      title: t(`claim.stage.${step.stage}`),
      sub:
        step.state === "todo"
          ? undefined
          : step.state === "now" && step.stage !== "opened"
            ? t("claim.since", { date })
            : date,
    };
  });
  return (
    <>
      <div className={cn(box, "grid gap-3.5 p-[22px]")}>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="grid gap-1.5">
            {receipt ? <OkPill>{t("clara.chat.view.confirmed")}</OkPill> : <Caption>{t("clara.chat.view.claim.kicker")}</Caption>}
            <h3 className="text-[19px] font-semibold">
              {claim.merchant_name} · <span className="tabular-nums">{money(claim)}</span>
            </h3>
          </div>
          <span className="font-mono text-base font-medium">{claim.claim_id}</span>
        </div>
        <Timeline items={items} />
        {receipt && card && (
          <p className="text-[13px] text-ink-3">{t("clara.chat.view.claimReceipt.note", { card: cardLabel(card, t) })}</p>
        )}
      </div>
      <Source claim />
    </>
  );
}

function AgentView({ spec, ctx }: ViewProps<"agent">) {
  const { locale, t } = useI18n();
  const lockTime = useLockTime();
  const money = useMoney();
  const card = cardOf(ctx, spec.productId);
  const tx = spec.transactionId ? findEntry(ctx, spec.transactionId) : undefined;
  const since = card ? cardLock(card, ctx.session).since : null;
  const knows = [
    ...(tx
      ? [
          t("clara.chat.view.agent.charge", {
            merchant: tx.merchant_name,
            amount: money(tx),
            when: whenText(tx.transaction_date, ctx.now, locale, t),
          }),
        ]
      : []),
    t(spec.lost ? "clara.chat.view.agent.lost" : "clara.chat.view.agent.notMe"),
    ...(card && since ? [t("clara.chat.view.agent.blocked", { card: cardLabel(card, t), time: lockTime(since) })] : []),
    t("clara.chat.view.agent.case", { caseId: spec.caseId }),
  ];
  return (
    <>
      <div className={cn(box, "flex items-center gap-4 p-[22px]")}>
        <span className="relative grid size-16 flex-none place-items-center rounded-full bg-[linear-gradient(135deg,#e7eef7,#d5e2f3)] text-xl font-bold text-info after:absolute after:right-0.5 after:bottom-0.5 after:size-3.5 after:rounded-full after:bg-[#2fb67a] after:shadow-[0_0_0_3px_#ffffff]">
          {agent.initials}
        </span>
        <div>
          <h3 className="text-xl font-semibold">{agent.name}</h3>
          <span className="text-[13.5px] text-ink-3">{t("clara.chat.view.agent.online")}</span>
        </div>
      </div>
      <Caption>{t("clara.chat.view.agent.knows", { name: agent.name })}</Caption>
      <div className={cn(box, "px-5 py-[18px]")}>
        <Ticks items={knows} />
      </div>
      <Source />
    </>
  );
}
