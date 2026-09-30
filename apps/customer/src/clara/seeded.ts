import type { QueryClient } from "@tanstack/react-query";

import { ensureLedgerUntil } from "../bank/queries";
import { bankQueries } from "../bank/services";
import type { Profile } from "../bank/types";
import { findSeededClaim, seededCard } from "./claims";
import { claraSession } from "./store";

export async function resolveSeededClaim(queryClient: QueryClient, profile: Profile): Promise<void> {
  if (claraSession.current().seeded !== undefined) return;
  const card = seededCard(await queryClient.ensureQueryData(bankQueries.cards()));
  if (!card) return;
  const entries = await ensureLedgerUntil(
    queryClient,
    bankQueries.ledger(card.product_id),
    (loaded) => findSeededClaim(card, loaded, profile.country) !== null,
  );
  claraSession.resolveSeeded(findSeededClaim(card, entries, profile.country));
}
