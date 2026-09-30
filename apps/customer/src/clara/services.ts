import { bankQueries } from "../bank/services";
import { claraChat } from "./chat/services";
import { createSeededResolver } from "./seeded";
import { claraSession } from "./store";

export const resolveSeededClaim = createSeededResolver(bankQueries, claraSession);

export function resetClaraDemo() {
  claraSession.resetDemo();
  claraChat.reset();
}

export function forgetClara() {
  claraSession.clear();
  claraChat.reset();
}
