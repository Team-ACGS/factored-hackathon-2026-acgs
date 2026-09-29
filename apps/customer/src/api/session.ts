import { fetchAuthSession } from "aws-amplify/auth";

import { config } from "../config";
import { createClock } from "../chat/clock";
import { createHttp } from "./http";

async function idToken(): Promise<string> {
  const token = (await fetchAuthSession()).tokens?.idToken?.toString();
  if (!token) throw new Error("not signed in");
  return token;
}

export async function tokenLocale(): Promise<string | undefined> {
  const locale = (await fetchAuthSession()).tokens?.idToken?.payload.locale;
  return typeof locale === "string" ? locale : undefined;
}

export const http = createHttp({ baseUrl: config.apiUrl, token: idToken });

export const clock = createClock();
