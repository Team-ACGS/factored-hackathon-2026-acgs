import { lastDigits } from "../../bank/format";
import { cardTypeKey } from "../../bank/labels";
import type { Card } from "../../bank/types";
import type { Translate } from "../../i18n/locale";
import type { Segment } from "./state";

export function rich(text: string): Segment[] {
  return text
    .split("**")
    .map((part, index) => (index % 2 === 1 ? { text: part, strong: true } : { text: part }))
    .filter((segment) => segment.text !== "");
}

export function wordCount(segments: readonly Segment[]): number {
  return segments.reduce((count, segment) => count + (segment.text.match(/\S+/g)?.length ?? 0), 0);
}

export function revealed(segments: readonly Segment[], shown: number): Segment[] {
  const out: Segment[] = [];
  let left = shown;
  for (const segment of segments) {
    if (left <= 0) break;
    const parts = segment.text.split(/(\s+)/);
    let text = "";
    for (const part of parts) {
      if (part.trim() === "") {
        text += part;
        continue;
      }
      if (left <= 0) break;
      text += part;
      left -= 1;
    }
    out.push({ ...segment, text: left <= 0 ? text.trimEnd() : text });
  }
  return out;
}

export function plain(segments: readonly Segment[]): string {
  return segments.map((segment) => segment.text).join("");
}

export function sameDay(a: number, b: number): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString();
}

export function whenText(iso: string, now: number, locale: string, t: Translate): string {
  const at = Date.parse(iso);
  const time = new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(at);
  if (sameDay(at, now)) return t("clara.when.today", { time });
  if (sameDay(at, now - 86_400_000)) return t("clara.when.yesterday", { time });
  return t("clara.when.on", {
    date: new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(at),
    time,
  });
}

export function hourText(hour: number, locale: string): string {
  return new Intl.DateTimeFormat(locale, { hour: "numeric" }).format(new Date(2026, 0, 1, hour % 24));
}

export function cardLabel(card: Card, t: Translate): string {
  return `${t(cardTypeKey(card))} •••• ${lastDigits(card.product_number)}`;
}
