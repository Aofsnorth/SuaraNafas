"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

interface AuthGateProps {
  next: string;
  children: ReactNode;
}

export function AuthGate({ next, children }: AuthGateProps) {
  const router = useRouter();
  const { user, ready } = useAuth();

  useEffect(() => {
    if (ready && !user) {
      router.replace(`/masuk?next=${encodeURIComponent(next)}`);
    }
  }, [ready, user, next, router]);

  if (!ready) {
    return (
      <div className="auth-loading" role="status">
        Memeriksa sesi…
      </div>
    );
  }

  if (!user) {
    return (
      <div className="auth-loading" role="status">
        Mengalihkan ke halaman masuk…
      </div>
    );
  }

  return <>{children}</>;
}
