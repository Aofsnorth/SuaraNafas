import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ConvexSurfaceVariant = "panel" | "card" | "note";
export type ConvexSurfaceElement = "article" | "aside" | "div" | "section";

interface ConvexSurfaceProps extends HTMLAttributes<HTMLElement> {
  as?: ConvexSurfaceElement;
  children: ReactNode;
  variant?: ConvexSurfaceVariant;
}

export function ConvexSurface({
  as = "div",
  children,
  className,
  variant = "card",
  ...props
}: ConvexSurfaceProps) {
  const classes = cn("convex-surface", `convex-surface--${variant}`, className);

  if (as === "article") {
    return <article className={classes} {...props}>{children}</article>;
  }

  if (as === "aside") {
    return <aside className={classes} {...props}>{children}</aside>;
  }

  if (as === "section") {
    return <section className={classes} {...props}>{children}</section>;
  }

  return <div className={classes} {...props}>{children}</div>;
}
