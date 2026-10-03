import { cn } from "@clara/ui/lib/cn";
import { Check } from "lucide-react";

import { useOpenClara } from "../clara/entry";
import { useI18n } from "../i18n";
import { BankSheet, SheetBody, SheetFoot, SheetHead } from "./bank-sheet";
import { pillButton } from "./buttons";
import { stepsOf } from "./cases";
import { formatMoney } from "./format";
import { chargeOf, useRow } from "./rows";
import type { Case } from "./types";

export function CaseSheet({ item, onClose }: { item: Case | undefined; onClose: () => void }) {
  return (
    <BankSheet open={item !== undefined} onClose={onClose}>
      {item && <CaseDetails item={item} />}
    </BankSheet>
  );
}

function CaseDetails({ item }: { item: Case }) {
  const { locale, t } = useI18n();
  const openClara = useOpenClara();
  const charge = useRow(chargeOf(item));
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });

  return (
    <>
      <SheetHead
        title={charge ? t("claim.title", { merchant: charge.merchant_name }) : t(`case.type.${item.type}`)}
        subtitle={<span className="font-mono">{item.case_id}</span>}
      />
      <SheetBody>
        {charge && (
          <span className="text-[34px] font-semibold tracking-tight tabular-nums">
            {formatMoney(charge.amount, charge.currency, locale)}
          </span>
        )}
        <ol className="grid">
          {stepsOf(item).map(({ step, state, at }) => (
            <li
              key={step}
              className="relative grid grid-cols-[22px_1fr] gap-3 pb-[18px] last:pb-0 before:absolute before:top-5 before:bottom-0 before:left-2.5 before:w-0.5 before:bg-line last:before:hidden"
            >
              <span
                className={cn(
                  "relative grid size-[22px] place-items-center rounded-full border-2 border-line bg-surface",
                  state === "done" && "border-primary bg-primary text-primary-foreground",
                  state === "now" && "border-primary",
                )}
              >
                {state === "done" && <Check className="size-3" strokeWidth={3} aria-hidden />}
                {state === "now" && <span className="size-2 rounded-full bg-primary" />}
              </span>
              <span>
                <b className="block text-sm font-semibold">{t(`claim.stage.${step}`)}</b>
                {at && (
                  <span className="text-[13px] text-ink-3">
                    {state === "now" && step !== "opened"
                      ? t("claim.since", { date: day.format(new Date(at)) })
                      : day.format(new Date(at))}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>
        <p className="text-[13px] text-ink-3">{t("claim.fine")}</p>
      </SheetBody>
      <SheetFoot>
        <button
          type="button"
          className={cn(pillButton, "w-full")}
          onClick={() => openClara({ kind: "claim", claim_id: item.case_id, merchant_name: charge?.merchant_name ?? null })}
        >
          {t("claim.askClara")}
        </button>
      </SheetFoot>
    </>
  );
}
