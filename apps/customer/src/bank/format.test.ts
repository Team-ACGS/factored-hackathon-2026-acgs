import { describe, expect, it } from "vitest";

import { formatExpiration, formatMoney } from "./format";
import { guessCountry } from "./labels";

describe("formatMoney", () => {
  it.each([
    ["235700.00", "COP", "es", "235.700"],
    ["1063.50", "MXN", "es", "1063,50"],
    ["57.48", "USD", "en", "$57.48"],
    ["310.39", "BRL", "pt-BR", "310,39"],
  ] as const)("shows %s %s the way %s customers read it", (amount, currency, locale, expected) => {
    expect(formatMoney(amount, currency, locale)).toContain(expected);
  });
});

describe("formatExpiration", () => {
  it("shows month and two digit year", () => {
    expect(formatExpiration("2029-08-31")).toBe("08/29");
  });
});

describe("guessCountry", () => {
  it.each([
    [["es-CO", "en-US"], "CO"],
    [["pt-BR"], "BR"],
    [["es-ES", "es-AR"], "AR"],
    [["fr-FR"], "US"],
    [[], "US"],
  ] as const)("picks the first supported region of %j", (languages, expected) => {
    expect(guessCountry(languages)).toBe(expected);
  });
});
