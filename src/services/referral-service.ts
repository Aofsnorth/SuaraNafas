import { Doctor, Referral, ReferralInput } from "@/models/referral";

const DOCTORS: Doctor[] = [
  {
    id: "prc-001",
    name: "dr. Sari Wijaya, Sp.P",
    specialty: "Pulmonologi",
    facility: "RSUP Persahabatan",
    city: "Jakarta Timur",
    distanceKm: 3.2,
    availability: "Hari ini · 14:00",
    source: "sandbox",
  },
  {
    id: "prc-002",
    name: "dr. Bagus Nugroho, Sp.P",
    specialty: "Pulmonologi",
    facility: "RS Paru dr. M. Goenawan Partowidigdo",
    city: "Bogor",
    distanceKm: 6.8,
    availability: "Besok · 09:30",
    source: "sandbox",
  },
  {
    id: "prc-003",
    name: "dr. Ratih Kusuma",
    specialty: "Dokter Umum · Skrining TB",
    facility: "Puskesmas Kecamatan Matraman",
    city: "Jakarta Timur",
    distanceKm: 1.4,
    availability: "Hari ini · 16:15",
    source: "sandbox",
  },
  {
    id: "prc-004",
    name: "dr. Andini Prakoso, Sp.P",
    specialty: "Pulmonologi",
    facility: "RSUD Tarakan",
    city: "Jakarta Pusat",
    distanceKm: 5.1,
    availability: "Besok · 13:00",
    source: "sandbox",
  },
  {
    id: "prc-005",
    name: "dr. Hendra Saputra",
    specialty: "Dokter Umum · Skrining TB",
    facility: "Klinik Pratama Sehat Bersama",
    city: "Depok",
    distanceKm: 8.7,
    availability: "Hari ini · 19:00",
    source: "sandbox",
  },
];

export function listDoctors(): Doctor[] {
  return DOCTORS;
}

export async function createReferral(input: ReferralInput): Promise<Referral> {
  const doctor = DOCTORS.find((item) => item.id === input.doctorId);
  await new Promise((resolve) => setTimeout(resolve, 700));

  return {
    id: `REF-${Date.now().toString(36).toUpperCase()}`,
    doctorId: input.doctorId,
    doctorName: doctor?.name ?? "Dokter",
    facility: doctor?.facility ?? "Fasilitas kesehatan",
    scenario: input.scenario,
    createdAt: new Date().toISOString(),
    status: "sent",
    source: "sandbox",
  };
}
