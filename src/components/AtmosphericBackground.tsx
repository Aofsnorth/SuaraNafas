import type { CSSProperties } from "react";

export type BackgroundVariant = "landing" | "app" | "document";

interface AtmosphericBackgroundProps {
  variant?: BackgroundVariant;
}

const SPECTRUM_BARS = Array.from({ length: 72 }, (_, index) => {
  const primary = Math.abs(Math.sin(index * 0.43));
  const secondary = Math.abs(Math.sin(index * 0.17 + 1.2));

  return {
    height: 0.16 + primary * 0.52 + secondary * 0.2,
    delay: index * -0.075,
    duration: 1.7 + (index % 7) * 0.13,
  };
});

export function AtmosphericBackground({
  variant = "landing",
}: AtmosphericBackgroundProps) {
  return (
    <div className="signal-field" data-variant={variant} aria-hidden="true">
      <div className="signal-field__glow signal-field__glow--one" />
      <div className="signal-field__glow signal-field__glow--two" />
      <div className="signal-field__noise" />
      <div className="signal-field__grid" />
      <div className="signal-field__contours" />
      <svg className="signal-field__wave" viewBox="0 0 3200 300" preserveAspectRatio="none">
        <path
          className="signal-field__wave-echo"
          d="M0 168 Q 400 214 800 168 T 1600 168 T 2400 168 T 3200 168"
        />
        <path
          className="signal-field__wave-main"
          d="M0 150 Q 400 96 800 150 T 1600 150 T 2400 150 T 3200 150"
        />
      </svg>
      <div className="signal-field__particles" />
      <div className="signal-field__spectrum">
        {SPECTRUM_BARS.map((bar, index) => (
          <span
            key={index}
            className="signal-field__bar"
            style={
              {
                "--bar-height": `${Math.round(bar.height * 100)}%`,
                "--bar-delay": `${bar.delay}s`,
                "--bar-speed": `${bar.duration}s`,
              } as CSSProperties
            }
          />
        ))}
      </div>
    </div>
  );
}
