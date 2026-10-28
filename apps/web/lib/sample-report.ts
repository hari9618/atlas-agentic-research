// A sample brief for Helios Robotics, built ONLY from facts in the demo corpus
// (data/corpus). Used by the landing page mock + preview and to develop the report
// UI without a backend. Always labelled "Sample" wherever it is shown.

import type { Citation, DebateTurn, Finding, ReportSections, ResearchPayload } from "./api";

export const SAMPLE_QUERY = "Should I worry about Helios Robotics as a competitor?";

export const SAMPLE_SECTIONS: ReportSections = {
  company: "Helios Robotics",
  headline:
    "Helios is growing fast and shifting toward recurring software revenue, but heavy customer concentration and a single-source supplier keep the picture balanced.",
  stance: "neutral",
  confidence: 0.62,
  executive_summary: [
    "FY2025 revenue reached $4.2B, up 28% year over year from $3.28B [sec_edgar#0].",
    "Fleet software and services make up more than 30% of revenue, ahead of rival Aster Dynamics at about 18% [research#0].",
    "A $900M, five-year contract signed in March 2026 covers 12,000 robots, with roughly 40% of its value in recurring software and support [news#0].",
    "The top three customers accounted for 39% of FY2025 revenue, so losing one would hurt [sec_edgar#1].",
    "High-precision actuators come from a single Taiwanese supplier; dual-sourcing is not expected before late 2026 [sec_edgar#1].",
  ],
  company_overview: {
    what_they_do:
      "Helios Robotics builds robots and the fleet software and services that run them [sec_edgar#0].",
    business_model:
      "Revenue comes from robot sales plus fleet software and services, which are more than 30% of the total and growing in importance [research#0].",
    products: ["Robots", "Fleet software", "Software & support services"],
    customers:
      "A concentrated base: the three largest customers made up 39% of FY2025 revenue [sec_edgar#1].",
  },
  financials: {
    summary:
      "Revenue grew 28% to $4.2B in FY2025 [sec_edgar#0]. The mix is tilting toward software and services, which tends to be more recurring than hardware [research#0].",
    metrics: [
      { label: "Revenue (FY2025)", value: "$4.2B", change: "+28% YoY", citation: "[sec_edgar#0]" },
      { label: "Revenue (FY2024)", value: "$3.28B", citation: "[sec_edgar#0]" },
      { label: "Software & services share", value: ">30%", change: "vs ~18% at Aster", citation: "[research#0]" },
      { label: "Top-3 customer share", value: "39%", change: "of FY2025 revenue", citation: "[sec_edgar#1]" },
    ],
  },
  market_position: {
    summary:
      "Helios has a larger software mix than its main rival and just won a large multi-year deal, but depends on a few big customers [research#0] [news#0].",
    strengths: [
      "Software and services above 30% of revenue vs about 18% at Aster Dynamics [research#0].",
      "A $900M five-year contract with roughly 40% recurring software and support [news#0].",
      "Revenue up 28% year over year [sec_edgar#0].",
    ],
    weaknesses: [
      "Top three customers are 39% of revenue [sec_edgar#1].",
      "Single Taiwanese supplier for high-precision actuators [sec_edgar#1].",
    ],
  },
  competitors: [
    {
      name: "Aster Dynamics",
      comparison:
        "Smaller software mix (about 18% of revenue vs more than 30% at Helios), so less recurring revenue [research#0].",
      threat: "medium",
      citation: "[research#0]",
    },
  ],
  recent_developments: [
    {
      date: "Mar 2026",
      title: "$900M, five-year contract for 12,000 robots",
      detail:
        "About 40% of the contract value is recurring software and support, which strengthens revenue visibility [news#0].",
      sentiment: "positive",
      citation: "[news#0]",
    },
    {
      date: "Mar 2026",
      title: "Shares rose 14% on the deal",
      detail: "The market read the contract as a clear positive [news#0].",
      sentiment: "positive",
      citation: "[news#0]",
    },
  ],
  sentiment: {
    overall: "positive",
    summary:
      "Recent news is upbeat: the March 2026 contract lifted the stock 14% [news#0]. Filings are more cautious about concentration and supply [sec_edgar#1].",
  },
  risks: [
    {
      title: "Customer concentration",
      severity: "high",
      detail: "The top three customers account for 39% of FY2025 revenue [sec_edgar#1].",
      citation: "[sec_edgar#1]",
    },
    {
      title: "Single-source actuators",
      severity: "high",
      detail:
        "High-precision actuators come from one Taiwanese supplier; dual-sourcing is not expected before late 2026 [sec_edgar#1].",
      citation: "[sec_edgar#1]",
    },
    {
      title: "Delivery on the new contract",
      severity: "medium",
      detail:
        "Shipping 12,000 robots under the new deal depends on the same single actuator supplier [news#0] [sec_edgar#1].",
      citation: "[news#0]",
    },
  ],
  bull_case: [
    "28% revenue growth to $4.2B shows strong demand [sec_edgar#0].",
    "A higher software mix than Aster Dynamics means more recurring revenue [research#0].",
    "The $900M contract locks in years of software and support revenue [news#0].",
  ],
  bear_case: [
    "Three customers drive 39% of revenue; one loss would be material [sec_edgar#1].",
    "A single Taiwanese actuator supplier is a supply-chain choke point until at least late 2026 [sec_edgar#1].",
    "The 14% share jump may already price in the good news [news#0].",
  ],
  outlook: {
    summary:
      "Expect continued growth and a rising software share if the new contract ships on schedule [news#0]. Supply and concentration are the swing factors [sec_edgar#1].",
    watch_items: [
      "Progress on dual-sourcing actuators (not expected before late 2026) [sec_edgar#1].",
      "Deliveries under the 12,000-robot contract [news#0].",
      "Whether the top-3 customer share falls below 39% [sec_edgar#1].",
      "Software and services share of revenue vs Aster Dynamics [research#0].",
    ],
  },
  bottom_line:
    "Take Helios seriously as a competitor: it is growing 28% a year and building recurring software revenue faster than Aster Dynamics [sec_edgar#0] [research#0]. Its weak points are a handful of large customers and one actuator supplier [sec_edgar#1].",
  uncertainties: [
    "Profitability and margins are not covered by the evidence we found.",
    "We don't know who the top three customers are or when their contracts renew.",
    "The timing of dual-sourcing could slip beyond late 2026.",
  ],
};

