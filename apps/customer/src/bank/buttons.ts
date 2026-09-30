import { cn } from "@clara/ui/lib/cn";

export const pillButton =
  "inline-flex h-[42px] items-center justify-center gap-2 rounded-full border border-line bg-surface px-[18px] text-[14.5px] font-semibold whitespace-nowrap transition-colors outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50";

export const primaryPillButton = cn(pillButton, "border-primary bg-primary text-primary-foreground hover:bg-primary hover:brightness-110");

export const textLink =
  "inline-flex w-fit items-center gap-1 py-1 text-sm font-semibold text-ink outline-none hover:text-primary focus-visible:ring-[3px] focus-visible:ring-ring/40 rounded-sm";
