import { ClaraEntity } from "@clara/ui/components/clara-entity";
import { cn } from "@clara/ui/lib/cn";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Suspense } from "react";

import { isOpen } from "../bank/cases";
import { LedgersOf } from "../bank/ledgers-of";
import { bankQueries } from "../bank/services";
import { useI18n } from "../i18n";
import { useOpenClara } from "./entry";
import { Launcher } from "./launcher";
import { flaggedCharges } from "./overlay";
import { launcher, useLauncherOpen } from "./store";

export function ClaraWidget() {
  return (
    <Suspense fallback={null}>
      <Widget />
    </Suspense>
  );
}

function Widget() {
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const claim = useQuery(bankQueries.cases()).data?.find((item) => item.type === "claim" && isOpen(item));
  const open = useLauncherOpen();
  const openClara = useOpenClara();

  return (
    <LedgersOf productIds={cards.map((card) => card.product_id)}>
      {(ledgers) => {
        const flagged = flaggedCharges(ledgers.flat(), cards);
        return (
          <>
            <Fab unread={flagged.length} launched={open} onOpen={launcher.open} />
            {open && (
              <Launcher
                note={flagged[0]}
                claim={claim}
                onClosed={launcher.close}
                onTopic={openClara}
              />
            )}
          </>
        );
      }}
    </LedgersOf>
  );
}

function Fab({ unread, launched, onOpen }: { unread: number; launched: boolean; onOpen: () => void }) {
  const { t } = useI18n();
  return (
    <>
      <button
        type="button"
        onClick={onOpen}
        data-unread={unread > 0 || undefined}
        aria-label={unread > 0 ? t("clara.openUnread", { count: String(unread) }) : t("clara.open")}
        className={cn(
          "clara-fab peer fixed right-3 bottom-[calc(14px+env(safe-area-inset-bottom))] z-[45] size-[88px] rounded-full outline-none hover:scale-[1.07] focus-visible:ring-[3px] focus-visible:ring-ring/40 min-[561px]:right-[18px]",
          launched && "pointer-events-none scale-[0.4] opacity-0",
        )}
      >
        <ClaraEntity state={unread > 0 ? "confirma" : "orden"} motion="idle" className="absolute inset-0 size-full" />
        {unread > 0 && (
          <span className="absolute top-2.5 right-2.5 z-[2] grid h-[22px] min-w-[22px] place-items-center rounded-full bg-badge px-1.5 text-xs font-bold text-white shadow-[0_0_0_3px_var(--background)]">
            {unread}
          </span>
        )}
      </button>
      <span
        aria-hidden
        className="pointer-events-none fixed right-[112px] bottom-[calc(46px+env(safe-area-inset-bottom))] z-[44] translate-x-1 rounded-full bg-ink px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap text-white opacity-0 transition-[opacity,translate] duration-200 peer-hover:translate-x-0 peer-hover:opacity-100 peer-focus-visible:translate-x-0 peer-focus-visible:opacity-100"
      >
        {t("clara.tip")}
      </span>
    </>
  );
}
