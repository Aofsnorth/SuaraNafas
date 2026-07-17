"use client";

import { useState } from "react";
import { useReferral } from "@/hooks/useReferral";
import { DoctorCard } from "@/components/referral/DoctorCard";
import { ConvexSurface } from "@/components/convex-surface";

interface DoctorReferralPanelProps {
  scenario?: string;
}

export function DoctorReferralPanel({
  scenario = "Skenario simulasi C",
}: DoctorReferralPanelProps) {
  const { doctors, status, referral, error, refer, reset } = useReferral();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (status === "sent" && referral) {
    return (
      <ConvexSurface variant="panel" className="referral-confirm">
        <p className="section-tag">Rujukan dibuat</p>
        <h2 className="referral-confirm__title">Rujukan terkirim (simulasi)</h2>
        <dl className="referral-confirm__list">
          <div>
            <dt>Kode</dt>
            <dd>{referral.id}</dd>
          </div>
          <div>
            <dt>Dokter</dt>
            <dd>{referral.doctorName}</dd>
          </div>
          <div>
            <dt>Fasilitas</dt>
            <dd>{referral.facility}</dd>
          </div>
          <div>
            <dt>Skenario</dt>
            <dd>{referral.scenario}</dd>
          </div>
        </dl>
        <p className="referral-confirm__note">
          Ini rujukan contoh (sandbox), bukan janji temu medis nyata. Untuk
          pemeriksaan sebenarnya, hubungi fasilitas kesehatan resmi.
        </p>
        <button
          type="button"
          className="cta-link"
          onClick={() => {
            reset();
            setSelectedId(null);
          }}
        >
          Buat rujukan lain
        </button>
      </ConvexSurface>
    );
  }

  return (
    <div className="referral-panel">
      <header className="referral-panel__head">
        <p className="section-tag">Rekomendasi dokter</p>
        <h1 className="referral-panel__title">Pilih dokter untuk dirujuk</h1>
        <p className="referral-panel__note">
          Daftar berikut adalah data contoh bergaya SatuSehat (sandbox) untuk{" "}
          {scenario}. Bukan data faskes nyata dan bukan diagnosis medis.
        </p>
      </header>

      <div className="referral-panel__list">
        {doctors.map((doctor) => (
          <DoctorCard
            key={doctor.id}
            doctor={doctor}
            pending={status === "sending" && selectedId === doctor.id}
            disabled={status === "sending"}
            onRefer={() => {
              setSelectedId(doctor.id);
              refer({ doctorId: doctor.id, scenario });
            }}
          />
        ))}
      </div>

      {error && (
        <p role="alert" className="referral-panel__error">
          {error}
        </p>
      )}
    </div>
  );
}
