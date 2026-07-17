export interface TbDatum {
  value: string;
  label: string;
  definition: string;
  year: number;
  sourceTitle: string;
  sourceUrl: string;
  note?: string;
}

export const TB_DATA: readonly TbDatum[] = [
  {
    value: "10,8 juta",
    label: "Estimasi orang yang jatuh sakit akibat TB secara global",
    definition: "Estimasi kasus insiden TB, bukan jumlah diagnosis yang dilaporkan.",
    year: 2023,
    sourceTitle: "WHO Global Tuberculosis Report 2024 — TB incidence",
    sourceUrl:
      "https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-disease-burden/1-1-tb-incidence",
    note: "Interval ketidakpastian 10,1–11,7 juta; 134 kasus insiden per 100.000 penduduk.",
  },
  {
    value: "8,2 juta",
    label: "Orang dengan episode TB baru atau kambuh yang didiagnosis dan dinotifikasi",
    definition: "Kasus baru dan kambuh yang didiagnosis dan dinotifikasi, bukan estimasi total insiden.",
    year: 2023,
    sourceTitle: "WHO Global Tuberculosis Report 2024 — Case notifications",
    sourceUrl:
      "https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-diagnosis-and-treatment/2-1-case-notifications",
  },
  {
    value: "10%",
    label: "Perkiraan bagian Indonesia dari kasus insiden TB global",
    definition: "Proporsi estimasi kasus insiden TB global yang dikaitkan WHO dengan Indonesia.",
    year: 2023,
    sourceTitle: "WHO — Tuberculosis resurges as top infectious disease killer",
    sourceUrl:
      "https://www.who.int/news/item/29-10-2024-tuberculosis-resurges-as-top-infectious-disease-killer",
  },
] as const;
