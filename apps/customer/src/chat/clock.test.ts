import { describe, expect, it } from "vitest";

import { createClock, idTime, mintId } from "./clock";

describe("clock", () => {
  it("mints ids on server time even when the device clock is off", () => {
    const deviceSkew = -10 * 60_000;
    const serverNow = Date.parse("2026-09-27T20:00:00.000Z");
    const clock = createClock(() => serverNow + deviceSkew);

    clock.sync("2026-09-27T20:00:00.000Z", serverNow + deviceSkew - 100, serverNow + deviceSkew + 100);

    expect(Math.abs(idTime(mintId(clock)) - serverNow)).toBeLessThan(5);
  });

  it("reads the millisecond timestamp of a UUIDv7", () => {
    expect(idTime("0199a0b0-1234-7000-8000-000000000001")).toBe(0x0199a0b01234);
  });
});
