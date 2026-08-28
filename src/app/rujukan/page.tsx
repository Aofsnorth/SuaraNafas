import type { Metadata } from "next";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { AuthGate } from "@/components/auth/AuthGate";
import { DoctorReferralPanel } from "@/components/referral/DoctorReferralPanel";

export const metadata: Metadata = {
  title: "Rujukan",
  description:
    "Rekomendasi dokter contoh (sandbox) dan pembuatan rujukan simulasi bergaya SatuSehat.",
};

export default function RujukanPage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="app" />
      <Navbar />
      <main id="konten-utama" className="app-main">
        <div className="section-shell">
          <AuthGate next="/rujukan">
            <DoctorReferralPanel />
          </AuthGate>
        </div>
      </main>
      <Footer />
    </div>
  );
}
