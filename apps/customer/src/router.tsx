import { createRootRoute, createRoute, createRouter, Navigate, Outlet, redirect } from "@tanstack/react-router";
import { getCurrentUser } from "aws-amplify/auth";

import { AppLayout, RetryPage } from "./app/app-layout";
import { tokenLocale } from "./api/session";
import { SignInPage } from "./auth/sign-in-page";
import { SignUpPage } from "./auth/sign-up-page";
import { VerifyPage } from "./auth/verify-page";
import { CardPage } from "./bank/card-page";
import { CardsPage } from "./bank/cards-page";
import { bank } from "./bank/services";
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

async function onlySignedOut() {
  if (await signedInCustomer()) throw redirect({ to: "/" });
  localeStore.set(localeStore.signedOut());
}

const rootRoute = createRootRoute({ component: Outlet });

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async () => {
    const customerId = await signedInCustomer();
    if (!customerId) throw redirect({ to: "/sign-in" });
    return { customerId };
  },
  loader: async () => {
    const profile = await bank.profile();
    const fromToken = await tokenLocale();
    const language = profile.language ?? (isLocale(fromToken) ? fromToken : null);
    if (language) localeStore.set(language);
    return { profile };
  },
  errorComponent: RetryPage,
  component: function App() {
    const { profile } = appRoute.useLoaderData();
    return <AppLayout profile={profile} />;
  },
});

const cardsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  loader: () => bank.cards(),
  errorComponent: RetryPage,
  component: function Cards() {
    return <CardsPage cards={cardsRoute.useLoaderData()} />;
  },
});

const cardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/cards/$productId",
  validateSearch: (search: Record<string, unknown>): { transaction?: string } =>
    typeof search.transaction === "string" ? { transaction: search.transaction } : {},
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
  beforeLoad: async ({ search }) => {
    await onlySignedOut();
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
  defaultNotFoundComponent: () => <Navigate to="/" />,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
