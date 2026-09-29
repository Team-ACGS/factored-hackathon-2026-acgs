import { Link } from "@tanstack/react-router";

import { useI18n } from "../i18n";
import { CardFace } from "./card-face";
import type { Card } from "./types";

export function CardsPage({ cards }: { cards: Card[] }) {
  const { t } = useI18n();

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
        <h2 className="text-lg font-semibold">{t("cards.title")}</h2>
        {cards.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted-foreground">{t("cards.empty")}</p>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {cards.map((card) => (
              <li key={card.product_id}>
                <Link
                  to="/cards/$productId"
                  params={{ productId: card.product_id }}
                  search={{}}
                  className="block rounded-xl outline-none transition-shadow hover:shadow-md focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                  <CardFace card={card} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
