export type BackgroundVariant = "landing" | "app" | "document";

interface AtmosphericBackgroundProps {
  variant?: BackgroundVariant;
}

/**
 * Latar belakang tenang: gradasi radial sangat halus di atas kertas hangat.
 * Sengaja tanpa partikel, grid, atau animasi — elemen bergerak hanya untuk
 * menyampaikan status (mis. denyut napas saat merekam).
 */
export function AtmosphericBackground({
  variant = "landing",
}: AtmosphericBackgroundProps) {
  return <div className="calm-backdrop" data-variant={variant} aria-hidden="true" />;
}
