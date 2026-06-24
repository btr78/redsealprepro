// SEO data for per-trade landing pages. Each becomes /<slug> — a keyword-rich page that ranks
// for "<trade> red seal practice exam/test" searches and funnels to the free quiz.
export const TRADES_SEO = [
  {
    slug: "construction-electrician-309a-red-seal-practice-exam", code: "309A",
    name: "Construction Electrician", short: "Construction Electrician",
    intro: "Get exam-ready for the 309A Construction Electrician Red Seal (Certificate of Qualification) with realistic, up-to-date practice questions and instant explanations.",
    topics: ["Canadian Electrical Code (CEC)", "Conductors & wiring methods", "Circuits, Ohm's law & calculations", "Motors, controls & transformers", "Services, panels & distribution", "Conduit bending & installation", "Safety, lockout & WHMIS"],
  },
  {
    slug: "industrial-electrician-442a-red-seal-practice-exam", code: "442A",
    name: "Industrial Electrician", short: "Industrial Electrician",
    intro: "Prepare for the 442A Industrial Electrician Red Seal exam with practice questions covering plant electrical systems, controls and troubleshooting.",
    topics: ["PLCs & industrial controls", "Motor controls & VFDs", "Instrumentation & process control", "Three-phase systems", "Transformers & power distribution", "Troubleshooting & maintenance", "Industrial CEC & safety"],
  },
  {
    slug: "plumber-306a-red-seal-practice-exam", code: "306A",
    name: "Plumber", short: "Plumber",
    intro: "Practice for the 306A Plumber Red Seal exam with questions on drainage, water supply, venting, code and fixtures — with clear explanations on every answer.",
    topics: ["Drainage, waste & vent (DWV)", "Water supply & pipe sizing", "Venting systems", "Fixtures & appliances", "Backflow prevention", "Materials & joining methods", "Plumbing code & safety"],
  },
  {
    slug: "steamfitter-pipefitter-307a-red-seal-practice-exam", code: "307A",
    name: "Steamfitter / Pipefitter", short: "Steamfitter/Pipefitter",
    intro: "Get ready for the 307A Steamfitter/Pipefitter Red Seal exam with practice questions on piping systems, welding, steam and hydronic systems.",
    topics: ["Piping systems & layout", "Welding & joining", "Steam & hydronic systems", "Blueprint & isometric reading", "Rigging & hoisting", "Valves & supports", "Pressure & safety"],
  },
  {
    slug: "automotive-service-technician-310s-red-seal-practice-exam", code: "310S",
    name: "Automotive Service Technician", short: "Auto Service Technician",
    intro: "Study for the 310S Automotive Service Technician Red Seal exam with practice questions on engines, brakes, electrical and diagnostics.",
    topics: ["Engines & fuel systems", "Brakes & ABS", "Electrical & electronics", "Steering & suspension", "Heating & A/C (HVAC)", "Drivetrain & transmissions", "Diagnostics & scan tools"],
  },
  {
    slug: "carpenter-403a-red-seal-practice-exam", code: "403A",
    name: "Carpenter", short: "Carpenter",
    intro: "Prepare for the 403A Carpenter Red Seal exam with realistic practice questions on framing, concrete, finishing and code.",
    topics: ["Framing & structures", "Foundations & concrete", "Blueprint reading", "Stairs & roofing", "Interior & exterior finishing", "Renovations", "Building code & safety"],
  },
  {
    slug: "tool-and-die-maker-430a-red-seal-practice-exam", code: "430A",
    name: "Tool and Die Maker", short: "Tool and Die Maker",
    intro: "Practice for the 430A Tool and Die Maker Red Seal exam with questions on machining, die design, metrology and GD&T.",
    topics: ["Machining & grinding", "GD&T & blueprint reading", "Die & mould design", "Metrology & inspection", "Materials & heat treatment", "CNC programming", "Jigs & fixtures"],
  },
  {
    slug: "millwright-433a-red-seal-practice-exam", code: "433A",
    name: "Industrial Mechanic (Millwright)", short: "Industrial Mechanic (Millwright)",
    intro: "Get exam-ready for the 433A Industrial Mechanic (Millwright) Red Seal with practice questions on bearings, alignment, hydraulics and power transmission.",
    topics: ["Bearings & lubrication", "Precision alignment", "Pumps & compressors", "Hydraulics & pneumatics", "Power transmission", "Rigging & hoisting", "Vibration & maintenance"],
  },
  {
    slug: "welder-456a-red-seal-practice-exam", code: "456A",
    name: "Welder", short: "Welder",
    intro: "Study for the 456A Welder Red Seal exam with practice questions covering SMAW, GMAW, GTAW, metallurgy and welding symbols.",
    topics: ["SMAW (stick)", "GMAW / FCAW (MIG)", "GTAW (TIG)", "Metallurgy & distortion", "Welding symbols & blueprints", "Joint design & positions", "CWB codes & safety"],
  },
];

export const findTrade = (slug) => TRADES_SEO.find((t) => t.slug === slug);
