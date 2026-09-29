export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`API answered ${status}`);
  }
}

export interface HttpOptions {
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

export function createHttp({
  baseUrl,
  token,
  fetch: send = (...args) => globalThis.fetch(...args),
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  retryDelays = defaultRetryDelays,
}: HttpOptions) {
  async function once(method: "GET" | "POST", path: string, body?: unknown): Promise<unknown> {
    const response = await send(`${baseUrl}${path}`, {
      method,
      headers: { Authorization: await token(), "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new ApiError(response.status);
    return response.json();
  }

  return {
    async request(method: "GET" | "POST", path: string, body?: unknown): Promise<unknown> {
      for (const delay of retryDelays) {
        try {
          return await once(method, path, body);
        } catch (error) {
          if (!retriable(error)) throw error;
          await sleep(delay);
        }
      }
      return once(method, path, body);
    },
  };
}

export type Http = ReturnType<typeof createHttp>;
