import type { Locale } from "../i18n/locale";

const wholeCurrencies = new Set(["COP"]);

const currencyRegions: Record<string, string> = { MXN: "MX", PEN: "PE", COP: "CO", ARS: "AR", USD: "US", BRL: "BR" };

export function formatMoney(amount: string, currency: string, locale: Locale): string {
  const whole = wholeCurrencies.has(currency);
  const region = currencyRegions[currency];
  const language = locale.split("-")[0] ?? locale;
  return new Intl.NumberFormat(region ? `${language}-${region}` : locale, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(Number(amount));
}

export function lastDigits(productNumber: string): string {
  return productNumber.slice(-4);
}