export const SAMPLE_CITATIONS: Citation[] = [
  { citation: "Helios Robotics FY2025 10-K, results (sec_edgar#0)", agent: "fundamentals" },
  { citation: "Helios Robotics FY2025 10-K, risk factors (sec_edgar#1)", agent: "risk" },
  { citation: "Helios Robotics signs largest-ever deal, shares jump (news#0)", agent: "news_sentiment" },
  { citation: "Aster Dynamics company profile (research#0)", agent: "market" },
];

export const SAMPLE_FINDINGS: Finding[] = [
  {
    agent: "fundamentals",
    claim: "FY2025 revenue was $4.2B, up 28% from $3.28B in FY2024.",
    citation: "Helios Robotics FY2025 10-K, results (sec_edgar#0)",
    confidence: 0.9,
  },
  {
    agent: "news_sentiment",
    claim: "Helios signed a $900M five-year contract for 12,000 robots; shares rose 14%.",
    citation: "Helios Robotics signs largest-ever deal, shares jump (news#0)",
    confidence: 0.85,
  },
  {
    agent: "market",
    claim: "Fleet software & services exceed 30% of Helios revenue vs ~18% at Aster Dynamics.",
    citation: "Aster Dynamics company profile (research#0)",
    confidence: 0.8,
  },
  {
    agent: "risk",
    claim: "Top three customers were 39% of FY2025 revenue; actuators are single-sourced from Taiwan.",
    citation: "Helios Robotics FY2025 10-K, risk factors (sec_edgar#1)",
    confidence: 0.85,
  },
];

export const SAMPLE_DEBATE: DebateTurn[] = [
  {
    role: "bull",
    text: "28% growth to $4.2B and a software mix above 30% make Helios a durable, compounding competitor. The $900M deal adds years of recurring revenue.",
    leaning: "positive",
  },
  {
    role: "bear",
    text: "39% of revenue sits with three customers and every robot depends on one Taiwanese actuator supplier until at least late 2026. One disruption hits the big new contract directly.",
    leaning: "cautious",
  },
  {
    role: "judge",
    text: "Both sides are supported by the evidence. Growth and software mix are real; so are concentration and supply risk. Net: neutral, moderate confidence.",
    leaning: "neutral",
  },
];

export const SAMPLE_PAYLOAD: ResearchPayload = {
  report: "",
  report_sections: SAMPLE_SECTIONS,
  confidence: SAMPLE_SECTIONS.confidence ?? null,
  uncertainties: SAMPLE_SECTIONS.uncertainties ?? [],
  citations: SAMPLE_CITATIONS,
  findings: SAMPLE_FINDINGS,
  debate: SAMPLE_DEBATE,
  plan: ["fundamentals", "news_sentiment", "market", "risk"],
  target: "Helios Robotics",
};
