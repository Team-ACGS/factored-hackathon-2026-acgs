import type { QueryClient } from "@tanstack/react-query";

import { ensureLedgerUntil, type BankQueries } from "../bank/queries";
import type { Profile } from "../bank/types";
import { findSeededClaim, seededCard } from "./claims";
import type { ClaraSession } from "./session";

export function createSeededResolver(queries: BankQueries, session: ClaraSession) {
  async function resolve(queryClient: QueryClient, profile: Profile) {
    if (session.current().seeded !== undefined) return;
    const card = seededCard(await queryClient.ensureQueryData(queries.cards()));
    if (!card) return;
    const entries = await ensureLedgerUntil(
      queryClient,
      queries.ledger(card.product_id),
      (loaded) => findSeededClaim(card, loaded, profile.country) !== null,
    );
    session.resolveSeeded(findSeededClaim(card, entries, profile.country));
  }

  return (queryClient: QueryClient, profile: Profile): Promise<void> =>
    resolve(queryClient, profile).catch(() => undefined);
}
