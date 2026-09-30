import { Button } from "@clara/ui/components/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@clara/ui/components/dialog";
import { cn } from "@clara/ui/lib/cn";
import { useState, type FormEvent } from "react";

import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";
import type { ScoreOption } from "./types";

const options: { value: ScoreOption; label: MessageKey; hint: MessageKey }[] = [
  { value: "flagged", label: "suspicious.flagged", hint: "suspicious.flaggedHint" },
  { value: "missed", label: "suspicious.missed", hint: "suspicious.missedHint" },
  { value: "none", label: "suspicious.none", hint: "suspicious.noneHint" },
];

interface SuspiciousDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (score: ScoreOption) => void;
}

export function SuspiciousDialog({ open, onOpenChange, onSubmit }: SuspiciousDialogProps) {
  const { t } = useI18n();
  const [score, setScore] = useState<ScoreOption>("missed");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(score);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t("transaction.close")} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("suspicious.title")}</DialogTitle>
          <DialogDescription>{t("suspicious.description")}</DialogDescription>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={submit}>
          <fieldset className="grid gap-2">
            <legend className="sr-only">{t("suspicious.title")}</legend>
            {options.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50",
                  score === option.value && "border-primary bg-muted/50",
                )}
              >
                <input
                  type="radio"
                  name="score"
                  value={option.value}
                  checked={score === option.value}
                  onChange={() => setScore(option.value)}
                  className="mt-0.5 size-4 accent-primary"
                />
                <span className="grid gap-0.5">
                  <span className="text-sm font-medium">{t(option.label)}</span>
                  <span className="text-xs text-muted-foreground">{t(option.hint)}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("suspicious.cancel")}
            </Button>
            <Button type="submit">
              {t("suspicious.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
