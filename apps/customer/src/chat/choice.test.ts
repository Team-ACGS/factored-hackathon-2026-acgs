import { describe, expect, it } from "vitest";

import { choice, type ChatMessage } from "./conversation";

const asked = { messageId: "m-002" } as ChatMessage;
const yes = { id: "yes", label: "Sí, fui yo" };

describe("an answer chosen in the bar", () => {
  it("carries the customer's note in the tap and shows it under the option", () => {
    expect(choice(asked, yes, "  era la gasolina del viaje ")).toEqual([
      "Sí, fui yo\nera la gasolina del viaje",
      { ask_id: "m-002", option: "yes", note: "era la gasolina del viaje" },
    ]);
  });

  it("sends no note when the field was left empty", () => {
    expect(choice(asked, yes, "   ")).toEqual(["Sí, fui yo", { ask_id: "m-002", option: "yes" }]);
  });
});
