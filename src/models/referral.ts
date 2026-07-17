export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  facility: string;
  city: string;
  distanceKm: number;
  availability: string;
  source: "sandbox";
}

export interface Referral {
  id: string;
  doctorId: string;
  doctorName: string;
  facility: string;
  scenario: string;
  createdAt: string;
  status: "sent";
  source: "sandbox";
}

export interface ReferralInput {
  doctorId: string;
  scenario: string;
  note?: string;
}
