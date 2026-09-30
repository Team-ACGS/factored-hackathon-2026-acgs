import { describe, expect, it } from "vitest";

import { cardAt, purchase } from "../fixtures";
import { intentOf, mentionedMovement, polarity } from "./lexicon";

describe("typed answers", () => {
  it.each(["Sí, es ese", "sí", "Yes", "it was me", "Sim, fui eu", "bloquéala", "Block it", "ábrela", "la tengo"])(
    "reads %s as yes",
    (text) => expect(polarity(text)).toBe(true),
  );

  it.each(["no fui yo", "No, es otro", "It wasn't me", "not now", "Ahora no", "não fui eu", "I don't have it"])(
    "reads %s as no",
    (text) => expect(polarity(text)).toBe(false),
  );

  it("does not guess on anything else", () => {
    expect(polarity("¿qué es esto?")).toBeNull();
  });
});

describe("free text", () => {
  it.each([
    ["Quiero ver mis tarjetas", "cards"],
    ["how is my claim going", "claims"],
    ["Me robaron la tarjeta", "protect"],
    ["Não reconheço uma cobrança", "charge"],
    ["hola", null],
  ])("routes %s", (text, intent) => expect(intentOf(text)).toBe(intent));

  it("finds the movement the customer names by merchant or by amount", () => {
    const card = cardAt("Tarjeta Crédito");
    const hotel = purchase(card, 1, { merchant_name: "Hotel Fiesta Americana", amount: "3500.00" });
    const spotify = purchase(card, 2, { merchant_name: "SPOTIFY", amount: "129.00" });

    expect(mentionedMovement("¿qué es lo del hotel fiesta?", [spotify, hotel])).toBe(hotel);
    expect(mentionedMovement("un cargo de $129", [spotify, hotel])).toBe(spotify);
    expect(mentionedMovement("un cargo raro", [spotify, hotel])).toBeUndefined();
  });
});
