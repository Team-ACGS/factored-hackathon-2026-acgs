import { describe, expect, it } from "vitest";

import { formatMoney } from "../bank/format";
import { translator } from "../i18n/locale";
import { cardAt, purchase } from "./fixtures";
import { chargeTopic, topicMessage } from "./topics";

const charge = purchase(cardAt("Tarjeta Crédito"), 0, {
  merchant_name: "GLOBALPAY*DIGITALSVC",
  amount: "4780.00",
  transaction_date: "2026-09-28T09:12:00.000Z",
});

describe("topic messages", () => {
  it("names the charge the customer started from, in their language and currency", () => {
    expect(topicMessage(chargeTopic(charge), translator("es"), "es")).toBe(
      `No reconozco el cargo de GLOBALPAY*DIGITALSVC por ${formatMoney("4780.00", "MXN", "es")} del 28 de septiembre de 2026.`,
    );
  });

  it("names the merchant of the claim when there is one", () => {
    const t = translator("en");
    expect(topicMessage({ kind: "claim", claim_id: "CLR-2026-004217", merchant_name: "Cinemex" }, t, "en")).toBe(
      "How is my claim for Cinemex going?",
    );
    expect(topicMessage({ kind: "claim", claim_id: null, merchant_name: null }, t, "en")).toBe("How is my claim going?");
  });

  it("sends typed text as it was written", () => {
    expect(topicMessage({ kind: "text", text: "  hola Clara " }, translator("pt-BR"), "pt-BR")).toBe("  hola Clara ");
  });
});
