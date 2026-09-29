import { Button } from "@clara/ui/components/button";
import { cn } from "@clara/ui/lib/cn";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, Loader2, Plus, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { FormError } from "../auth/field";
import { useI18n } from "../i18n";
import { CardFace } from "./card-face";
import { formatMoney } from "./format";
import { labelOf } from "./labels";
import { StatusBadge } from "./status-badge";
import { SuspiciousDialog } from "./suspicious-dialog";
import { TransactionSheet } from "./transaction-sheet";
import type { ScoreOption, Transaction } from "./types";
import { useCardLedger, type AddRequest } from "./use-card-ledger";

export function CardPage({ productId, transactionId }: { productId: string; transactionId: string | undefined }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const view = useCardLedger(productId);
  const [adding, setAdding] = useState<AddRequest["kind"] | null>(null);
  const [addFailed, setAddFailed] = useState(false);
  const [suspiciousOpen, setSuspiciousOpen] = useState(false);

  function show(id: string | undefined) {
    void navigate({ to: "/cards/$productId", params: { productId }, search: { transaction: id }, replace: !id });
  }

  async function add(request: AddRequest) {
    setAdding(request.kind);
    setAddFailed(false);
    try {
      await view.add(request);
      setSuspiciousOpen(false);
    } catch {
      setAddFailed(true);
    }
    setAdding(null);
  }

  if (view.failed) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <p>{t("app.loadFailed")}</p>
        <Button variant="outline" size="sm" onClick={view.reload}>
          {t("app.retry")}
        </Button>
      </div>
    );
  }

  const card = view.card;
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

        {!card ? (
          <Loader2 className="mx-auto my-16 size-6 animate-spin text-muted-foreground" aria-hidden />
        ) : (
          <>
            <CardFace card={card} className="max-w-sm" />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void add({ kind: "normal" })} disabled={adding !== null}>
                {adding === "normal" ? <Loader2 className="animate-spin" aria-hidden /> : <Plus />}
                {t("card.addNormal")}
              </Button>
              <Button variant="outline" onClick={() => setSuspiciousOpen(true)} disabled={adding !== null}>
                <ShieldAlert />
                {t("card.addSuspicious")}
              </Button>
            </div>
            <FormError message={addFailed ? t("card.addFailed") : null} />

            <section className="flex flex-col gap-3">
              <h2 className="text-base font-semibold">{t("card.transactions")}</h2>
              {view.ledger.transactions.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">{t("card.empty")}</p>
              ) : (
                <ul className="divide-y overflow-hidden rounded-xl border bg-background">
                  {view.ledger.transactions.map((transaction) => (
                    <li key={transaction.transaction_id}>
                      <TransactionRow transaction={transaction} onOpen={() => show(transaction.transaction_id)} />
                    </li>
                  ))}
                </ul>
              )}
              {view.ledger.nextCursor && (
                <Button
                  variant="outline"
                  className="self-center"
                  onClick={() => void view.loadMore()}
                  disabled={view.loadingMore}
                >
                  {view.loadingMore && <Loader2 className="animate-spin" aria-hidden />}
                  {t("card.loadMore")}
                </Button>
              )}
              <FormError message={view.moreFailed ? t("app.loadFailed") : null} />
            </section>

            <TransactionSheet
              card={card}
              transactionId={transactionId}
              listed={view.ledger.transactions.find((transaction) => transaction.transaction_id === transactionId)}
              onClose={() => show(undefined)}
            />
            <SuspiciousDialog
              open={suspiciousOpen}
              busy={adding === "suspicious"}
              onOpenChange={setSuspiciousOpen}
              onSubmit={(score: ScoreOption) => void add({ kind: "suspicious", score })}
            />
          </>
        )}
      </div>
    </div>
  );
}

function TransactionRow({ transaction, onOpen }: { transaction: Transaction; onOpen: () => void }) {
  const { locale, t } = useI18n();
  const struck = transaction.transaction_status === "Declined" || transaction.transaction_status === "Reversed";
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(transaction.transaction_date));
  const category = labelOf(t, "category", transaction.transaction_category);

  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-4 px-4 py-3 text-left outline-none transition-colors hover:bg-muted/50 focus-visible:bg-muted/50"
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
    </button>
  );
}
