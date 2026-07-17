"use client";

import { useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/useAuth";

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { configured, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!configured) {
    return (
      <div className="auth-card" role="status">
        <p className="auth-card__notice-title">Autentikasi belum dikonfigurasi</p>
        <p className="auth-card__notice">
          Tambahkan variabel NEXT_PUBLIC_FIREBASE_* pada .env.local untuk
          mengaktifkan masuk dengan email. Bagian lain tetap dapat dicoba.
        </p>
      </div>
    );
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      if (mode === "signin") await signIn(email, password);
      else await signUp(email, password);
      onSuccess?.();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Gagal masuk. Periksa email dan kata sandi.",
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <form className="auth-card" onSubmit={submit} noValidate>
      <div className="auth-field">
        <label htmlFor="auth-email">Email</label>
        <input
          id="auth-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="auth-field">
        <label htmlFor="auth-password">Kata sandi</label>
        <input
          id="auth-password"
          type="password"
          autoComplete={mode === "signin" ? "current-password" : "new-password"}
          required
          minLength={6}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>

      {error && (
        <p role="alert" className="auth-error">
          {error}
        </p>
      )}

      <button type="submit" className="btn-primary auth-submit" disabled={pending}>
        {pending ? "Memproses…" : mode === "signin" ? "Masuk" : "Daftar & masuk"}
      </button>

      <button
        type="button"
        className="cta-link auth-toggle"
        onClick={() => {
          setMode(mode === "signin" ? "signup" : "signin");
          setError(null);
        }}
      >
        {mode === "signin" ? "Belum punya akun? Daftar" : "Sudah punya akun? Masuk"}
      </button>
    </form>
  );
}
