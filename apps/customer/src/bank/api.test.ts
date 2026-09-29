import { describe, expect, it, vi } from "vitest";

import { ApiError, createHttp } from "../api/http";
import { createBankApi } from "./api";

function respond(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), { status });
}

function bank(fetch: typeof globalThis.fetch) {
  return createBankApi(
    createHttp({ baseUrl: "https://api.test", token: () => Promise.resolve("id-token"), fetch, sleep: () => Promise.resolve() }),
  );
}

describe("bank api", () => {
  it("asks for the next page with the opaque cursor escaped", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(respond(200, { transactions: [] }));

    await bank(fetch).card("card-1", "a+b/c==");

    expect(fetch.mock.calls[0]?.[0]).toBe("https://api.test/crud/cards/card-1?cursor=a%2Bb%2Fc%3D%3D");
  });

  it("surfaces a completed setup as a conflict without retrying", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(respond(409));

    await expect(bank(fetch).setup("MX", "es")).rejects.toEqual(new ApiError(409));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetch.mock.calls[0]?.[1]?.body as string)).toEqual({ country: "MX", language: "es" });
  });

  it("retries an add with the same transaction id", async () => {
    const added = { transaction_id: "t-1" };
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(respond(502))
      .mockResolvedValueOnce(respond(201, { transaction: added }));

    const transaction = await bank(fetch).add("card-1", { transaction_id: "t-1", kind: "suspicious", score: "none" });

    expect(transaction).toEqual(added);
    const bodies = fetch.mock.calls.map(([, init]) => JSON.parse(init?.body as string) as unknown);
    expect(bodies).toEqual(Array(2).fill({ transaction_id: "t-1", kind: "suspicious", score: "none" }));
  });
});
