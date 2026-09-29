import { useCallback, useEffect, useState } from "react";

import { clock } from "../api/session";
import { mintId } from "../chat/clock";
import { appendPage, prepend, type Ledger } from "./ledger";
import { bank } from "./services";
import type { Card, ScoreOption, Transaction } from "./types";

export type AddRequest = { kind: "normal" } | { kind: "suspicious"; score: ScoreOption };

export function useCardLedger(productId: string) {
  const [card, setCard] = useState<Card | null>(null);
  const [ledger, setLedger] = useState<Ledger>({ transactions: [], nextCursor: null });
  const [failed, setFailed] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreFailed, setMoreFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const requestedAt = Date.now();
    bank.card(productId).then(
      (page) => {
        if (!active) return;
        clock.sync(page.server_time, requestedAt, Date.now());
        setCard(page.card);
        setLedger({ transactions: page.transactions, nextCursor: page.next_cursor });
      },
      () => active && setFailed(true),
    );
    return () => {
      active = false;
    };
  }, [productId, attempt]);

  const loadMore = useCallback(async () => {
    if (!ledger.nextCursor) return;
    setLoadingMore(true);
    setMoreFailed(false);
    try {
      const page = await bank.card(productId, ledger.nextCursor);
      setLedger((current) => appendPage(current, page.transactions, page.next_cursor));
    } catch {
      setMoreFailed(true);
    }
    setLoadingMore(false);
  }, [productId, ledger.nextCursor]);

  const add = useCallback(
    async (request: AddRequest): Promise<Transaction> => {
      const added = await bank.add(productId, { ...request, transaction_id: mintId(clock) });
      setLedger((current) => prepend(current, added));
      return added;
    },
    [productId],
  );

  return {
    card,
    ledger,
    failed,
    loadingMore,
    moreFailed,
    loadMore,
    add,
    reload: () => {
      setFailed(false);
      setAttempt((count) => count + 1);
    },
  };
}
