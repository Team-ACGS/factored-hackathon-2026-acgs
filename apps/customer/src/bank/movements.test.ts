import { describe, expect, it } from "vitest";

import { cardAt, purchase } from "../clara/fixtures";
import type { PendingTransaction } from "./ledger";
import { daysBetween, groupByDay, matches, recentMovements } from "./movements";

const card = cardAt("Tarjeta Crédito");
const at = (iso: string, merchant_name = "OXXO") => purchase(card, 0, { transaction_date: iso, merchant_name });
const adding: PendingTransaction = { transaction_id: "new", transaction_date: "2026-09-29T12:00:00.000Z", pending: true };

describe("movement filters", () => {
  const pending = purchase(card, 1, { transaction_status: "Pending", merchant_name: "Hotel Fiesta Americana" });
  const reversed = purchase(card, 2, { transaction_status: "Reversed", merchant_name: "Liverpool en línea" });

  it("keeps only the chosen status", () => {
    expect([pending, reversed].filter((entry) => matches(entry, "Reversed", ""))).toEqual([reversed]);
  });

  it("searches merchants ignoring case and surrounding spaces", () => {
    expect([pending, reversed].filter((entry) => matches(entry, "all", "  hotel "))).toEqual([pending]);
  });

  it("shows a purchase being added only when nothing narrows the list", () => {
    expect(matches(adding, "all", "")).toBe(true);
    expect(matches(adding, "Pending", "")).toBe(false);
    expect(matches(adding, "all", "oxxo")).toBe(false);
  });
});

describe("groupByDay", () => {
  it("groups by the customer's local day, not the UTC day", () => {
    const late = at("2026-09-28T03:12:00.000Z");
    const evening = at("2026-09-27T23:40:00.000Z");
    const morning = at("2026-09-27T14:05:00.000Z");

    const groups = groupByDay([late, evening, morning], "America/Mexico_City");

    expect(groups.map((group) => [group.day, group.entries.length])).toEqual([["2026-09-27", 3]]);
    expect(groupByDay([late, evening, morning], "UTC").map((group) => group.day)).toEqual(["2026-09-28", "2026-09-27"]);
  });

  it("counts calendar days between two days", () => {
    expect(daysBetween("2026-09-28", "2026-09-29")).toBe(1);
    expect(daysBetween("2026-02-28", "2026-03-01")).toBe(1);
  });
});

describe("recentMovements", () => {
  it("merges the newest movements of every card", () => {
    const debit = cardAt("Tarjeta Débito");
    const a = at("2026-09-28T10:00:00.000Z");
    const b = purchase(debit, 0, { transaction_date: "2026-09-28T12:00:00.000Z" });
    const c = at("2026-09-20T10:00:00.000Z");

    expect(recentMovements([[adding, a, c], [b]], 3)).toEqual([adding, b, a]);
  });
});
