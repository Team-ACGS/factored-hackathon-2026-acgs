import { en, type MessageKey } from "./en";
import { es } from "./es";
import { ptBR } from "./pt-BR";

export const locales = ["en", "es", "pt-BR"] as const;
export type Locale = (typeof locales)[number];

export const languageNames: Record<Locale, string> = {
  en: "English",
  es: "Español",
  "pt-BR": "Português (Brasil)",
};

const catalogs: Record<Locale, Record<MessageKey, string>> = { en, es, "pt-BR": ptBR };

export function isMessageKey(key: string): key is MessageKey {
  return key in en;
}

export function isLocale(value: unknown): value is Locale {
  return locales.includes(value as Locale);
}

export function resolveLocale(preferred: readonly string[]): Locale {
  for (const tag of preferred) {
    const language = tag.toLowerCase().split("-")[0];
    if (language === "es") return "es";
    if (language === "pt") return "pt-BR";
    if (language === "en") return "en";
  }
  return "en";
}

export type Translate = (key: MessageKey, values?: Record<string, string>) => string;

export function translator(locale: Locale): Translate {
  const catalog = catalogs[locale];
  return (key, values = {}) => catalog[key].replace(/\{(\w+)\}/g, (match, name: string) => values[name] ?? match);
}
