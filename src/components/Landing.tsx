import { Hero } from "@/components/Hero";
import { LabStrip } from "@/components/LabStrip";
import { TbDataSection } from "@/components/tb-data-section";
import { Workflow } from "@/components/Workflow";
import { Science } from "@/components/Science";
import { CaseFile } from "@/components/CaseFile";
import { Faq } from "@/components/Faq";
import { Statement } from "@/components/Statement";

export function Landing() {
  return (
    <main className="relative">
      <Hero />
      <LabStrip />
      <TbDataSection />
      <Workflow />
      <Science />
      <CaseFile />
      <Faq />
      <Statement />
    </main>
  );
}
