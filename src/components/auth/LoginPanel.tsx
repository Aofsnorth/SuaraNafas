"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { LoginForm } from "@/components/auth/LoginForm";

interface LoginPanelProps {
  next: string;
}

export function LoginPanel({ next }: LoginPanelProps) {
  const router = useRouter();
  const { user, ready } = useAuth();

  useEffect(() => {
    if (ready && user) router.replace(next);
  }, [ready, user, next, router]);

  return (
    <div className="section-shell">
      <div className="auth-shell">
        <p className="section-tag">Rujukan</p>
        <h1 className="auth-shell__title">Masuk untuk merujuk</h1>
        <p className="auth-shell__lede">
          Masuk dengan email untuk melihat rekomendasi dokter (data contoh
          sandbox) dan membuat rujukan. Skrining tetap bisa dicoba tanpa masuk.
        </p>
        <LoginForm onSuccess={() => router.replace(next)} />
      </div>
    </div>
  );
}
