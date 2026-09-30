import { Button } from "@clara/ui/components/button";
import { cn } from "@clara/ui/lib/cn";
import { Link, Outlet, useLocation, useNavigate, useRouter } from "@tanstack/react-router";
import { signOut } from "aws-amplify/auth";
import { Loader2, LogOut } from "lucide-react";

import { brand } from "../bank/brand";
import { SetupFlow } from "../bank/setup-flow";
import type { Profile } from "../bank/types";
import { ClaraWidget } from "../clara/widget";
import { useI18n } from "../i18n";
import { DemoFooter } from "./demo-footer";

const navClass =
  "flex h-9 items-center rounded-full px-3 text-sm font-semibold whitespace-nowrap text-ink-2 hover:bg-muted hover:text-ink aria-[current=page]:bg-muted aria-[current=page]:text-ink";

export function AppLayout({ profile }: { profile: Profile }) {
  const { t } = useI18n();
  const router = useRouter();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onChat = pathname.startsWith("/chat");
  const onHelp = pathname.startsWith("/help");

  async function leave() {
    await signOut();
    router.clearCache();
    await navigate({ to: "/sign-in" });
  }

  return (
    <div className={cn("flex min-h-dvh flex-col bg-background", onChat && "h-dvh")}>
      <header className={cn("w-full flex-none border-b border-line bg-surface px-4", onChat && "min-[901px]:px-5")}>
        <div className={cn("mx-auto flex h-[72px] items-center justify-between gap-4", !onChat && "max-w-[960px]")}>
          <div className="flex min-w-0 items-center gap-3 sm:gap-7">
            <Link to="/" className="flex items-center gap-2 text-base font-bold tracking-[0.01em] whitespace-nowrap">
              <span className="brand-mark size-6 rounded-[7px]" aria-hidden />
              {brand.name}
            </Link>
            <nav className="flex gap-1" aria-label={t("nav.label")}>
              <Link to="/" className={navClass} aria-current={!onHelp && !onChat ? "page" : undefined}>
                {t("nav.home")}
              </Link>
              <Link to="/help" className={navClass} aria-current={onHelp ? "page" : undefined}>
                <span className="hidden sm:inline">{t("nav.help")}</span>
                <span className="sm:hidden">{t("nav.helpShort")}</span>
              </Link>
            </nav>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="rounded-full text-ink-2"
            onClick={() => void leave()}
            aria-label={t("app.signOut")}
          >
            <LogOut />
            <span className="hidden sm:inline">{t("app.signOut")}</span>
          </Button>
        </div>
      </header>
      {onChat ? (
        <main className="min-h-0 flex-1">
          <Outlet />
        </main>
      ) : (
        <>
          <main className="mx-auto w-full max-w-[992px] flex-1 px-4 pt-7 pb-12">
            <Outlet />
          </main>
          <DemoFooter />
          <ClaraWidget />
        </>
      )}
      <SetupFlow profile={profile} />
    </div>
  );
}

export function RetryPage() {
  const { t } = useI18n();
  const router = useRouter();
  return (
    <div className="flex h-full min-h-40 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
      <p>{t("app.loadFailed")}</p>
      <Button variant="outline" size="sm" onClick={() => void router.invalidate()}>
        {t("app.retry")}
      </Button>
    </div>
  );
}

export function PendingPage() {
  return (
    <div className="flex h-full min-h-40 items-center justify-center">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden />
    </div>
  );
}
