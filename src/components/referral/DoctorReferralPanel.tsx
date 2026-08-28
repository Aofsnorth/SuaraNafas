"use client";

import { useState } from "react";
import { useReferral } from "@/hooks/useReferral";
import { DoctorCard } from "@/components/referral/DoctorCard";

interface DoctorReferralPanelProps {
  scenario?: string;
}

export function DoctorReferralPanel({
  scenario = "hasil skrining",
}: DoctorReferralPanelProps) {
  const { doctors, status, referral, error, refer, reset } = useReferral();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (status === "sent" && referral) {
    return (
      <section className="panel referral-confirm" aria-labelledby="referral-confirm-title">
        <span className="chip chip--success">Rujukan terkirim (simulasi)</span>
        <h2 id="referral-confirm-title" className="referral-confirm__title">
          Rujukan contoh berhasil dibuat.
        </h2>
        <dl className="referral-confirm__list">
          <div>
            <dt>Kode rujukan</dt>
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
          Ini rujukan contoh untuk demonstrasi alur — bukan janji temu medis
          nyata. Untuk pemeriksaan sebenarnya, hubungi fasilitas kesehatan
          resmi terdekat.
        </p>
        <div>
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
        </div>
      </section>
    );
  }

  return (
    <div className="referral-panel">
      <header className="referral-head">
        <p className="eyebrow">Rujukan</p>
        <h1>Pilih dokter untuk langkah lanjutan.</h1>
        <p>
          Daftar berikut adalah data contoh bergaya SatuSehat (sandbox) untuk{" "}
          {scenario} — bukan fasilitas kesehatan nyata. Di produksi, daftar ini
          akan tersambung ke ekosistem layanan kesehatan resmi.
        </p>
      </header>

      <div className="referral-list">
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
