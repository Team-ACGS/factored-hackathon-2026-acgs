import { useQueryClient, useSuspenseInfiniteQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { entriesOf, type LedgerEntry } from "./ledger";
import { bankQueries } from "./services";

type Render = (ledgers: LedgerEntry[][]) => ReactNode;

export function LedgersOf({ productIds, children }: { productIds: readonly string[]; children: Render }) {
  const queryClient = useQueryClient();
  for (const productId of productIds) {
    const options = bankQueries.ledger(productId);
    if (!queryClient.getQueryState(options.queryKey)) void queryClient.prefetchInfiniteQuery(options);
  }
  return <Collect productIds={productIds} collected={[]} render={children} />;
}

interface CollectProps {
  productIds: readonly string[];
  collected: LedgerEntry[][];
  render: Render;
}

function Collect({ productIds, collected, render }: CollectProps) {
  const [first, ...rest] = productIds;
  if (first === undefined) return render(collected);
  return <Next productId={first} productIds={rest} collected={collected} render={render} />;
}

function Next({ productId, ...props }: CollectProps & { productId: string }) {
  const { data } = useSuspenseInfiniteQuery(bankQueries.ledger(productId));
  return <Collect {...props} collected={[...props.collected, entriesOf(data)]} />;
}
