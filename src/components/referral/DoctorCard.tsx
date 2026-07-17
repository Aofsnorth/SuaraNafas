import { Doctor } from "@/models/referral";
import { ConvexSurface } from "@/components/convex-surface";

interface DoctorCardProps {
  doctor: Doctor;
  pending: boolean;
  disabled: boolean;
  onRefer: () => void;
}

export function DoctorCard({ doctor, pending, disabled, onRefer }: DoctorCardProps) {
  return (
    <ConvexSurface as="article" variant="card" className="doctor-card">
      <div className="doctor-card__head">
        <h3>{doctor.name}</h3>
        <span className="doctor-card__badge">Data contoh · sandbox</span>
      </div>
      <p className="doctor-card__specialty">{doctor.specialty}</p>
      <p className="doctor-card__facility">
        {doctor.facility} · {doctor.city}
      </p>
      <div className="doctor-card__meta">
        <span>{doctor.distanceKm} km</span>
        <span>{doctor.availability}</span>
      </div>
      <button
        type="button"
        className="btn-primary doctor-card__cta"
        onClick={onRefer}
        disabled={disabled}
      >
        {pending ? "Mengirim…" : "Rujuk ke sini"}
      </button>
    </ConvexSurface>
  );
}
