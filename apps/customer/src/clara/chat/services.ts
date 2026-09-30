import { clock, queryClient } from "../../api/session";
import { brand } from "../../bank/brand";
import { bankQueries } from "../../bank/services";
import { localeStore } from "../../i18n";
import { translator } from "../../i18n/locale";
import { claraSession } from "../store";
import { createMockChat } from "./engine";
import { createSnapshotLoader } from "./snapshot";

export const claraChat = createMockChat({
  load: createSnapshotLoader(queryClient, bankQueries, () => clock.now()),
  session: claraSession,
  t: () => translator(localeStore.current()),
  locale: () => localeStore.current(),
  now: () => clock.now(),
  wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  bank: brand.name,
});
