import { Button } from "@clara/ui/components/button";
import { Link, useNavigate } from "@tanstack/react-router";
import { resendSignUpCode, signIn } from "aws-amplify/auth";
import { useState, type FormEvent } from "react";

import { t } from "../i18n";
import { AuthCard } from "./auth-card";
import { authErrorKey } from "./errors";
import { Field, FormError } from "./field";

export function SignInPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { nextStep } = await signIn({ username: email, password });
      if (nextStep.signInStep === "CONFIRM_SIGN_UP") {
        await resendSignUpCode({ username: email });
        await navigate({ to: "/verify", search: { email } });
        return;
      }
      if (nextStep.signInStep !== "DONE") throw new Error(nextStep.signInStep);
      await navigate({ to: "/" });
    } catch (caught) {
      setError(t(authErrorKey(caught)));
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title={t("signIn.title")}
      description={t("signIn.description")}
      footer={
        <>
          {t("signIn.noAccount")}
          <Link to="/sign-up" className="font-medium text-foreground underline-offset-4 hover:underline">
            {t("signIn.toSignUp")}
          </Link>
        </>
      }
    >
      <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
        <Field
          label={t("auth.email")}
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Field
          label={t("auth.password")}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <FormError message={error} />
        <Button type="submit" disabled={busy} className="w-full">
          {t("signIn.submit")}
        </Button>
      </form>
    </AuthCard>
  );
}
