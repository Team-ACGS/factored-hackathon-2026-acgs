import { createRootRoute, createRoute, createRouter, Navigate, Outlet, redirect } from "@tanstack/react-router";
import { getCurrentUser } from "aws-amplify/auth";

import { SignInPage } from "./auth/sign-in-page";
import { SignUpPage } from "./auth/sign-up-page";
import { VerifyPage } from "./auth/verify-page";
import { ChatPage } from "./chat/chat-page";

async function signedInCustomer(): Promise<string | null> {
  try {
    return (await getCurrentUser()).userId;
  } catch {
    return null;
  }
}

async function onlySignedOut() {
  if (await signedInCustomer()) throw redirect({ to: "/" });
}

const rootRoute = createRootRoute({ component: Outlet });

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: async () => {
    const customerId = await signedInCustomer();
    if (!customerId) throw redirect({ to: "/sign-in" });
    return { customerId };
  },
  component: function Chat() {
    const { customerId } = chatRoute.useRouteContext();
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
  routeTree: rootRoute.addChildren([chatRoute, signInRoute, signUpRoute, verifyRoute]),
  defaultNotFoundComponent: () => <Navigate to="/" />,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
