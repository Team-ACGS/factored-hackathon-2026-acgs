import { useSuspenseQuery, type QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, createRoute, createRouter, Navigate, Outlet, redirect } from "@tanstack/react-router";
import { getCurrentUser } from "aws-amplify/auth";

import { AppLayout, PendingPage, RetryPage } from "./app/app-layout";
import { applyProfileLanguage } from "./app/profile-language";
import { queryClient } from "./api/session";
import { SignInPage } from "./auth/sign-in-page";
import { SignUpPage } from "./auth/sign-up-page";
import { VerifyPage } from "./auth/verify-page";
import { CardPage } from "./bank/card-page";
import { HelpPage } from "./bank/help-page";
import { HomePage } from "./bank/home-page";
import { bankQueries } from "./bank/services";
import { ClaraChatPage } from "./clara/chat/chat-page";
import { forgetClara, resolveSeededClaim } from "./clara/services";
import { claraSession } from "./clara/store";
import { localeStore } from "./i18n";

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
  forgetClara();
  localeStore.set(localeStore.signedOut());
}

const rootRoute = createRootRouteWithContext<RouterContext>()({ component: Outlet });

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async () => {
    const customerId = await signedInCustomer();
    if (!customerId) throw redirect({ to: "/sign-in" });
    claraSession.open(customerId);
    return { customerId };
  },
  loader: async ({ context }) => {
    const profile = await context.queryClient.ensureQueryData(bankQueries.profile());
    await Promise.all([applyProfileLanguage(profile), resolveSeededClaim(context.queryClient, profile)]);
  },
  errorComponent: RetryPage,
  component: function App() {
    const { data: profile } = useSuspenseQuery(bankQueries.profile());
    return <AppLayout profile={profile} />;
  },
});

function transactionSearch(search: Record<string, unknown>): { transaction?: string } {
  return typeof search.transaction === "string" ? { transaction: search.transaction } : {};
}

const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  validateSearch: (search: Record<string, unknown>): { card?: string; transaction?: string } =>
    typeof search.card === "string" ? { card: search.card, ...transactionSearch(search) } : {},
  loaderDeps: ({ search }) => ({ card: search.card, transaction: search.transaction }),
  loader: async ({ context, deps: { card, transaction } }) => {
    if (card && transaction) void context.queryClient.prefetchQuery(bankQueries.transaction(card, transaction));
    const cards = await context.queryClient.ensureQueryData(bankQueries.cards());
    await Promise.all(cards.map((item) => context.queryClient.ensureInfiniteQueryData(bankQueries.ledger(item.product_id))));
  },
  errorComponent: RetryPage,
  component: function Home() {
    const { card, transaction } = homeRoute.useSearch();
    return <HomePage productId={card} transactionId={transaction} />;
  },
});

const cardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/cards/$productId",
  validateSearch: transactionSearch,
  loaderDeps: ({ search }) => ({ transaction: search.transaction }),
  loader: async ({ context, params: { productId }, deps: { transaction } }) => {
    if (transaction) void context.queryClient.prefetchQuery(bankQueries.transaction(productId, transaction));
    await Promise.all([
      context.queryClient.ensureQueryData(bankQueries.cards()),
      context.queryClient.ensureInfiniteQueryData(bankQueries.ledger(productId)),
    ]);
  },
  errorComponent: RetryPage,
  component: function Card() {
    const { productId } = cardRoute.useParams();
    const { transaction } = cardRoute.useSearch();
    return <CardPage key={productId} productId={productId} transactionId={transaction} />;
  },
});

const helpRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/help",
  validateSearch: (search: Record<string, unknown>): { claim?: string } =>
    typeof search.claim === "string" ? { claim: search.claim } : {},
  component: function Help() {
    const { claim } = helpRoute.useSearch();
    return <HelpPage claimId={claim} />;
  },
});

const chatRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/chat",
  component: function Chat() {
    const { customerId } = appRoute.useRouteContext();
    return <ClaraChatPage customerId={customerId} />;
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
    appRoute.addChildren([homeRoute, cardRoute, helpRoute, chatRoute]),
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
