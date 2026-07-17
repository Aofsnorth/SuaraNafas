"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthUser } from "@/models/auth";
import {
  observeAuth,
  signIn as authSignIn,
  signUp as authSignUp,
  signOutUser,
  isFirebaseConfigured,
} from "@/services/auth-service";

interface UseAuthReturn {
  user: AuthUser | null;
  ready: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const configured = isFirebaseConfigured();

  useEffect(() => {
    const unsubscribe = observeAuth((next) => {
      setUser(next);
      setReady(true);
    });
    return () => unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await authSignIn(email, password);
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    await authSignUp(email, password);
  }, []);

  const signOut = useCallback(async () => {
    await signOutUser();
  }, []);

  return { user, ready, configured, signIn, signUp, signOut };
}
