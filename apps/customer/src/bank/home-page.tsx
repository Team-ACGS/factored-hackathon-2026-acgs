import { useSuspenseQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";

import { cardLock, claimForTransaction } from "../clara/overlay";
import { useClaraSession } from "../clara/store";
import { useI18n } from "../i18n";
import { textLink } from "./buttons";
import { materialOf, useCardName } from "./card-display";
import { CardFace, CardUsage } from "./card-face";
import { lastDigits } from "./format";
import { isPending } from "./ledger";
import { LedgersOf } from "./ledgers-of";
import { MovementContent, movementRowClass } from "./movement-row";
import { recentMovements } from "./movements";
import { bankQueries } from "./services";
import { TransactionSheet } from "./transaction-sheet";

const RECENT_COUNT = 6;

interface HomePageProps {
  productId: string | undefined;
  transactionId: string | undefined;
}

export function HomePage({ productId, transactionId }: HomePageProps) {
  const { locale, t } = useI18n();
  const navigate = useNavigate();
  const session = useClaraSession();
  const cardName = useCardName();
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const byId = new Map(cards.map((card) => [card.product_id, card]));
  const shortDay = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });

  return (
    <div className="grid gap-9">
      <section className="grid gap-3.5" aria-labelledby="home-cards">
        <h1 id="home-cards" className="text-lg font-semibold">
          {t("home.cards")}
        </h1>
        {cards.length === 0 ? (
          <p className="py-9 text-center text-ink-3">{t("cards.empty")}</p>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-[22px] min-[821px]:grid-cols-3">
            {cards.map((card) => {
              const lock = cardLock(card, session);
              return (
                <div key={card.product_id} className="flex min-w-0 flex-col gap-3">
                  <Link
                    to="/cards/$productId"
                    params={{ productId: card.product_id }}
                    aria-label={t("card.viewMovementsOf", { card: cardName(card) })}
                    className="rounded-[14px] outline-none transition-transform duration-200 hover:-translate-y-0.5 focus-visible:ring-[3px] focus-visible:ring-ring/40"
                  >
                    <CardFace card={card} material={materialOf(cards, card.product_id)} lock={lock} />
                  </Link>
                  <CardUsage card={card} />
                  <Link to="/cards/$productId" params={{ productId: card.product_id }} className={textLink}>
                    {t("card.viewMovements")}
                    <ChevronRight className="size-[18px]" aria-hidden />
                  </Link>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {cards.length > 0 && (
        <section className="grid gap-3.5" aria-labelledby="home-recent">
          <h2 id="home-recent" className="text-lg font-semibold">
            {t("home.recent")}
          </h2>
          <LedgersOf productIds={cards.map((card) => card.product_id)}>
            {(ledgers) => {
              const recent = recentMovements(ledgers, RECENT_COUNT);
              if (recent.length === 0) {
                return <p className="rounded-2xl bg-surface py-9 text-center text-ink-3 shadow-bank">{t("home.noMovements")}</p>;
              }
              return (
                <div className="overflow-hidden rounded-2xl bg-surface shadow-bank">
                  {recent.map((entry) => {
                    const card = isPending(entry) ? undefined : byId.get(entry.product_id);
                    const meta = [shortDay.format(new Date(entry.transaction_date)), card && `•••• ${lastDigits(card.product_number)}`]
                      .filter(Boolean)
                      .join(" · ");
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
                        to="/"
                        search={{ card: entry.product_id, transaction: entry.transaction_id }}
                        className={movementRowClass}
                      >
                        {content}
                      </Link>
                    );
                  })}
                </div>
              );
            }}
          </LedgersOf>
        </section>
      )}

      <TransactionSheet
        card={productId ? byId.get(productId) : undefined}
        transactionId={transactionId}
        onClose={() => void navigate({ to: "/", search: {}, replace: true })}
      />
    </div>
  );
}
