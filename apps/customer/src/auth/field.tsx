import { Input } from "@clara/ui/components/input";
import { Label } from "@clara/ui/components/label";
import { useId, type ComponentProps } from "react";

interface FieldProps extends ComponentProps<typeof Input> {
  label: string;
  hint?: string;
}

export function Field({ label, hint, ...props }: FieldProps) {
  const id = useId();
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-describedby={hint ? `${id}-hint` : undefined} {...props} />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-sm text-destructive">
      {message}
    </p>
  );
}
