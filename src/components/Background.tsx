import {
  AtmosphericBackground,
  type BackgroundVariant,
} from "@/components/AtmosphericBackground";

interface BackgroundProps {
  variant?: Exclude<BackgroundVariant, "landing">;
}

export function Background({ variant = "app" }: BackgroundProps) {
  return <AtmosphericBackground variant={variant} />;
}
