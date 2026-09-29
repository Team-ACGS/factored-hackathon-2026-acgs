import { Button } from "@clara/ui/components/button";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@clara/ui/components/sheet";
import { cn } from "@clara/ui/lib/cn";
import { Link } from "@tanstack/react-router";
import { MessageCircleQuestion } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { useI18n } from "../i18n";
import { formatMoney, lastDigits } from "./format";
import { cardTypeKey, countryName, labelOf } from "./labels";
import { bank } from "./services";
import { StatusBadge } from "./status-badge";
import type { Card, Transaction } from "./types";

interface TransactionSheetProps {
  card: Card;
  transactionId: string | undefined;
  listed: Transaction | undefined;
  onClose: () => void;
}

export function TransactionSheet({ card, transactionId, listed, onClose }: TransactionSheetProps) {
  const { t } = useI18n();

  return (
    <Sheet open={transactionId !== undefined} onOpenChange={(open) => !open && onClose()}>
      <SheetContent closeLabel={t("transaction.close")}>
        {transactionId && <Details key={transactionId} card={card} transactionId={transactionId} listed={listed} />}
      </SheetContent>
    </Sheet>
  );
}

function Details({ card, transactionId, listed }: { card: Card; transactionId: string; listed: Transaction | undefined }) {
  const { locale, t } = useI18n();
  const [fetched, setFetched] = useState<Transaction | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    bank.transaction(card.product_id, transactionId).then(
      (transaction) => active && setFetched(transaction),
      () => active && setFailed(true),
    );
    return () => {
      active = false;
    };
  }, [card.product_id, transactionId]);

  const transaction = fetched ?? listed;
  if (!transaction) {
    return (
      <SheetHeader>
        <SheetTitle className="sr-only">{t("card.transactions")}</SheetTitle>
        <SheetDescription>{failed ? t("transaction.loadFailed") : "…"}</SheetDescription>
      </SheetHeader>
    );
  }

  const when = new Date(transaction.transaction_date);
  const struck = transaction.transaction_status === "Declined" || transaction.transaction_status === "Reversed";
  const place = [transaction.transaction_city, countryName(transaction.transaction_country, locale)]
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <SheetHeader>
        <SheetTitle>{transaction.merchant_name}</SheetTitle>
        <SheetDescription>
          {new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short" }).format(when)}
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-col gap-6 px-6">
        <div className="flex items-center justify-between gap-3">
          <p className={cn("text-3xl font-semibold tabular-nums", struck && "text-muted-foreground line-through")}>
            {formatMoney(transaction.amount, transaction.currency, locale)}
          </p>
          <StatusBadge status={transaction.transaction_status} />
        </div>
        <dl className="grid gap-3 text-sm">
          <Row term={t("transaction.card")}>
            {t(cardTypeKey(card))} •••• {lastDigits(card.product_number)}
          </Row>
          <Row term={t("transaction.category")}>{labelOf(t, "category", transaction.transaction_category)}</Row>
          <Row term={t("transaction.channel")}>{labelOf(t, "channel", transaction.channel)}</Row>
          <Row term={t("transaction.location")}>{place}</Row>
          <Row term={t("transaction.id")}>
            <span className="font-mono text-xs break-all">{transaction.transaction_id}</span>
          </Row>
        </dl>
      </div>
      <SheetFooter className="border-t">
        <p className="text-sm font-medium">{t("transaction.unrecognized")}</p>
        <Button asChild>
          <Link to="/chat">
            <MessageCircleQuestion />
            {t("transaction.askClara")}
          </Link>
        </Button>
      </SheetFooter>
    </>
  );
}

function Row({ term, children }: { term: string; children: ReactNode }) {
  if (children === null || children === "") return null;
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3">
      <dt className="text-muted-foreground">{term}</dt>
      <dd>{children}</dd>
    </div>
  );
}
