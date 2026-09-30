import { tokenLocale } from "../api/session";
import type { Profile } from "../bank/types";
import { localeStore } from "../i18n";
import { isLocale } from "../i18n/locale";

export async function applyProfileLanguage(profile: Profile): Promise<void> {
  const fromToken = profile.language ? undefined : await tokenLocale();
  const language = profile.language ?? (isLocale(fromToken) ? fromToken : null);
  if (language) localeStore.set(language);
}
