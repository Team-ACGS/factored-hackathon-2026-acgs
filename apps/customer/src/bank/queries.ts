import {
  InfiniteQueryObserver,
  infiniteQueryOptions,
  queryOptions,
  type MutationOptions,
  type QueryClient,
} from "@tanstack/react-query";

import { ApiError } from "../api/http";
import { minutes, seconds } from "../api/query-client";
import { idTime, type Clock } from "../chat/clock";
import type { Effect } from "../chat/conversation";
import type { Locale } from "../i18n/locale";
import type { BankApi } from "./api";
import {
  entriesOf,
  findTransaction,
  withAdded,
  withoutPlaceholder,
  withPlaceholder,
  type Ledger,
  type LedgerEntry,
  type LedgerPage,
} from "./ledger";
import type { Country, NewTransaction, PlantedCase, Profile, Transaction } from "./types";

export const bankKeys = {
  profile: () => ["bank", "profile"] as const,
  cards: () => ["bank", "cards"] as const,
  cases: () => ["bank", "cases"] as const,
  answered: () => ["bank", "answered"] as const,
  ledger: (productId: string) => ["bank", "ledger", productId] as const,
  transaction: (productId: string, transactionId: string) => ["bank", "transaction", productId, transactionId] as const,
  adds: () => ["bank", "add"] as const,
  add: (productId: string) => [...bankKeys.adds(), productId] as const,
};

export function invalidationsOf(effects: readonly Effect[]): (readonly string[])[] {
  return effects.flatMap((effect): (readonly string[])[] => {
    switch (effect.type) {
      case "card_blocked":
        return [bankKeys.cards(), bankKeys.ledger(effect.productId)];
      case "case_opened":
        return [bankKeys.cases()];
      case "charge_answered":
        return [bankKeys.answered()];
    }
  });
}

function isSetupConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

export interface SetupOutcome {
  profile: Profile;
  cases: PlantedCase[] | null;
}

export function createBankQueries(bank: BankApi, clock: Clock) {
  const profile = () =>
    queryOptions({ queryKey: bankKeys.profile(), queryFn: () => bank.profile(), staleTime: minutes(5) });

  return {
    profile,

    cards: () => queryOptions({ queryKey: bankKeys.cards(), queryFn: () => bank.cards(), staleTime: minutes(5) }),

    ledger: (productId: string) =>
      infiniteQueryOptions({
        queryKey: bankKeys.ledger(productId),
        queryFn: async ({ pageParam }): Promise<LedgerPage> => {
          const requestedAt = Date.now();
          const page = await bank.card(productId, pageParam);
          clock.sync(page.server_time, requestedAt, Date.now());
          return page;
        },
        initialPageParam: null as string | null,
        getNextPageParam: (page) => page.next_cursor,
        staleTime: seconds(30),
      }),

    cases: () => queryOptions({ queryKey: bankKeys.cases(), queryFn: () => bank.cases(), staleTime: seconds(30) }),
    answered: () =>
      queryOptions({ queryKey: bankKeys.answered(), queryFn: () => bank.answered(), staleTime: seconds(30) }),

    transaction: (productId: string, transactionId: string) =>
      queryOptions({
        queryKey: bankKeys.transaction(productId, transactionId),
        queryFn: () => bank.transaction(productId, transactionId),
        staleTime: seconds(30),
      }),

    row: (queryClient: QueryClient, productId: string, transactionId: string) =>
      queryOptions({
        queryKey: bankKeys.transaction(productId, transactionId),
        queryFn: () => bank.transaction(productId, transactionId),
        staleTime: seconds(30),
        initialData: () => findTransaction(entriesOf(queryClient.getQueryData<Ledger>(bankKeys.ledger(productId))), transactionId),
        initialDataUpdatedAt: () => queryClient.getQueryState(bankKeys.ledger(productId))?.dataUpdatedAt,
      }),

    setup: (queryClient: QueryClient): MutationOptions<SetupOutcome, Error, { country: Country; language: Locale }> => ({
      mutationFn: async ({ country, language }) => {
        try {
          return await bank.setup(country, language);
        } catch (error) {
          if (!isSetupConflict(error)) throw error;
          return { profile: await queryClient.fetchQuery({ ...profile(), staleTime: 0 }), cases: null };
        }
      },
      onSuccess: (outcome) => {
        queryClient.setQueryData(bankKeys.profile(), outcome.profile);
        void queryClient.invalidateQueries({ queryKey: bankKeys.cards() });
        void queryClient.invalidateQueries({ queryKey: bankKeys.cases() });
      },
    }),

    add: (queryClient: QueryClient, productId: string): MutationOptions<Transaction, Error, NewTransaction> => {
      const ledgerKey = bankKeys.ledger(productId);
      const update = (change: (ledger: Ledger | undefined) => Ledger | undefined) =>
        queryClient.setQueryData<Ledger>(ledgerKey, change);

      return {
        mutationKey: bankKeys.add(productId),
        mutationFn: (transaction) => bank.add(productId, transaction),
        onMutate: async ({ transaction_id }) => {
          await queryClient.cancelQueries({ queryKey: ledgerKey, exact: true });
          const transaction_date = new Date(idTime(transaction_id)).toISOString();
          update((ledger) => withPlaceholder(ledger, { transaction_id, transaction_date, pending: true }));
        },
        onSuccess: (added) => {
          update((ledger) => withAdded(ledger, added));
        },
        onError: (_error, { transaction_id }) => {
          update((ledger) => withoutPlaceholder(ledger, transaction_id));
        },
        onSettled: () => {
          if (queryClient.isMutating({ mutationKey: bankKeys.add(productId) }) === 1) {
            void queryClient.invalidateQueries({ queryKey: ledgerKey, exact: true });
          }
          if (queryClient.isMutating({ mutationKey: bankKeys.adds() }) === 1) {
            void queryClient.invalidateQueries({ queryKey: bankKeys.cards(), exact: true });
          }
        },
      };
    },
  };
}

export type BankQueries = ReturnType<typeof createBankQueries>;

export type LedgerOptions = ReturnType<BankQueries["ledger"]>;

export async function ensureLedgerUntil(
  queryClient: QueryClient,
  options: LedgerOptions,
  done: (entries: LedgerEntry[]) => boolean,
): Promise<LedgerEntry[]> {
  await queryClient.ensureInfiniteQueryData(options);
  const observer = new InfiniteQueryObserver(queryClient, options);
  let result = observer.getCurrentResult();
  while (!done(entriesOf(result.data)) && result.hasNextPage) {
    result = await observer.fetchNextPage();
    if (result.isFetchNextPageError) throw result.error;
  }
  return entriesOf(result.data);
}
