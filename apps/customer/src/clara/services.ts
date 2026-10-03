import { bankQueries } from "../bank/services";
import { createSeededResolver } from "./seeded";
import { claraSession } from "./store";

export const resolveSeededClaim = createSeededResolver(bankQueries, claraSession);

export function forgetClara() {
  claraSession.clear();
}
