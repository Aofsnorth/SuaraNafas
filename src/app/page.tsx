import { AtmosphericBackground } from "@/components/AtmosphericBackground";
import { Navbar } from "@/components/Navbar";
import { Landing } from "@/components/Landing";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <AtmosphericBackground variant="landing" />
      <Navbar />
      <Landing />
      <Footer />
    </div>
  );
}
