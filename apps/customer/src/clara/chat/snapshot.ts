import type { QueryClient } from "@tanstack/react-query";

import { isPending } from "../../bank/ledger";
import { ensureLedgerUntil, type BankQueries } from "../../bank/queries";
import type { Transaction } from "../../bank/types";
import { DAY_MS, HISTORY_DAYS, type Snapshot } from "./insight";

export function createSnapshotLoader(queryClient: QueryClient, queries: BankQueries, now: () => number) {
  return async (): Promise<Snapshot> => {
    const [profile, cards] = await Promise.all([
      queryClient.ensureQueryData(queries.profile()),
      queryClient.ensureQueryData(queries.cards()),
    ]);
    const since = new Date(now() - HISTORY_DAYS * DAY_MS).toISOString();
    const ledgers = await Promise.all(
      cards.map((card) =>
        ensureLedgerUntil(queryClient, queries.ledger(card.product_id), (entries) =>
          entries.some((entry) => entry.transaction_date < since),
        ),
      ),
    );
    return {
      profile,
      cards,
      entries: ledgers.flat().filter((entry): entry is Transaction => !isPending(entry)),
    };
  };
}
