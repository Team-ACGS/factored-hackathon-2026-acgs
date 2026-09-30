import { useSuspenseQuery, type QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, createRoute, createRouter, Navigate, Outlet, redirect } from "@tanstack/react-router";
import { getCurrentUser } from "aws-amplify/auth";

import { AppLayout, PendingPage, RetryPage } from "./app/app-layout";
import { queryClient, tokenLocale } from "./api/session";
import { SignInPage } from "./auth/sign-in-page";
import { SignUpPage } from "./auth/sign-up-page";
import { VerifyPage } from "./auth/verify-page";
import { CardPage } from "./bank/card-page";
import { CardsPage } from "./bank/cards-page";
import { bankQueries } from "./bank/services";
import { ChatPage } from "./chat/chat-page";
import { localeStore } from "./i18n";
import { isLocale } from "./i18n/locale";

async function signedInCustomer(): Promise<string | null> {
  try {
    return (await getCurrentUser()).userId;
  } catch {
    return null;
  }
}

interface RouterContext {
  queryClient: QueryClient;
}

async function onlySignedOut({ context }: { context: RouterContext }) {
  if (await signedInCustomer()) throw redirect({ to: "/" });
  context.queryClient.clear();
  localeStore.set(localeStore.signedOut());
}

const rootRoute = createRootRouteWithContext<RouterContext>()({ component: Outlet });

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async () => {
    const customerId = await signedInCustomer();
    if (!customerId) throw redirect({ to: "/sign-in" });
    return { customerId };
  },
  loader: async ({ context }) => {
    const profile = await context.queryClient.ensureQueryData(bankQueries.profile());
    const fromToken = await tokenLocale();
    const language = profile.language ?? (isLocale(fromToken) ? fromToken : null);
    if (language) localeStore.set(language);
  },
  errorComponent: RetryPage,
  component: function App() {
    const { data: profile } = useSuspenseQuery(bankQueries.profile());
    return <AppLayout profile={profile} />;
  },
});

const cardsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  loader: async ({ context }) => {
    await context.queryClient.ensureQueryData(bankQueries.cards());
  },
  errorComponent: RetryPage,
  component: function Cards() {
    const { data: cards } = useSuspenseQuery(bankQueries.cards());
    return <CardsPage cards={cards} />;
  },
});

const cardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/cards/$productId",
  validateSearch: (search: Record<string, unknown>): { transaction?: string } =>
    typeof search.transaction === "string" ? { transaction: search.transaction } : {},
  loaderDeps: ({ search }) => ({ transaction: search.transaction }),
  loader: async ({ context, params: { productId }, deps: { transaction } }) => {
    if (transaction) void context.queryClient.prefetchQuery(bankQueries.transaction(productId, transaction));
    await context.queryClient.ensureInfiniteQueryData(bankQueries.ledger(productId));
  },
  errorComponent: RetryPage,
  component: function Card() {
    const { productId } = cardRoute.useParams();
    const { transaction } = cardRoute.useSearch();
    return <CardPage key={productId} productId={productId} transactionId={transaction} />;
  },
});

const chatRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/chat",
  component: function Chat() {
    const { customerId } = appRoute.useRouteContext();
    return <ChatPage customerId={customerId} />;
  },
});

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sign-in",
  beforeLoad: onlySignedOut,
  component: SignInPage,
});

const signUpRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sign-up",
  beforeLoad: onlySignedOut,
  component: SignUpPage,
});

const verifyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/verify",
  validateSearch: (search: Record<string, unknown>) => ({
    email: typeof search.email === "string" ? search.email : "",
  }),
  beforeLoad: async ({ context, search }) => {
    await onlySignedOut({ context });
    if (!search.email) throw redirect({ to: "/sign-up" });
  },
  component: function Verify() {
    const { email } = verifyRoute.useSearch();
    return <VerifyPage email={email} />;
  },
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    appRoute.addChildren([cardsRoute, cardRoute, chatRoute]),
    signInRoute,
    signUpRoute,
    verifyRoute,
  ]),
  context: { queryClient },
  defaultPreload: "intent",
  defaultPreloadStaleTime: 0,
  defaultPendingComponent: PendingPage,
  defaultNotFoundComponent: () => <Navigate to="/" />,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
