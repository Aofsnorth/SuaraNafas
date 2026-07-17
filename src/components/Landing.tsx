import { Hero } from "@/components/Hero";
import { LabStrip } from "@/components/LabStrip";
import { Manifesto } from "@/components/Manifesto";
import { Workflow } from "@/components/Workflow";
import { Science } from "@/components/Science";
import { TbDataSection } from "@/components/tb-data-section";
import { CaseFile } from "@/components/CaseFile";
import { Faq } from "@/components/Faq";
import { Statement } from "@/components/Statement";

export function Landing() {
  return (
    <main className="relative">
      <Hero />
      <LabStrip />
      <Manifesto />
      <Workflow />
      <Science />
      <TbDataSection />
      <Faq />
      <Statement />
    </main>
  );
}
