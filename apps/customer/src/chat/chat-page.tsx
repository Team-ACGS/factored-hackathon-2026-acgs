import { Button } from "@clara/ui/components/button";
import { Input } from "@clara/ui/components/input";
import { cn } from "@clara/ui/lib/cn";
import { useNavigate } from "@tanstack/react-router";
import { signOut } from "aws-amplify/auth";
import { AlertCircle, Check, Clock, LogOut, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { locale, t } from "../i18n";
import type { ChatMessage } from "./conversation";
import { useChat } from "./use-chat";

const MAX_TEXT_LENGTH = 2000;
const timeFormat = new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit" });

export function ChatPage({ customerId }: { customerId: string }) {
  const navigate = useNavigate();
  const chat = useChat(customerId);
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [chat.messages.length]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    void chat.send(text);
  }

  async function leave() {
    await signOut();
    await navigate({ to: "/sign-in" });
  }

  return (
    <div className="flex h-dvh flex-col bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-base font-semibold">Clara</h1>
            <p className="text-xs text-muted-foreground">{t("chat.subtitle")}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void leave()}>
            <LogOut />
            {t("chat.signOut")}
          </Button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-2xl flex-col gap-3 px-4 py-6" aria-live="polite">
          {chat.problem === "load" ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center text-sm text-muted-foreground">
              <p>{t("chat.loadFailed")}</p>
              <Button variant="outline" size="sm" onClick={chat.reload}>
                {t("chat.reload")}
              </Button>
            </div>
          ) : !chat.loaded ? (
            <p className="py-16 text-center text-sm text-muted-foreground">{t("chat.loading")}</p>
          ) : chat.messages.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted-foreground">{t("chat.empty")}</p>
          ) : (
            chat.messages.map((message) => (
              <Bubble key={message.messageId} message={message} onRetry={() => void chat.retry(message)} />
            ))
          )}
          <div ref={end} />
        </div>
      </main>

      <footer className="border-t bg-background">
        {chat.problem === "live" && (
          <p role="status" className="mx-auto max-w-2xl px-4 pt-3 text-xs text-muted-foreground">
            {t("chat.liveUpdatesLost")}
          </p>
        )}
        <form className="mx-auto flex max-w-2xl gap-2 px-4 py-3" onSubmit={submit}>
          <Input
            aria-label={t("chat.placeholder")}
            placeholder={t("chat.placeholder")}
            autoComplete="off"
            maxLength={MAX_TEXT_LENGTH}
            disabled={!chat.loaded}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <Button type="submit" size="icon" aria-label={t("chat.send")} disabled={!chat.loaded || !draft.trim()}>
            <SendHorizontal />
          </Button>
        </form>
      </footer>
    </div>
  );
}

function Bubble({ message, onRetry }: { message: ChatMessage; onRetry: () => void }) {
  const mine = message.senderType === "customer";
  const time = timeFormat.format(new Date(message.createdAt ?? message.sentAt));

  return (
    <div className={cn("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <p
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap break-words",
          mine ? "rounded-br-sm bg-primary text-primary-foreground" : "rounded-bl-sm border bg-background",
        )}
      >
        {message.text}
      </p>
      <div className="flex items-center gap-1 px-1 text-[11px] text-muted-foreground">
        <time dateTime={message.createdAt ?? message.sentAt}>{time}</time>
        {mine && <DeliveryMark message={message} onRetry={onRetry} />}
      </div>
    </div>
  );
}

function DeliveryMark({ message, onRetry }: { message: ChatMessage; onRetry: () => void }) {
  if (message.delivery === "pending") {
    return <Clock className="size-3" aria-label={t("chat.pending")} role="img" />;
  }
  if (message.delivery === "sent") {
    return <Check className="size-3" aria-label={t("chat.sent")} role="img" />;
  }
  return (
    <span className="flex items-center gap-1 text-destructive">
      <AlertCircle className="size-3" aria-hidden />
      {t("chat.failed")}
      <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" onClick={onRetry}>
        {t("chat.retry")}
      </Button>
    </span>
  );
}
