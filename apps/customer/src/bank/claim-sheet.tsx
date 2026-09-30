import { cn } from "@clara/ui/lib/cn";
import { Check } from "lucide-react";

import { useNow } from "../app/use-now";
import { claimSteps, type Claim } from "../clara/claims";
import { useOpenClara } from "../clara/entry";
import { useI18n } from "../i18n";
import { BankSheet, SheetBody, SheetFoot, SheetHead } from "./bank-sheet";
import { pillButton } from "./buttons";
import { formatMoney } from "./format";

export function ClaimSheet({ claim, onClose }: { claim: Claim | undefined; onClose: () => void }) {
  return (
    <BankSheet open={claim !== undefined} onClose={onClose}>
      {claim && <ClaimDetails claim={claim} />}
    </BankSheet>
  );
}

function ClaimDetails({ claim }: { claim: Claim }) {
  const { locale, t } = useI18n();
  const openClara = useOpenClara();
  const now = useNow();
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });

  return (
    <>
      <SheetHead
        title={t("claim.title", { merchant: claim.merchant_name })}
        subtitle={<span className="font-mono">{claim.claim_id}</span>}
      />
      <SheetBody>
        <span className="text-[34px] font-semibold tracking-tight tabular-nums">
          {formatMoney(claim.amount, claim.currency, locale)}
        </span>
        <ol className="grid">
          {claimSteps(claim, now).map((step) => {
            const date = day.format(new Date(step.at));
            return (
              <li
                key={step.stage}
                className="relative grid grid-cols-[22px_1fr] gap-3 pb-[18px] last:pb-0 before:absolute before:top-5 before:bottom-0 before:left-2.5 before:w-0.5 before:bg-line last:before:hidden"
              >
                <span
                  className={cn(
                    "relative grid size-[22px] place-items-center rounded-full border-2 border-line bg-surface",
                    step.state === "done" && "border-primary bg-primary text-primary-foreground",
                    step.state === "now" && "border-primary",
                  )}
                >
                  {step.state === "done" && <Check className="size-3" strokeWidth={3} aria-hidden />}
                  {step.state === "now" && <span className="size-2 rounded-full bg-primary" />}
                </span>
                <span>
                  <b className="block text-sm font-semibold">{t(`claim.stage.${step.stage}`)}</b>
                  {step.state !== "todo" && (
                    <span className="text-[13px] text-ink-3">
                      {step.state === "now" && step.stage !== "opened" ? t("claim.since", { date }) : date}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
        <p className="text-[13px] text-ink-3">{t("claim.fine")}</p>
      </SheetBody>
      <SheetFoot>
        <button
          type="button"
          className={cn(pillButton, "w-full")}
          onClick={() => openClara({ kind: "claim", claim_id: claim.claim_id, merchant_name: claim.merchant_name })}
        >
          {t("claim.askClara")}
        </button>
      </SheetFoot>
    </>
  );
}
