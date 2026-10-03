import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { bankQueries } from "./services";
import type { Case, Transaction } from "./types";

export interface RowRef {
  product_id: string;
  transaction_id: string;
}

export function useRow(ref: RowRef | null): Transaction | undefined {
  const queryClient = useQueryClient();
  const options = bankQueries.row(queryClient, ref?.product_id ?? "", ref?.transaction_id ?? "");
  return useQuery({ ...options, enabled: ref !== null }).data;
}

export function useRows(refs: readonly RowRef[]): (Transaction | undefined)[] {
  const queryClient = useQueryClient();
  return useQueries({
    queries: refs.map((ref) => bankQueries.row(queryClient, ref.product_id, ref.transaction_id)),
  }).map((result) => result.data);
}

export function chargeOf(item: Pick<Case, "product_id" | "transaction_id">): RowRef | null {
  return item.product_id && item.transaction_id
    ? { product_id: item.product_id, transaction_id: item.transaction_id }
    : null;
}
