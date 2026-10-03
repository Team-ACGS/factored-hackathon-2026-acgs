import type { Http } from "../api/http";
import type { Card, CardPage, Case, Country, NewTransaction, Profile, Setup, Transaction } from "./types";
import type { Locale } from "../i18n/locale";

export function createBankApi(http: Http) {
  const card = (productId: string) => `/crud/cards/${encodeURIComponent(productId)}`;

  return {
    async profile(): Promise<Profile> {
      return ((await http.request("GET", "/crud/profile")) as { profile: Profile }).profile;
    },

    async setup(country: Country, language: Locale): Promise<Setup> {
      return (await http.request("POST", "/crud/profile/setup", { country, language })) as Setup;
    },

    async cards(): Promise<Card[]> {
      return ((await http.request("GET", "/crud/cards")) as { cards: Card[] }).cards;
    },

    async cases(): Promise<Case[]> {
      return ((await http.request("GET", "/crud/cases")) as { cases: Case[] }).cases;
    },

    async card(productId: string, cursor: string | null = null): Promise<CardPage> {
      const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
      return (await http.request("GET", `${card(productId)}${query}`)) as CardPage;
    },

    async transaction(productId: string, transactionId: string): Promise<Transaction> {
      const path = `${card(productId)}/transactions/${encodeURIComponent(transactionId)}`;
      return ((await http.request("GET", path)) as { transaction: Transaction }).transaction;
    },

    async add(productId: string, transaction: NewTransaction): Promise<Transaction> {
      const body = await http.request("POST", `${card(productId)}/transactions`, transaction);
      return (body as { transaction: Transaction }).transaction;
    },
  };
}

export type BankApi = ReturnType<typeof createBankApi>;
