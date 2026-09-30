import { Button } from "@clara/ui/components/button";
import { Link, Outlet, useLocation, useNavigate, useRouter } from "@tanstack/react-router";
import { signOut } from "aws-amplify/auth";
import { CreditCard, Loader2, LogOut, MessageCircle } from "lucide-react";

import { SetupFlow } from "../bank/setup-flow";
import type { Profile } from "../bank/types";
import { useI18n } from "../i18n";

export function AppLayout({ profile }: { profile: Profile }) {
  const { t } = useI18n();
  const router = useRouter();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onChat = pathname.startsWith("/chat");

  async function leave() {
    await signOut();
    router.clearCache();
    await navigate({ to: "/sign-in" });
  }

  return (
    <div className="flex h-dvh flex-col bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <div className="min-w-0">
            <h1 className="text-base font-semibold">Clara</h1>
            <p className="truncate text-xs text-muted-foreground">{t("app.subtitle")}</p>
          </div>
          <nav className="flex items-center gap-1">
            <Button asChild variant={onChat ? "ghost" : "outline"} size="sm">
              <Link to="/" aria-current={onChat ? undefined : "page"}>
                <CreditCard />
                {t("app.cards")}
              </Link>
            </Button>
            <Button asChild variant={onChat ? "outline" : "ghost"} size="sm">
              <Link to="/chat" aria-current={onChat ? "page" : undefined}>
                <MessageCircle />
                {t("app.chat")}
              </Link>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void leave()} aria-label={t("app.signOut")}>
              <LogOut />
              <span className="hidden sm:inline">{t("app.signOut")}</span>
            </Button>
          </nav>
        </div>
      </header>
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
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
