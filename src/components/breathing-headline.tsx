import type { ReactNode } from "react";

interface BreathingHeadlineProps {
  children: ReactNode;
  className?: string;
  id: string;
}

export function BreathingHeadline({ children, className, id }: BreathingHeadlineProps) {
  return (
    <div className={className}>
      <h1 id={id} className="sr-only">{children}</h1>
      <div className="breathing-headline" aria-hidden="true">
        <span className="breathing-headline__layer breathing-headline__layer--calm">
          {children}
        </span>
        <span className="breathing-headline__layer breathing-headline__layer--soft">
          {children}
        </span>
      </div>
    </div>
  );
}
