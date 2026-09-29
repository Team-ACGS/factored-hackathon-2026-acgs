import { useMemo, useSyncExternalStore } from "react";

import { translator, type Locale, type Translate } from "./locale";
import { createLocaleStore } from "./store";

export const localeStore = createLocaleStore(
  window.localStorage,
  navigator.languages.length > 0 ? navigator.languages : [navigator.language],
);

localeStore.subscribe(() => {
  document.documentElement.lang = localeStore.current();
});

export function useI18n(): { locale: Locale; t: Translate } {
  const locale = useSyncExternalStore(localeStore.subscribe, localeStore.current);
  const t = useMemo(() => translator(locale), [locale]);
  return { locale, t };
}
