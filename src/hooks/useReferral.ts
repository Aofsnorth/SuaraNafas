"use client";

import { useCallback, useState } from "react";
import { Doctor, Referral, ReferralInput } from "@/models/referral";
import { createReferral, listDoctors } from "@/services/referral-service";

type ReferralStatus = "idle" | "sending" | "sent" | "error";

interface UseReferralReturn {
  doctors: Doctor[];
  status: ReferralStatus;
  referral: Referral | null;
  error: string | null;
  refer: (input: ReferralInput) => Promise<Referral | null>;
  reset: () => void;
}

export function useReferral(): UseReferralReturn {
  const doctors = listDoctors();
  const [status, setStatus] = useState<ReferralStatus>("idle");
  const [referral, setReferral] = useState<Referral | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refer = useCallback(async (input: ReferralInput) => {
    setStatus("sending");
    setError(null);
    try {
      const created = await createReferral(input);
      setReferral(created);
      setStatus("sent");
      return created;
    } catch {
      setError("Gagal membuat rujukan. Coba lagi.");
      setStatus("error");
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setReferral(null);
    setError(null);
  }, []);

  return { doctors, status, referral, error, refer, reset };
}
