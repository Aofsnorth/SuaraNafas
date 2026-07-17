import type { Metadata } from "next";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { LoginPanel } from "@/components/auth/LoginPanel";

export const metadata: Metadata = {
  title: "Masuk — GarudaHacks 7.0",
  description:
    "Masuk dengan email untuk melihat rekomendasi dokter dan membuat rujukan.",
};

export default async function MasukPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  const next =
    typeof params.next === "string" && params.next.startsWith("/")
      ? params.next
      : "/rujukan";

  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="app" />
      <Navbar />
      <main className="relative pt-24 md:pt-36 pb-16 md:pb-24">
        <LoginPanel next={next} />
      </main>
      <Footer />
    </div>
  );
}
