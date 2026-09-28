import { isServerMessage, type ServerMessage } from "./conversation";

export interface LatestRoom {
  room: { room_id: string; created_at: string } | null;
  messages: ServerMessage[];
  server_time: string;
}

export interface NewMessage {
  room_id: string;
  message_id: string;
  text: string;
}

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`API answered ${status}`);
  }
}

interface ApiOptions {
  baseUrl: string;
  token: () => Promise<string>;
  fetch?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  retryDelays?: readonly number[];
}

const defaultRetryDelays = [400, 1200, 3000];

function retriable(error: unknown): boolean {
  if (error instanceof ApiError) return error.status === 429 || error.status >= 500;
  return error instanceof TypeError;
}

export function createApi({
  baseUrl,
  token,
  fetch: send = (...args) => globalThis.fetch(...args),
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  retryDelays = defaultRetryDelays,
}: ApiOptions) {
  async function request(method: "GET" | "POST", path: string, body?: unknown): Promise<unknown> {
    const response = await send(`${baseUrl}${path}`, {
      method,
      headers: { Authorization: await token(), "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new ApiError(response.status);
    return response.json();
  }

  async function withRetries<T>(attempt: () => Promise<T>): Promise<T> {
    for (const delay of retryDelays) {
      try {
        return await attempt();
      } catch (error) {
        if (!retriable(error)) throw error;
        await sleep(delay);
      }
    }
    return attempt();
  }

  return {
    async latestRoom(): Promise<LatestRoom> {
      return (await withRetries(() => request("GET", "/messages/rooms/latest"))) as LatestRoom;
    },

    async send(message: NewMessage): Promise<ServerMessage> {
      const body = await withRetries(() => request("POST", "/messages", message));
      const stored = (body as { message?: unknown }).message;
      if (!isServerMessage(stored)) throw new ApiError(502);
      return stored;
    },
  };
}

export type Api = ReturnType<typeof createApi>;
