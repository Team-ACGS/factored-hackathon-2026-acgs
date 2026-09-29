import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@clara/ui/components/card";
import type { ReactNode } from "react";

import { LanguagePicker } from "./language-picker";

interface AuthCardProps {
  title: string;
  description: string;
  footer?: ReactNode;
  children: ReactNode;
}

export function AuthCard({ title, description, footer, children }: AuthCardProps) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-muted/40 px-4 py-10">
      <LanguagePicker />
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
        {footer && <CardFooter className="justify-center gap-1 text-sm text-muted-foreground">{footer}</CardFooter>}
      </Card>
    </main>
  );
}
