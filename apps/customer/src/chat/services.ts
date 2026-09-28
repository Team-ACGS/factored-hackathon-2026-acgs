import { fetchAuthSession } from "aws-amplify/auth";

import { config } from "../config";
import { createApi } from "./api";
import { createClock } from "./clock";

async function idToken(): Promise<string> {
  const token = (await fetchAuthSession()).tokens?.idToken?.toString();
  if (!token) throw new Error("not signed in");
  return token;
}

export const api = createApi({ baseUrl: config.apiUrl, token: idToken });
export const clock = createClock();
