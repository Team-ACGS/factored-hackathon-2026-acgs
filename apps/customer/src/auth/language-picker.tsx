import { NativeSelect } from "@clara/ui/components/native-select";
import { Languages } from "lucide-react";

import { localeStore, useI18n } from "../i18n";
import { isLocale, languageNames, locales } from "../i18n/locale";

export function LanguagePicker() {
  const { locale, t } = useI18n();

  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <Languages className="size-4" aria-hidden />
      <span className="sr-only">{t("auth.language")}</span>
      <NativeSelect
        className="w-44"
        value={locale}
        onChange={(event) => {
          if (isLocale(event.target.value)) localeStore.chooseSignedOut(event.target.value);
        }}
      >
        {locales.map((option) => (
          <option key={option} value={option}>
            {languageNames[option]}
          </option>
        ))}
      </NativeSelect>
    </label>
  );
}
