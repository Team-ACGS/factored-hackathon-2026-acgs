import { formatMoney } from "../../bank/format";
import type { Transaction } from "../../bank/types";
import { useI18n } from "../../i18n";

export function useMoney() {
  const { locale } = useI18n();
  return (item: Pick<Transaction, "amount" | "currency">) => formatMoney(item.amount, item.currency, locale);
}
