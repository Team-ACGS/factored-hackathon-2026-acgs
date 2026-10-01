import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { Suspense, useState } from "react";

import { clock } from "../api/session";
import { bankQueries } from "../bank/services";
import { SuspiciousDialog } from "../bank/suspicious-dialog";
import type { ScoreOption } from "../bank/types";
import { mintId } from "../chat/clock";
import { resetClaraDemo } from "../clara/services";
import { launcher } from "../clara/store";
import { useI18n } from "../i18n";

const linkClass = "text-[13px] text-ink-2 underline underline-offset-[3px] hover:text-ink disabled:opacity-50";

export function DemoFooter() {
  const { t } = useI18n();
  const navigate = useNavigate();

  function reset() {
    launcher.close();
    resetClaraDemo();
    void navigate({ to: "/" });
  }

  return (
    <footer className="mx-auto flex max-w-[992px] flex-wrap justify-between gap-4 px-4 pt-2 pb-[104px] text-[13px] text-ink-3">
      <span>{t("demo.note")}</span>
      <span className="flex flex-wrap gap-4">
        <Suspense fallback={null}>
          <AddLinks />
        </Suspense>
        <button type="button" className={linkClass} onClick={reset}>
          {t("demo.reset")}
        </button>
      </span>
    </footer>
  );
}

function AddLinks() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { productId: viewed } = useParams({ strict: false });
  const { data: cards } = useSuspenseQuery(bankQueries.cards());
  const productId = cards.find((card) => card.product_id === viewed)?.product_id ?? cards[0]?.product_id;
  const [suspiciousOpen, setSuspiciousOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const addition = useMutation(bankQueries.add(queryClient, productId ?? ""));

  if (!productId) return null;

  function add(request: { type: "normal" } | { type: "suspicious"; score: ScoreOption }) {
    setFailed(false);
    setSuspiciousOpen(false);
    addition.mutateAsync({ ...request, transaction_id: mintId(clock) }).catch(() => setFailed(true));
  }

  return (
    <>
      {failed && (
        <span role="alert" className="text-danger">
          {t("demo.addFailed")}
        </span>
      )}
      <button type="button" className={linkClass} onClick={() => add({ type: "normal" })}>
        {t("demo.addNormal")}
      </button>
      <button type="button" className={linkClass} onClick={() => setSuspiciousOpen(true)}>
        {t("demo.addSuspicious")}
      </button>
      <SuspiciousDialog
        open={suspiciousOpen}
        onOpenChange={setSuspiciousOpen}
        onSubmit={(score) => add({ type: "suspicious", score })}
      />
    </>
  );
}
