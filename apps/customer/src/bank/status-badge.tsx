import { Badge } from "@clara/ui/components/badge";

import { useI18n } from "../i18n";
import { statusVariants } from "./labels";
import type { TransactionStatus } from "./types";

export function StatusBadge({ status }: { status: TransactionStatus }) {
  const { t } = useI18n();
  return <Badge variant={statusVariants[status]}>{t(`status.${status}`)}</Badge>;
}
