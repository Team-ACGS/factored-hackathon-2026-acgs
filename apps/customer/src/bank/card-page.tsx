import { Button } from "@clara/ui/components/button";
import { cn } from "@clara/ui/lib/cn";
import { useMutation, useQueryClient, useSuspenseInfiniteQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, Loader2, Plus, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { clock } from "../api/session";
import { FormError } from "../auth/field";
import { mintId } from "../chat/clock";
import { useI18n } from "../i18n";
import { CardFace } from "./card-face";
import { formatMoney } from "./format";
import { labelOf } from "./labels";
import { isPending, type PendingTransaction } from "./ledger";
import { bankQueries } from "./services";
import { StatusBadge } from "./status-badge";
import { SuspiciousDialog } from "./suspicious-dialog";
import { TransactionSheet } from "./transaction-sheet";
import type { ScoreOption, Transaction } from "./types";

type AddRequest = { kind: "normal" } | { kind: "suspicious"; score: ScoreOption };

export function CardPage({ productId, transactionId }: { productId: string; transactionId: string | undefined }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const ledger = useSuspenseInfiniteQuery(bankQueries.ledger(productId));
  const addition = useMutation(bankQueries.add(queryClient, productId));
  const [addFailed, setAddFailed] = useState(false);
  const [suspiciousOpen, setSuspiciousOpen] = useState(false);

  function close() {
    void navigate({ to: "/cards/$productId", params: { productId }, search: {}, replace: true });
  }

  function add(request: AddRequest) {
    setAddFailed(false);
    setSuspiciousOpen(false);
    addition.mutateAsync({ ...request, transaction_id: mintId(clock) }).catch(() => setAddFailed(true));
  }

  const card = ledger.data.pages[0]?.card;
  if (!card) return null;
  const rows = ledger.data.pages.flatMap((page) => page.transactions);
  const listed = rows.find(
    (entry): entry is Transaction => !isPending(entry) && entry.transaction_id === transactionId,
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
        <Link
          to="/"
          className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-4" aria-hidden />
          {t("card.back")}
        </Link>

        <CardFace card={card} className="max-w-sm" />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => add({ kind: "normal" })}>
            <Plus />
            {t("card.addNormal")}
          </Button>
          <Button variant="outline" onClick={() => setSuspiciousOpen(true)}>
            <ShieldAlert />
            {t("card.addSuspicious")}
          </Button>
        </div>
        <FormError message={addFailed ? t("card.addFailed") : null} />

        <section className="flex flex-col gap-3">
          <h2 className="text-base font-semibold">{t("card.transactions")}</h2>
          {rows.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">{t("card.empty")}</p>
          ) : (
            <ul className="divide-y overflow-hidden rounded-xl border bg-background">
              {rows.map((entry) => (
                <li key={entry.transaction_id}>
                  {isPending(entry) ? (
                    <PendingRow entry={entry} />
                  ) : (
                    <TransactionRow productId={productId} transaction={entry} />
                  )}
                </li>
              ))}
            </ul>
          )}
          {ledger.hasNextPage && (
            <Button
              variant="outline"
              className="self-center"
              onClick={() => void ledger.fetchNextPage()}
              disabled={ledger.isFetchingNextPage}
            >
              {ledger.isFetchingNextPage && <Loader2 className="animate-spin" aria-hidden />}
              {t("card.loadMore")}
            </Button>
          )}
          <FormError message={ledger.isFetchNextPageError ? t("app.loadFailed") : null} />
        </section>

        <TransactionSheet card={card} transactionId={transactionId} listed={listed} onClose={close} />
        <SuspiciousDialog
          open={suspiciousOpen}
          onOpenChange={setSuspiciousOpen}
          onSubmit={(score: ScoreOption) => add({ kind: "suspicious", score })}
        />
      </div>
    </div>
  );
}

const rowClass = "flex w-full items-center gap-4 px-4 py-3 text-left";

function useRowDate(isoDate: string): string {
  const { locale } = useI18n();
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(isoDate));
}

function PendingRow({ entry }: { entry: PendingTransaction }) {
  const { t } = useI18n();
  const date = useRowDate(entry.transaction_date);

  return (
    <div className={cn(rowClass, "text-muted-foreground")} aria-busy>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{t("card.adding")}</p>
        <p className="truncate text-xs">{date}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1" aria-hidden>
        <Loader2 className="my-0.5 size-4 animate-spin" />
        <span className="h-[22px] w-16 rounded-md bg-muted" />
      </div>
    </div>
  );
}

function TransactionRow({ productId, transaction }: { productId: string; transaction: Transaction }) {
  const { locale, t } = useI18n();
  const struck = transaction.transaction_status === "Declined" || transaction.transaction_status === "Reversed";
  const date = useRowDate(transaction.transaction_date);
  const category = labelOf(t, "category", transaction.transaction_category);

  return (
    <Link
      to="/cards/$productId"
      params={{ productId }}
      search={{ transaction: transaction.transaction_id }}
      className={cn(rowClass, "outline-none transition-colors hover:bg-muted/50 focus-visible:bg-muted/50")}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{transaction.merchant_name}</p>
        <p className="truncate text-xs text-muted-foreground">{category ? `${date} · ${category}` : date}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className={cn("text-sm font-medium tabular-nums", struck && "text-muted-foreground line-through")}>
          {formatMoney(transaction.amount, transaction.currency, locale)}
        </span>
        <StatusBadge status={transaction.transaction_status} />
      </div>
    </Link>
  );
}
