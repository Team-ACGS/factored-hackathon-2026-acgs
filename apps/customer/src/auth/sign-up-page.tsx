import { Button } from "@clara/ui/components/button";
import { Link, useNavigate } from "@tanstack/react-router";
import { signUp } from "aws-amplify/auth";
import { useState, type FormEvent } from "react";

import { useI18n } from "../i18n";
import { AuthCard } from "./auth-card";
import { authErrorKey } from "./errors";
import { Field, FormError } from "./field";

export function SignUpPage() {
  const { locale, t } = useI18n();
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
      await signUp({
        username: email,
        password,
        options: { userAttributes: { email, locale }, autoSignIn: true },
      });
      await navigate({ to: "/verify", search: { email } });
    } catch (caught) {
      setError(t(authErrorKey(caught)));
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title={t("signUp.title")}
      description={t("signUp.description")}
      footer={
        <>
          {t("signUp.haveAccount")}
          <Link to="/sign-in" className="font-medium text-foreground underline-offset-4 hover:underline">
            {t("signUp.toSignIn")}
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
          hint={t("auth.passwordHint")}
          type="password"
          autoComplete="new-password"
          minLength={10}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <FormError message={error} />
        <Button type="submit" disabled={busy} className="w-full">
          {t("signUp.submit")}
        </Button>
      </form>
    </AuthCard>
  );
}
