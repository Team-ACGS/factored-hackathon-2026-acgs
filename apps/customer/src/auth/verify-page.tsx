import { Button } from "@clara/ui/components/button";
import { useNavigate } from "@tanstack/react-router";
import { autoSignIn, confirmSignUp, resendSignUpCode } from "aws-amplify/auth";
import { useState, type FormEvent } from "react";

import { t } from "../i18n";
import { AuthCard } from "./auth-card";
import { authErrorKey } from "./errors";
import { Field, FormError } from "./field";

export function VerifyPage({ email }: { email: string }) {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { nextStep } = await confirmSignUp({ username: email, confirmationCode: code.trim() });
      if (nextStep.signUpStep === "COMPLETE_AUTO_SIGN_IN") {
        await autoSignIn();
        await navigate({ to: "/" });
        return;
      }
      await navigate({ to: "/sign-in" });
    } catch (caught) {
      setError(t(authErrorKey(caught)));
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      await resendSignUpCode({ username: email });
      setNotice(t("verify.resent"));
    } catch (caught) {
      setError(t(authErrorKey(caught)));
    }
  }

  return (
    <AuthCard title={t("verify.title")} description={t("verify.description", { email })}>
      <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
        <Field
          label={t("verify.code")}
          inputMode="numeric"
          autoComplete="one-time-code"
          required
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <FormError message={error} />
        {notice && (
          <p role="status" className="text-sm text-muted-foreground">
            {notice}
          </p>
        )}
        <Button type="submit" disabled={busy} className="w-full">
          {t("verify.submit")}
        </Button>
        <Button type="button" variant="link" onClick={() => void resend()}>
          {t("verify.resend")}
        </Button>
      </form>
    </AuthCard>
  );
}
