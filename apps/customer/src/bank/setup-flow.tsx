import { Button } from "@clara/ui/components/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@clara/ui/components/dialog";
import { Label } from "@clara/ui/components/label";
import { NativeSelect } from "@clara/ui/components/native-select";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Loader2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { applyProfileLanguage } from "../app/profile-language";
import { FormError } from "../auth/field";
import { localeStore, useI18n } from "../i18n";
import { isLocale, languageNames, locales } from "../i18n/locale";
import { formatMoney } from "./format";
import { countryName, guessCountry } from "./labels";
import { bankQueries } from "./services";
import { StatusBadge } from "./status-badge";
import { countries, type Country, type PlantedCase, type Profile } from "./types";

const keepOpen = (event: Event) => event.preventDefault();

export function SetupFlow({ profile }: { profile: Profile }) {
  const [guide, setGuide] = useState<PlantedCase[] | null>(null);

  if (guide) return <PlantedCasesGuide cases={guide} onClose={() => setGuide(null)} />;
  if (profile.setup_completed) return null;
  return <SetupForm onCreated={setGuide} />;
}

function SetupForm({ onCreated }: { onCreated: (cases: PlantedCase[]) => void }) {
  const { locale, t } = useI18n();
  const queryClient = useQueryClient();
  const setup = useMutation(bankQueries.setup(queryClient));
  const countryId = useId();
  const languageId = useId();
  const [country, setCountry] = useState<Country>(() => guessCountry(navigator.languages));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const outcome = await setup.mutateAsync({ country, language: locale }).catch(() => null);
    if (!outcome) return;
    if (outcome.cases) onCreated(outcome.cases);
    await applyProfileLanguage(outcome.profile);
  }

  const busy = setup.isPending;
  const error = setup.isError ? t("errors.generic") : null;

  return (
    <Dialog open>
      <DialogContent onEscapeKeyDown={keepOpen} onInteractOutside={keepOpen} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("setup.title")}</DialogTitle>
          <DialogDescription>{t("setup.description")}</DialogDescription>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={(event) => void submit(event)}>
          <div className="grid gap-2">
            <Label htmlFor={countryId}>{t("setup.country")}</Label>
            <NativeSelect
              id={countryId}
              aria-describedby={`${countryId}-hint`}
              value={country}
              disabled={busy}
              onChange={(event) => setCountry(event.target.value as Country)}
            >
              {countries.map((code) => (
                <option key={code} value={code}>
                  {countryName(code, locale)}
                </option>
              ))}
            </NativeSelect>
            <p id={`${countryId}-hint`} className="text-xs text-muted-foreground">
              {t("setup.countryHint")}
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={languageId}>{t("setup.language")}</Label>
            <NativeSelect
              id={languageId}
              value={locale}
              disabled={busy}
              onChange={(event) => {
                if (isLocale(event.target.value)) localeStore.set(event.target.value);
              }}
            >
              {locales.map((option) => (
                <option key={option} value={option}>
                  {languageNames[option]}
                </option>
              ))}
            </NativeSelect>
          </div>
          <FormError message={error} />
          <DialogFooter>
            <Button type="submit" disabled={busy} className="w-full sm:w-auto">
              {busy && <Loader2 className="animate-spin" aria-hidden />}
              {busy ? t("setup.creating") : t("setup.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PlantedCasesGuide({ cases, onClose }: { cases: PlantedCase[]; onClose: () => void }) {
  const { locale, t } = useI18n();
  const dateFormat = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t("transaction.close")} className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("guide.title")}</DialogTitle>
          <DialogDescription>{t("guide.description")}</DialogDescription>
        </DialogHeader>
        <ol className="grid gap-3">
          {cases.map(({ kind, transaction }) => (
            <li key={kind} className="grid gap-2 rounded-lg border p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{t(`guide.${kind}`)}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {transaction.merchant_name} · {formatMoney(transaction.amount, transaction.currency, locale)} ·{" "}
                    {dateFormat.format(new Date(transaction.transaction_date))}
                  </p>
                </div>
                <StatusBadge status={transaction.transaction_status} />
              </div>
              <p className="text-sm">
                <span className="font-medium">{t("guide.clara")}: </span>
                {t(`guide.${kind}.clara`)}
              </p>
              <Button asChild variant="link" size="sm" className="h-auto justify-self-start p-0">
                <Link
                  to="/cards/$productId"
                  params={{ productId: transaction.product_id }}
                  search={{ transaction: transaction.transaction_id }}
                  onClick={onClose}
                >
                  {t("guide.view")}
                  <ArrowRight />
                </Link>
              </Button>
            </li>
          ))}
        </ol>
        <p className="text-sm text-muted-foreground">{t("guide.suspicious")}</p>
        <DialogFooter>
          <Button onClick={onClose}>{t("guide.done")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
