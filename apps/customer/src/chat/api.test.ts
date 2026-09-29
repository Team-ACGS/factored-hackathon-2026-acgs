import { describe, expect, it, vi } from "vitest";

import { ApiError, createHttp } from "../api/http";
import { createChatApi } from "./api";

const stored = {
  room_id: "r",
  message_id: "m",
  sender_type: "customer",
  text: "hola",
  sent_at: "2026-09-27T20:00:00.000Z",
  created_at: "2026-09-27T20:00:00.100Z",
};

function respond(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), { status });
}

function api(fetch: typeof globalThis.fetch) {
  return createChatApi(
    createHttp({ baseUrl: "https://api.test", token: () => Promise.resolve("id-token"), fetch, sleep: () => Promise.resolve() }),
  );
}

describe("api.send", () => {
  it("retries a failed send with the same message id until it is confirmed", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce(respond(503))
      .mockResolvedValueOnce(respond(200, { message: stored }));

    const message = await api(fetch).send({ room_id: "r", message_id: "m", text: "hola" });

    expect(message).toEqual(stored);
    const bodies = fetch.mock.calls.map(([, init]) => JSON.parse(init?.body as string) as unknown);
    expect(bodies).toEqual(Array(3).fill({ room_id: "r", message_id: "m", text: "hola" }));
    expect(fetch.mock.calls[0]?.[1]?.headers).toMatchObject({ Authorization: "id-token" });
  });

  it("does not retry a rejected message", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(respond(400));

    await expect(api(fetch).send({ room_id: "r", message_id: "m", text: "hola" })).rejects.toEqual(new ApiError(400));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("gives up after the last retry", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(() => Promise.resolve(respond(500)));

    await expect(api(fetch).send({ room_id: "r", message_id: "m", text: "hola" })).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledTimes(4);
  });
});
