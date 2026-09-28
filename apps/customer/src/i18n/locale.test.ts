import { describe, expect, it } from "vitest";

import { resolveLocale, translator } from "./locale";

describe("resolveLocale", () => {
  it.each([
    [["es-MX", "en-US"], "es"],
    [["es-419"], "es"],
    [["pt-BR"], "pt-BR"],
    [["pt-PT"], "pt-BR"],
    [["fr-FR", "pt-BR", "es-CO"], "pt-BR"],
    [["en-GB"], "en"],
    [["fr-FR", "de-DE"], "en"],
    [[], "en"],
  ] as const)("picks the first supported language of %j", (preferred, expected) => {
    expect(resolveLocale(preferred)).toBe(expected);
  });
});

describe("translator", () => {
  it("fills placeholders in the chosen language", () => {
    expect(translator("es")("verify.description", { email: "ana@example.com" })).toBe(
      "Ingresa el código que enviamos a ana@example.com.",
    );
  });
});
