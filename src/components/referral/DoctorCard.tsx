import { Doctor } from "@/models/referral";

interface DoctorCardProps {
  doctor: Doctor;
  pending: boolean;
  disabled: boolean;
  onRefer: () => void;
}

function initials(name: string) {
  return name
    .replace(/^dr\.?\s*/i, "")
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function DoctorCard({ doctor, pending, disabled, onRefer }: DoctorCardProps) {
  return (
    <article className="panel doctor-card">
      <div className="doctor-card__head">
        <span className="doctor-card__avatar" aria-hidden="true">
          {initials(doctor.name)}
        </span>
        <div className="doctor-card__id">
          <h3 className="doctor-card__name">{doctor.name}</h3>
          <p className="doctor-card__specialty">{doctor.specialty}</p>
          <p className="doctor-card__facility">
            {doctor.facility} · {doctor.city}
          </p>
        </div>
      </div>

      <div className="doctor-card__meta">
        <span className="chip">{doctor.distanceKm} km</span>
        <span className="chip">{doctor.availability}</span>
        <span className="chip">Data contoh · sandbox</span>
      </div>

      <button
        type="button"
        className="btn-primary doctor-card__cta"
        onClick={onRefer}
        disabled={disabled}
      >
        {pending ? "Mengirim…" : "Rujuk ke sini"}
      </button>
    </article>
  );
}
