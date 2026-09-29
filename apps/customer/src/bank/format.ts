import type { Locale } from "../i18n/locale";

const wholeCurrencies = new Set(["COP"]);

export function formatMoney(amount: string, currency: string, locale: Locale): string {
  const whole = wholeCurrencies.has(currency);
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(Number(amount));
}

export function formatExpiration(date: string): string {
  const [year, month] = date.split("-");
  return `${month}/${year?.slice(2)}`;
}

export function lastDigits(productNumber: string): string {
  return productNumber.slice(-4);
}
