import { ClaraEntity } from "@clara/ui/components/clara-entity";
import { cn } from "@clara/ui/lib/cn";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronRight, Phone } from "lucide-react";

import { launcher } from "../clara/store";
import { useI18n } from "../i18n";
import { brand } from "./brand";
import { primaryPillButton } from "./buttons";
import { CaseSheet } from "./case-sheet";
import { isOpen, stepOf } from "./cases";
import { formatMoney } from "./format";
import { chargeOf, useRow } from "./rows";
import { bankQueries } from "./services";
import type { Case } from "./types";

const panel = "grid content-start gap-2.5 rounded-2xl bg-surface p-5 shadow-bank";

export function HelpPage({ claimId }: { claimId: string | undefined }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: cases } = useSuspenseQuery(bankQueries.cases());
  const claims = cases.filter(isOpen);

  return (
    <div className="grid gap-9">
      <h1 className="text-[clamp(28px,4.6vw,36px)] leading-[1.1] font-semibold tracking-tight">{t("help.title")}</h1>

      <section className="grid gap-3.5" aria-labelledby="help-claims">
        <h2 id="help-claims" className="text-lg font-semibold">
          {t("help.claims")}
        </h2>
        <div className="overflow-hidden rounded-2xl bg-surface shadow-bank">
          {claims.length === 0 ? (
            <p className="px-4 py-9 text-center text-ink-3">{t("help.noClaims")}</p>
          ) : (
            claims.map((item) => <CaseRow key={item.complaint_id} item={item} />)
          )}
        </div>
      </section>

      <section className="grid gap-3.5" aria-labelledby="help-need">
        <h2 id="help-need" className="text-lg font-semibold">
          {t("help.need")}
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
          <div className={panel}>
            <ClaraEntity state="hola" motion="idle" className="-mt-1.5 -mb-1 -ml-1.5 size-16" />
            <h3 className="font-semibold">{t("help.claraTitle")}</h3>
            <p className="text-ink-2">{t("help.claraText")}</p>
            <button type="button" className={cn(primaryPillButton, "justify-self-start")} onClick={launcher.open}>
              {t("help.talkToClara")}
            </button>
          </div>
          <div className={panel}>
            <span className="grid size-10 place-items-center rounded-full bg-muted text-ink" aria-hidden>
              <Phone className="size-[18px]" />
            </span>
            <h3 className="font-semibold">{t("help.phoneTitle", { bank: brand.name })}</h3>
            <p className="text-ink-2">{t("help.phoneText")}</p>
            <span className="font-mono text-[17px] select-all">{brand.phone}</span>
          </div>
        </div>
      </section>

      <CaseSheet
        item={cases.find((item) => item.case_id === claimId)}
        onClose={() => void navigate({ to: "/help", search: {}, replace: true })}
      />
    </div>
  );
}

function CaseRow({ item }: { item: Case }) {
  const { locale, t } = useI18n();
  const charge = useRow(chargeOf(item));
  return (
    <Link
      to="/help"
      search={{ claim: item.case_id }}
      className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-[18px] py-4 text-left outline-none transition-colors hover:bg-muted focus-visible:bg-muted [&+&]:border-t [&+&]:border-line"
    >
      <span className="grid min-w-0 gap-0.5">
        <span className="font-semibold">
          {charge ? (
            <>
              {t("claim.title", { merchant: charge.merchant_name })} ·{" "}
              <span className="tabular-nums">{formatMoney(charge.amount, charge.currency, locale)}</span>
            </>
          ) : (
            t(`case.type.${item.type}`)
          )}
        </span>
        <span className="text-[13.5px] text-ink-2">{t(`claim.status.${stepOf(item)}`)}</span>
        <span className="font-mono text-[12.5px] text-ink-3">{item.case_id}</span>
      </span>
      <ChevronRight className="size-[18px] text-ink-3" aria-hidden />
    </Link>
  );
}
