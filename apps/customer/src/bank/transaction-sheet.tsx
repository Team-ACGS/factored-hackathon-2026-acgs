import { cn } from "@clara/ui/lib/cn";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { chargeTopic } from "../clara/topics";
import { useOpenClara } from "../clara/entry";
import { useI18n } from "../i18n";
import { BankSheet, Facts, SheetBody, SheetFoot, SheetHead } from "./bank-sheet";
import { pillButton, primaryPillButton } from "./buttons";
import { useCardName } from "./card-display";
import { caseOfTransaction } from "./cases";
import { formatMoney } from "./format";
import { countryName, labelOf } from "./labels";
import { MovementPill } from "./movement-pill";
import { bankQueries } from "./services";
import type { Card, Transaction } from "./types";

interface TransactionSheetProps {
  card: Card | undefined;
  transactionId: string | undefined;
  listed?: Transaction;
  onClose: () => void;
}

export function TransactionSheet({ card, transactionId, listed, onClose }: TransactionSheetProps) {
  const open = card !== undefined && transactionId !== undefined;
  return (
    <BankSheet open={open} onClose={onClose}>
      {open && <Details key={transactionId} card={card} transactionId={transactionId} listed={listed} />}
    </BankSheet>
  );
}

function Details({ card, transactionId, listed }: { card: Card; transactionId: string; listed: Transaction | undefined }) {
  const { locale, t } = useI18n();
  const cases = useQuery(bankQueries.cases()).data ?? [];
  const openClara = useOpenClara();
  const cardName = useCardName();
  const detail = useQuery(bankQueries.transaction(card.product_id, transactionId));

  const transaction = detail.data ?? listed;
  if (!transaction) {
    return (
      <SheetHead
        title={<span className="sr-only">{t("card.movements")}</span>}
        subtitle={detail.isError ? t("transaction.loadFailed") : "…"}
      />
    );
  }

  const claim = caseOfTransaction(cases, transaction.transaction_id);
  const struck = transaction.transaction_status === "Declined" || transaction.transaction_status === "Reversed";
  const place = [transaction.transaction_city, countryName(transaction.transaction_country, locale)]
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <SheetHead
        title={transaction.merchant_name}
        subtitle={new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short" }).format(
          new Date(transaction.transaction_date),
        )}
      />
      <SheetBody>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className={cn("text-[34px] font-semibold tracking-tight tabular-nums", struck && "text-ink-3 line-through")}>
            {formatMoney(transaction.amount, transaction.currency, locale)}
          </span>
          <MovementPill status={transaction.transaction_status} inClaim={claim !== undefined} showApproved />
        </div>
        <Facts
          rows={[
            [t("transaction.card"), cardName(card)],
            [t("transaction.status"), t(`status.${transaction.transaction_status}`)],
            [t("transaction.channel"), labelOf(t, "channel", transaction.channel)],
            [t("transaction.location"), place],
            [t("transaction.category"), labelOf(t, "category", transaction.transaction_category)],
            [
              t("transaction.reference"),
              <span key="reference" className="font-mono text-[12.5px] uppercase">
                {transaction.transaction_id}
              </span>,
            ],
          ]}
        />
        {claim && (
          <p className="text-[13px] text-ink-3">
            {t("transaction.inClaim")} <span className="font-mono">{claim.case_id}</span>
          </p>
        )}
      </SheetBody>
      <SheetFoot>
        {claim ? (
          <Link to="/help" search={{ claim: claim.case_id }} className={cn(pillButton, "w-full")}>
            {t("transaction.viewClaim")}
          </Link>
        ) : (
          <>
            <p className="text-sm font-semibold">{t("transaction.unrecognized")}</p>
            <button type="button" className={cn(primaryPillButton, "w-full")} onClick={() => openClara(chargeTopic(transaction))}>
              {t("transaction.talkToClara")}
            </button>
          </>
        )}
      </SheetFoot>
    </>
  );
}
