import type { ReactNode } from "react";
import { ConvexSurface } from "@/components/convex-surface";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
}

export function GlassCard({ children, className }: GlassCardProps) {
  return (
    <ConvexSurface className={className} variant="card">
      {children}
    </ConvexSurface>
  );
}
