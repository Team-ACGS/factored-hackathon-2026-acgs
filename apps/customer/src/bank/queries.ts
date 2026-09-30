import { infiniteQueryOptions, queryOptions, type MutationOptions, type QueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/http";
import { minutes, seconds } from "../api/query-client";
import { idTime, type Clock } from "../chat/clock";
import type { Locale } from "../i18n/locale";
import type { BankApi } from "./api";
import { withAdded, withoutPlaceholder, withPlaceholder, type Ledger, type LedgerPage } from "./ledger";
import type { Country, NewTransaction, Setup, Transaction } from "./types";

export const bankKeys = {
  profile: () => ["bank", "profile"] as const,
  cards: () => ["bank", "cards"] as const,
  ledger: (productId: string) => ["bank", "ledger", productId] as const,
  transaction: (productId: string, transactionId: string) => ["bank", "transaction", productId, transactionId] as const,
  add: (productId: string) => ["bank", "add", productId] as const,
};

export function isSetupConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

export function createBankQueries(bank: BankApi, clock: Clock) {
  return {
    profile: () => queryOptions({ queryKey: bankKeys.profile(), queryFn: () => bank.profile(), staleTime: minutes(5) }),

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

    transaction: (productId: string, transactionId: string) =>
      queryOptions({
        queryKey: bankKeys.transaction(productId, transactionId),
        queryFn: () => bank.transaction(productId, transactionId),
        staleTime: seconds(30),
      }),

    setup: (queryClient: QueryClient): MutationOptions<Setup, Error, { country: Country; language: Locale }> => {
      const refresh = () => {
        void queryClient.invalidateQueries({ queryKey: bankKeys.profile() });
        void queryClient.invalidateQueries({ queryKey: bankKeys.cards() });
      };
      return {
        mutationFn: ({ country, language }) => bank.setup(country, language),
        onSuccess: refresh,
        onError: (error) => {
          if (isSetupConflict(error)) refresh();
        },
      };
    },

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
        },
      };
    },
  };
}

export type BankQueries = ReturnType<typeof createBankQueries>;
