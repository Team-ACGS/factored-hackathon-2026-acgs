import { resolveLocale, translator } from "./locale";

export const locale = resolveLocale(navigator.languages.length > 0 ? navigator.languages : [navigator.language]);
export const t = translator(locale);
