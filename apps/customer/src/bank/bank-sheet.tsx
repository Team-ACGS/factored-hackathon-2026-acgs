import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { useI18n } from "../i18n";

interface BankSheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function BankSheet({ open, onClose, children }: BankSheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="bank-scrim fixed inset-0 z-50 animate-fade bg-[rgb(14_24_21/0.34)]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="bank-sheet fixed inset-x-0 bottom-0 z-[60] flex max-h-[90%] animate-sheet-up flex-col rounded-t-[20px] bg-surface pt-[env(safe-area-inset-top)] shadow-bank-lg outline-none min-[561px]:inset-x-auto min-[561px]:top-0 min-[561px]:right-0 min-[561px]:max-h-none min-[561px]:w-[min(440px,100%)] min-[561px]:animate-sheet-right min-[561px]:rounded-none"
        >
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function SheetHead({ title, subtitle }: { title: ReactNode; subtitle: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex items-start justify-between gap-3 px-[22px] pt-[22px] pb-2">
      <div className="min-w-0">
        <Dialog.Title className="text-xl font-semibold">{title}</Dialog.Title>
        <p className="text-[13.5px] text-ink-3 first-letter:uppercase">{subtitle}</p>
      </div>
      <Dialog.Close className="grid size-[38px] shrink-0 place-items-center rounded-full bg-muted text-ink transition-colors hover:bg-line">
        <X className="size-[18px]" aria-hidden />
        <span className="sr-only">{t("transaction.close")}</span>
      </Dialog.Close>
    </div>
  );
}

export function SheetBody({ children }: { children: ReactNode }) {
  return <div className="grid flex-1 content-start gap-[22px] overflow-y-auto px-[22px] pt-2 pb-[22px]">{children}</div>;
}

export function SheetFoot({ children }: { children: ReactNode }) {
  return (
    <div className="grid gap-2.5 border-t border-line px-[22px] pt-4 pb-[calc(16px+env(safe-area-inset-bottom))]">{children}</div>
  );
}

export function Facts({ rows }: { rows: readonly (readonly [string, ReactNode])[] }) {
  return (
    <dl className="grid rounded-xl bg-muted px-3.5 py-1">
      {rows
        .filter(([, value]) => value !== null && value !== "")
        .map(([term, value]) => (
          <div key={term} className="flex justify-between gap-4 py-2.5 text-sm [&+&]:border-t [&+&]:border-line">
            <dt className="text-ink-3">{term}</dt>
            <dd className="min-w-0 text-right [overflow-wrap:anywhere]">{value}</dd>
          </div>
        ))}
    </dl>
  );
}
