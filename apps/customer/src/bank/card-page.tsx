import { cn } from "@clara/ui/lib/cn";
import { useQueryClient, useSuspenseInfiniteQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, Loader2, Search } from "lucide-react";
import { useState } from "react";

import { FormError } from "../auth/field";
import { claimForTransaction, isBlocked } from "../clara/overlay";
import { useClaraSession } from "../clara/store";
import { useI18n } from "../i18n";
import { pillButton, textLink } from "./buttons";
import { materialOf } from "./card-display";
import { CardFace, CardUsage } from "./card-face";
import { cardTypeKey, labelOf } from "./labels";
import { entriesOf, findTransaction, isPending } from "./ledger";
import { MovementContent, movementRowClass } from "./movement-row";
import {
  dayKey,
  daysBetween,
  groupByDay,
  isFiltering,
  matches,
  movementFilters,
  type MovementFilter,
} from "./movements";
import { ensureLedgerUntil } from "./queries";
import { bankQueries } from "./services";
import { TransactionSheet } from "./transaction-sheet";

export function CardPage({ productId, transactionId }: { productId: string; transactionId: string | undefined }) {
  const { locale, t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const session = useClaraSession();
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const ledger = useSuspenseInfiniteQuery(bankQueries.ledger(productId));
  const [filter, setFilter] = useState<MovementFilter>("all");
  const [query, setQuery] = useState("");
  const [loadingAll, setLoadingAll] = useState(false);
  const [loadAllFailed, setLoadAllFailed] = useState(false);

  const card = ledger.data.pages[0]?.card;
  if (!card) return null;
  const entries = entriesOf(ledger.data);
  const blocked = isBlocked(card);
  const filtering = isFiltering(filter, query);
  const visible = entries.filter((entry) => matches(entry, filter, query));
  const today = dayKey(new Date().toISOString());
  const time = new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit" });
  const longDay = new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });

  function dayLabel(day: string): string {
    const age = daysBetween(day, today);
    if (age === 0) return t("day.today");
    if (age === 1) return t("day.yesterday");
    return longDay.format(new Date(`${day}T12:00:00Z`));
  }

  function loadEverything() {
    if (!ledger.hasNextPage || loadingAll) return;
    setLoadingAll(true);
    setLoadAllFailed(false);
    ensureLedgerUntil(queryClient, bankQueries.ledger(productId), () => false)
      .catch(() => setLoadAllFailed(true))
      .finally(() => setLoadingAll(false));
  }

  function narrow(nextFilter: MovementFilter, nextQuery: string) {
    setFilter(nextFilter);
    setQuery(nextQuery);
    if (isFiltering(nextFilter, nextQuery)) loadEverything();
  }

  return (
    <div className="grid gap-9">
      <Link to="/" className={textLink}>
        <ChevronLeft className="size-[18px]" aria-hidden />
        {t("card.back")}
      </Link>

      <section className="grid items-center gap-7 min-[821px]:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
        <CardFace card={card} material={materialOf(cards, productId)} className="max-w-80 min-[821px]:max-w-none" />
        <div className="grid min-w-0 gap-3.5">
          <h1 className="text-[clamp(28px,4.6vw,36px)] leading-[1.1] font-semibold tracking-tight">{t(cardTypeKey(card))}</h1>
          <span
            className={cn(
              "inline-flex w-fit items-center gap-1.5 text-[13.5px] font-semibold text-ok before:size-2 before:rounded-full before:bg-current",
              blocked && "text-danger",
            )}
          >
            {blocked ? t("card.blocked") : t("card.active")}
          </span>
          <CardUsage card={card} className="max-w-[420px]" />
        </div>
      </section>

      <section className="grid gap-3.5" aria-labelledby="card-movements">
        <h2 id="card-movements" className="text-lg font-semibold">
          {t("card.movements")}
        </h2>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex h-[42px] max-w-[360px] flex-[1_1_240px] items-center gap-2 rounded-full border border-line bg-surface px-3.5 text-ink-3 focus-within:border-primary">
            <Search className="size-[18px] shrink-0" aria-hidden />
            <input
              type="search"
              value={query}
              placeholder={t("card.search")}
              aria-label={t("card.search")}
              onChange={(event) => narrow(filter, event.target.value)}
              className="min-w-0 flex-1 bg-transparent text-ink outline-none"
            />
          </label>
          <div className="flex max-w-full gap-1 overflow-x-auto rounded-full bg-muted p-1" role="group" aria-label={t("card.filters")}>
            {movementFilters.map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={filter === option}
                onClick={() => narrow(option, query)}
                className="h-[34px] rounded-full px-3.5 text-[13.5px] font-semibold whitespace-nowrap text-ink-2 aria-pressed:bg-surface aria-pressed:text-ink aria-pressed:shadow-[0_1px_2px_rgb(0_0_0/0.08)]"
              >
                {t(`filter.${option}`)}
              </button>
            ))}
          </div>
        </div>

        {filtering && loadingAll && (
          <p role="status" className="flex items-center gap-2 text-[13px] text-ink-3">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {t("card.loadingAll")}
          </p>
        )}
        <FormError message={loadAllFailed ? t("app.loadFailed") : null} />

        {visible.length === 0 ? (
          <p className="rounded-2xl bg-surface px-4 py-9 text-center text-ink-3 shadow-bank">
            {filtering ? t("card.noMatches") : t("home.noMovements")}
          </p>
        ) : (
          <div className="grid gap-[22px]">
            {groupByDay(visible).map((group) => (
              <div key={group.day} className="grid gap-2">
                <h3 className="pl-1 text-[13px] font-semibold text-ink-3 first-letter:uppercase">{dayLabel(group.day)}</h3>
                <div className="overflow-hidden rounded-2xl bg-surface shadow-bank">
                  {group.entries.map((entry) => {
                    const category = isPending(entry) ? null : labelOf(t, "category", entry.transaction_category);
                    const meta = [time.format(new Date(entry.transaction_date)), category].filter(Boolean).join(" · ");
                    const content = (
                      <MovementContent
                        entry={entry}
                        meta={meta}
                        inClaim={claimForTransaction(entry.transaction_id, session) !== undefined}
                      />
                    );
                    return isPending(entry) ? (
                      <div key={entry.transaction_id} className={movementRowClass} aria-busy>
                        {content}
                      </div>
                    ) : (
                      <Link
                        key={entry.transaction_id}
                        to="/cards/$productId"
                        params={{ productId }}
                        search={{ transaction: entry.transaction_id }}
                        className={movementRowClass}
                      >
                        {content}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {!filtering && ledger.hasNextPage && (
          <button
            type="button"
            className={cn(pillButton, "justify-self-center")}
            onClick={() => void ledger.fetchNextPage()}
            disabled={ledger.isFetchingNextPage}
          >
            {ledger.isFetchingNextPage && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {t("card.loadMore")}
          </button>
        )}
        {!filtering && <FormError message={ledger.isFetchNextPageError ? t("app.loadFailed") : null} />}
      </section>

      <TransactionSheet
        card={card}
        transactionId={transactionId}
        listed={findTransaction(entries, transactionId)}
        onClose={() => void navigate({ to: "/cards/$productId", params: { productId }, search: {}, replace: true })}
      />
    </div>
  );
}
