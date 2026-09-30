import { QueryClient } from "@tanstack/react-query";

export const minutes = (count: number) => count * 60_000;
export const seconds = (count: number) => count * 1_000;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: minutes(60) },
      mutations: { retry: false },
    },
  });
}
