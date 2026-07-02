"use client";
// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from "react";
import { QUESTIONS_309A, CATEGORIES_309A } from "./questions309A";
import { QUESTIONS_442A, CATEGORIES_442A } from "./questions442A";
import { QUESTIONS_306A, CATEGORIES_306A } from "./questions306A";
import { QUESTIONS_430A, CATEGORIES_430A } from "./questions430A";
import { QUESTIONS_307A, CATEGORIES_307A } from "./questions307A";
import { QUESTIONS_403A, CATEGORIES_403A } from "./questions403A";
import { QUESTIONS_310S, CATEGORIES_310S } from "./questions310S";
import { QUESTIONS_456A, CATEGORIES_456A } from "./questions456A";
import { supabase, loadCloudProgress, saveCloudProgress, applyProgress } from "./supabaseClient";

// ═══════════════════════════════════════════════════════════════
// TRADEPREP PRO — Red Seal Exam Prep SaaS
// Multi-trade • AI Tutor • Subscription • PWA-Ready
// ═══════════════════════════════════════════════════════════════

// ─── TRADE DEFINITIONS ──────────────────────────────────────
const TRADES = [
  { id: "433A", name: "Industrial Mechanic (Millwright)", icon: "⚙️", questions: 135, active: true, color: "#ff6b35" },
  { id: "309A", name: "Construction Electrician", icon: "⚡", questions: 135, active: true, color: "#3498db" },
  { id: "442A", name: "Industrial Electrician", icon: "🔌", questions: 135, active: true, color: "#9b59b6" },
  { id: "306A", name: "Plumber", icon: "🔧", questions: 135, active: true, color: "#1abc9c" },
  { id: "430A", name: "Tool and Die Maker", icon: "🔩", questions: 135, active: true, color: "#f39c12" },
  { id: "403A", name: "Carpenter", icon: "🪚", questions: 100, active: true, color: "#e67e22" },
  { id: "310S", name: "Auto Service Technician", icon: "🚗", questions: 120, active: true, color: "#e74c3c" },
  { id: "307A", name: "Steamfitter/Pipefitter", icon: "🔩", questions: 130, active: true, color: "#2ecc71" },
  { id: "456A", name: "Welder", icon: "🔥", questions: 120, active: true, color: "#f39c12" },
];

const CATEGORIES = [
  { id: "A", name: "Common Occupational Skills", target: 25, color: "#e74c3c" },
  { id: "B", name: "Rigging, Hoisting & Moving", target: 17, color: "#e67e22" },
  { id: "C", name: "Mechanical Power Transmission", target: 32, color: "#2ecc71" },
  { id: "D", name: "Material Handling / Process Systems", target: 24, color: "#3498db" },
  { id: "E", name: "Fluid Power Systems", target: 21, color: "#9b59b6" },
  { id: "F", name: "Preventive & Predictive Maintenance", target: 16, color: "#1abc9c" },
];

// ─── 433A QUESTION BANK (135 Questions) ─────────────────────
const QUESTIONS_433A = [
  // ═══ BLOCK A: Common Occupational Skills (25) ═══
  { id:1,cat:"A",q:"What is required when working from heights?",opts:["Hard hat","Fall arrest equipment","Safety glasses","Steel-toed boots"],ans:1,exp:"Fall arrest equipment is mandatory for heights to prevent falls — the #1 cause of workplace fatalities in trades.",type:"recall"},
  { id:2,cat:"A",q:"Before performing maintenance on a machine, what must be done first?",opts:["Notify supervisor","Apply lockout/tagout procedures","Put on safety glasses","Read service manual"],ans:1,exp:"LOTO isolates all energy sources (electrical, pneumatic, hydraulic, mechanical, gravity) to prevent accidental startup. Legally required under OHSA.",type:"procedure"},
  { id:3,cat:"A",q:"What does WHMIS stand for?",opts:["Workplace Hazard Management and Inspection System","Workplace Hazardous Materials Information System","Worker Health and Material Inventory Standards","Workplace Hazard Monitoring and Inspection Services"],ans:1,exp:"WHMIS — Workplace Hazardous Materials Information System — is Canada's national hazard communication standard.",type:"recall"},
  { id:4,cat:"A",q:"A GHS pictogram showing a flame over a circle indicates what hazard?",opts:["Flammable","Oxidizer","Explosive","Compressed gas"],ans:1,exp:"Flame-over-circle = oxidizer. Simple flame = flammable. Exploding bomb = explosive. Gas cylinder = compressed gas.",type:"recall"},
  { id:5,cat:"A",q:"Which instrument measures bore inside diameter to 0.001\" accuracy?",opts:["Outside micrometer","Telescoping gauge and micrometer","Vernier caliper","Steel rule and divider"],ans:1,exp:"Telescoping gauge inserted into the bore, locked, then measured with an outside micrometer for 0.001\" precision.",type:"procedure"},
  { id:6,cat:"A",q:"What type of file is used for finishing soft metals like aluminum?",opts:["Double-cut bastard","Single-cut smooth file","Rasp-cut file","Double-cut second-cut"],ans:1,exp:"Single-cut smooth files produce a finer finish on soft metals and resist loading (clogging) better than double-cut.",type:"recall"},
  { id:7,cat:"A",q:"A dial indicator checking shaft runout reads 0.006\". What is the TIR?",opts:["0.003\"","0.006\"","0.012\"","0.009\""],ans:1,exp:"TIR = Total Indicator Reading = full sweep from low to high. If the indicator reads 0.006\", the TIR IS 0.006\".",type:"critical"},
  { id:8,cat:"A",q:"A torque wrench reads 50 ft-lbs. What is this in Newton-meters?",opts:["36.9 N·m","67.8 N·m","50 N·m","73.7 N·m"],ans:1,exp:"1 ft-lb = 1.3558 N·m → 50 × 1.3558 = 67.79 ≈ 67.8 N·m. Unit conversion is critical for metric/imperial specs.",type:"critical"},
  { id:9,cat:"A",q:"On a blueprint, what does a hidden line (dashed) represent?",opts:["Center of a feature","An edge not visible in current view","A cutting plane","A dimension extension"],ans:1,exp:"Hidden lines (short dashes) show edges that exist but aren't visible from the current viewing angle.",type:"recall"},
  { id:10,cat:"A",q:"A drawing calls for 3/8\"-16 UNC. What does '16' mean?",opts:["Bolt length in sixteenths","Threads per inch","Tensile strength grade","Head size in mm"],ans:1,exp:"In UNC thread designation: 3/8\" = major diameter, 16 = threads per inch (TPI).",type:"recall"},
  { id:11,cat:"A",q:"When lighting an oxy-acetylene torch, which gas is turned on first?",opts:["Oxygen","Acetylene","Either one","Both simultaneously"],ans:1,exp:"Acetylene always first on, oxygen added to adjust flame. Shutdown: close oxygen first, then acetylene.",type:"procedure"},
  { id:12,cat:"A",q:"What type of fit allows hand assembly with slight clearance?",opts:["Interference fit","Sliding fit (clearance fit)","Transition fit","Shrink fit"],ans:1,exp:"Sliding/clearance fit: shaft slightly smaller than hole. Interference fits require force; shrink fits use heat.",type:"recall"},
  { id:13,cat:"A",q:"A metric bolt marked 8.8 — what does the first '8' indicate?",opts:["Yield strength class","Ultimate tensile strength ~800 MPa","Thread pitch","Rockwell C hardness"],ans:1,exp:"Grade 8.8: first number × 100 = UTS (800 MPa). Second × first × 100 = yield (640 MPa).",type:"recall"},
  { id:14,cat:"A",q:"When pressing a bearing onto a shaft, force should be applied to:",opts:["Outer race","Inner race","Rolling elements","Cage"],ans:1,exp:"Force on inner race when mounting on shaft. Force on outer race when pressing into housing. Wrong application damages rolling elements.",type:"procedure"},
  { id:15,cat:"A",q:"What is the correct procedure for tapping a hole in mild steel?",opts:["Drill, ream, then tap","Drill tap-drill size, chamfer, tap with cutting fluid","Drill, countersink, then tap","Drill oversize, force tap"],ans:1,exp:"Drill correct tap-drill size → chamfer entrance → tap with cutting fluid for lubrication and chip clearing.",type:"procedure"},
  { id:16,cat:"A",q:"The most effective training approach when mentoring an apprentice is:",opts:["Let them figure it out independently","Demonstrate, explain, then supervised practice","Give written manuals only","Observe for months first"],ans:1,exp:"Show-tell-do method (demonstrate → explain → supervised practice) is most effective for skilled trades apprenticeships.",type:"recall"},
  { id:17,cat:"A",q:"A complete maintenance report should include:",opts:["Only parts replaced","Work done, parts used, time, and recommendations","Only time spent","Symptoms only"],ans:1,exp:"Document: work performed, parts consumed, labor time, root cause, and recommendations for prevention.",type:"recall"},
  { id:18,cat:"A",q:"When is it appropriate to deviate from manufacturer's procedures?",opts:["When you have more experience","Never without engineering approval and documentation","When supervisor says OK verbally","When old procedure worked before"],ans:1,exp:"Changes require proper engineering review, approval, and documentation. Unauthorized changes void warranties and create hazards.",type:"procedure"},
  { id:19,cat:"A",q:"A vernier micrometer reads: sleeve 0.275\", thimble 0.015\", vernier 0.0003\". Total?",opts:["0.2903\"","0.2900\"","0.2906\"","0.2953\""],ans:0,exp:"Add all readings: 0.275 + 0.015 + 0.0003 = 0.2903\". Always sum sleeve + thimble + vernier.",type:"critical"},
  { id:20,cat:"A",q:"A precision level shows 0.005\"/ft slope over 10 ft. Total rise?",opts:["0.005\"","0.050\"","0.500\"","0.025\""],ans:1,exp:"Rise = slope/ft × feet = 0.005 × 10 = 0.050\". Essential for leveling machine bases.",type:"critical"},
  { id:21,cat:"A",q:"What layout tool scribes circles and arcs on metal?",opts:["Prick punch","Divider or trammel","Center punch","Scriber"],ans:1,exp:"Dividers for small radii, trammels for large radii — both scribe accurate circles on metal workpieces.",type:"recall"},
  { id:22,cat:"A",q:"A dial bore gauge primarily measures:",opts:["Outside diameters","Internal bore diameters and taper","Shaft runout","Surface finish"],ans:1,exp:"Dial bore gauges measure bore IDs with high precision and detect taper, out-of-round, and bell-mouth conditions.",type:"recall"},
  { id:23,cat:"A",q:"Which tool checks flatness of a surface plate?",opts:["Feeler gauge alone","Precision straight edge with feeler gauges","Dial indicator","Height gauge"],ans:1,exp:"Place straight edge on surface, use feeler gauges to detect gaps — standard method for flatness verification.",type:"procedure"},
  { id:24,cat:"A",q:"Welding electrode E7018 — what does '8' mean?",opts:["High-cellulose potassium","Low-hydrogen iron powder coating","Rutile dioxide","High iron oxide"],ans:1,exp:"E7018: E=electrode, 70=70ksi tensile, 1=all positions, 8=low-hydrogen iron powder. Preferred for structural work.",type:"recall"},
  { id:25,cat:"A",q:"For oxy-fuel cutting 1\" mild steel, which flame type?",opts:["Carburizing","Neutral flame","Oxidizing","Reducing"],ans:1,exp:"Neutral flame (equal O₂ and acetylene) preheats to cherry red, then the cutting oxygen jet oxidizes and blows molten metal.",type:"procedure"},

  // ═══ BLOCK B: Rigging, Hoisting & Moving (17) ═══
  { id:26,cat:"B",q:"What is the sling stress formula?",opts:["(L ÷ H × W) ÷ Number of legs","(W × H) ÷ L","W ÷ Number of slings","W × angle factor"],ans:0,exp:"Sling stress = (Length ÷ Height × Weight) ÷ Legs. As angle from vertical increases, stress increases dramatically.",type:"critical"},
  { id:27,cat:"B",q:"10,000 lb load, 2-leg sling at 60° from horizontal. Load per leg?",opts:["5,000 lbs","5,774 lbs","7,071 lbs","10,000 lbs"],ans:1,exp:"At 60° from horizontal (30° from vertical): (10,000 ÷ 2) ÷ cos(30°) = 5000 ÷ 0.866 = 5,774 lbs.",type:"critical"},
  { id:28,cat:"B",q:"WLL of 1/2\" diameter 6×19 wire rope?",opts:["1 ton","2 tons","4 tons","8 tons"],ans:1,exp:"WLL = d² × 8 = (0.5)² × 8 = 2 tons. This formula is provided on the Red Seal exam.",type:"critical"},
  { id:29,cat:"B",q:"Wire rope clips required for 3/4\" diameter rope?",opts:["3","4","5","6"],ans:1,exp:"For ≤7/8\" rope: clips = 3 × diameter(in eighths fraction math) + 1. For 3/4\" = 4 clips. Formula on exam.",type:"critical"},
  { id:30,cat:"B",q:"Correct spacing for wire rope clips?",opts:["4 × rope diameter","6 × rope diameter","8 × rope diameter","3 × rope diameter"],ans:1,exp:"Clip spacing = 6 × rope diameter. For 1/2\" rope: 6 × 0.5 = 3\" between clips.",type:"recall"},
  { id:31,cat:"B",q:"What does a 'critical lift' plan require?",opts:["Verbal agreement","Written plan reviewed by competent person","Only crane cert","Supervisor verbal OK"],ans:1,exp:"Critical lifts: formal written plan with load weight, crane capacity at radius, rigging, ground conditions, weather — reviewed by competent person.",type:"procedure"},
  { id:32,cat:"B",q:"Weight of steel plate 4' × 8' × 1\" thick? (steel = 490 lbs/ft³)",opts:["1,307 lbs","1,044 lbs","980 lbs","1,568 lbs"],ans:0,exp:"Volume = 4 × 8 × (1/12) = 2.667 ft³ → 2.667 × 490 = 1,307 lbs. Convert 1\" to 1/12 ft.",type:"critical"},
  { id:33,cat:"B",q:"When should tag lines be used during a lift?",opts:["Only loads over 5 tons","Always — to control rotation and swing","Only in wind","Only when signal person requests"],ans:1,exp:"Tag lines control load rotation/swing and keep workers safely away from suspended loads. Required for every lift.",type:"recall"},
  { id:34,cat:"B",q:"Minimum recommended sling angle from horizontal?",opts:["30°","45°","60°","90°"],ans:2,exp:"60° minimum from horizontal. Below 60°, sling stress spikes and horizontal crushing forces become dangerous.",type:"recall"},
  { id:35,cat:"B",q:"As crane radius increases, what happens to capacity?",opts:["Increases","Decreases","Stays same","Doubles"],ans:1,exp:"Capacity decreases with increased radius due to greater tipping moment. Always check load chart at actual working radius.",type:"recall"},
  { id:36,cat:"B",q:"Hand signal for 'HOIST' (raise)?",opts:["Arm extended, thumb up","Small circular motion, finger pointing up","Both fists, thumbs up","Arm horizontal, palm down"],ans:1,exp:"HOIST = small horizontal circular motion with index finger pointing up. Universal crane signal.",type:"recall"},
  { id:37,cat:"B",q:"Synthetic sling has visible cuts through 10% of width. Action?",opts:["Reduce load 10%","Remove from service and destroy","Wrap with tape","Continue if under 25% damage"],ans:1,exp:"Any visible damage → immediately remove and destroy to prevent reuse. No acceptable damage threshold.",type:"procedure"},
  { id:38,cat:"B",q:"Which hitch reduces sling capacity the most?",opts:["Vertical hitch","Basket hitch","Choker hitch","Bridle hitch"],ans:2,exp:"Choker hitch reduces capacity to ~75-80% due to sharp bend and crushing force at the choke point.",type:"recall"},
  { id:39,cat:"B",q:"Using come-alongs horizontally — what must be verified?",opts:["Load is painted","Anchor capacity, pull direction, rated capacity","Only correct size","3+ workers present"],ans:1,exp:"Verify anchor point capacity, straight-line pull (no side loading), and come-along rated capacity for the task.",type:"procedure"},
  { id:40,cat:"B",q:"Proper wire rope sling storage?",opts:["Coiled on ground","Hung on rack, dry area, lubricated","Sealed plastic bag","Stacked pile"],ans:1,exp:"Hang vertically on rack in dry, ventilated area. Keep lubricated. Floor storage causes kinking and deterioration.",type:"procedure"},
  { id:41,cat:"B",q:"What must be checked on chain slings before each use?",opts:["Color coding only","Links for stretch, wear, gouges, cracks, twists","Master link only","Hooks only"],ans:1,exp:"Inspect ALL links for elongation (>5%), wear, gouges, cracks, twists. Check hooks and master links for damage.",type:"procedure"},
  { id:42,cat:"B",q:"A shackle screw pin's primary purpose?",opts:["Decorative finish","Securely close shackle body for load attachment","Wear indicator","Limit sling angle"],ans:1,exp:"Screw pin closes the shackle for secure sling/cable attachment. Must be fully seated and tightened.",type:"recall"},

  // ═══ BLOCK C: Mechanical Power Transmission (32) ═══
  { id:43,cat:"C",q:"Most common cause of electric motor failure?",opts:["Shaft misalignment","Bearing failure from improper lubrication","Voltage fluctuation","Manufacturing defect"],ans:1,exp:"Bearing failure is #1 — usually from improper lubrication (too much/little/wrong type), contamination, or misalignment.",type:"recall"},
  { id:44,cat:"C",q:"Diesel engine running rough with black smoke — likely cause?",opts:["Low coolant","Overfueling or restricted air intake","Low oil pressure","Faulty alternator"],ans:1,exp:"Black smoke = incomplete combustion from overfueling or restricted air. White = coolant intrusion. Blue = oil burning.",type:"critical"},
  { id:45,cat:"C",q:"Purpose of a flywheel on a prime mover?",opts:["Increase speed","Store rotational energy, smooth power pulses","Reduce startup vibration only","Connect to driven equipment"],ans:1,exp:"Flywheel stores kinetic energy between power strokes, smoothing pulsating torque for more constant speed output.",type:"recall"},
  { id:46,cat:"C",q:"Replacing an electric motor — which nameplate data must match?",opts:["Color and weight","HP, RPM, voltage, frame size, enclosure type","Only horsepower","Brand only"],ans:1,exp:"Match: HP, RPM, voltage, phase, frame size (mounting dims), enclosure (TEFC, ODP), and service factor.",type:"procedure"},
  { id:47,cat:"C",q:"Which prime mover converts fluid pressure to rotational energy?",opts:["Electric motor","Hydraulic motor","ICE engine","Air compressor"],ans:1,exp:"Hydraulic motor converts hydraulic pressure/flow into rotational mechanical energy.",type:"recall"},
  { id:48,cat:"C",q:"Purpose of pre-loading tapered roller bearings?",opts:["Increase friction","Eliminate internal clearance, ensure contact","Easier installation","Reduce load capacity"],ans:1,exp:"Pre-load eliminates clearance, ensures full roller contact, prevents skidding, improves rigidity and accuracy.",type:"recall"},
  { id:49,cat:"C",q:"Fretting corrosion at bearing seat — likely cause?",opts:["Excessive speed","Loose fit between inner race and shaft","Over-lubrication","Shaft too hard"],ans:1,exp:"Fretting (reddish-brown oxidation) = micro-movement from too-loose fit. Fix with proper interference fit.",type:"critical"},
  { id:50,cat:"C",q:"What seal type prevents oil leakage along a rotating shaft?",opts:["O-ring","Lip seal (oil seal)","Gasket","Mechanical face seal"],ans:1,exp:"Lip seals with spring-loaded lip contact the shaft surface. For higher pressure, mechanical face seals are used.",type:"recall"},
  { id:51,cat:"C",q:"When removing a bearing with a puller, grip which part?",opts:["Cage/retainer","Inner race","Outer race","Rolling elements"],ans:1,exp:"Pull from the inner race — that's where the interference fit is. Pulling outer race or cage damages the bearing.",type:"procedure"},
  { id:52,cat:"C",q:"Which bearing handles both radial and thrust loads?",opts:["Cylindrical roller","Angular contact bearing","Needle roller","Thrust bearing"],ans:1,exp:"Angular contact bearings have angled raceways for combined radial + axial loads. Tapered rollers also work.",type:"recall"},
  { id:53,cat:"C",q:"Shaft journal shows blue discoloration. Indicates?",opts:["Normal oxidation","Overheating from insufficient lubrication","Properly hardened","Chemical contamination"],ans:1,exp:"Blue = overheated (>500°F/260°C). Usually from lost lubrication. Metallurgy may be altered — shaft may need replacement.",type:"critical"},
  { id:54,cat:"C",q:"Which coupling compensates for angular, parallel, and axial misalignment?",opts:["Rigid coupling","Jaw (spider) coupling","Disc coupling","Gear coupling"],ans:1,exp:"Jaw couplings with elastomeric spider handle all three misalignment types plus vibration dampening.",type:"recall"},
  { id:55,cat:"C",q:"Clutch disc contaminated with oil — what happens?",opts:["Friction increases","Clutch slips, reduced torque transmission","No effect","Faster engagement"],ans:1,exp:"Oil reduces friction coefficient → slippage → can't transmit full torque. Replace disc, fix oil leak source.",type:"critical"},
  { id:56,cat:"C",q:"Disc brake not releasing fully — most likely cause?",opts:["Pads too thick","Return spring broken or weak","Disc too clean","Caliper too tight"],ans:1,exp:"Weak/broken return spring → pads drag on disc → heat buildup, premature wear, energy loss.",type:"critical"},
  { id:57,cat:"C",q:"Purpose of a grid coupling?",opts:["Connect identical shafts only","Transmit torque, absorb shock, accommodate misalignment","Lock shafts permanently","Increase speed"],ans:1,exp:"Grid couplings use a tapered metallic grid spring that flexes to absorb shock and accommodate slight misalignment.",type:"recall"},
  { id:58,cat:"C",q:"How is roller chain slack measured?",opts:["Counting loose links","Measuring deflection at mid-span","Pulling chain tight","Weighing the chain"],ans:1,exp:"Measure sag at mid-span between sprockets. Proper slack = 2-4% of center distance for horizontal runs.",type:"procedure"},
  { id:59,cat:"C",q:"V-belt drive slipping — first action?",opts:["Replace all belts","Check and adjust belt tension","Increase motor speed","Add belt dressing"],ans:1,exp:"Check tension first — most common cause. Never use belt dressing (damages belts). If tension OK, check sheave/belt wear.",type:"procedure"},
  { id:60,cat:"C",q:"Multi-belt V-belt drive — when replacing belts:",opts:["Replace only worn ones","Replace ALL as a matched set","Mix old and new","Use any that fit"],ans:1,exp:"Always replace ALL belts. Mixing causes uneven loading — worn belts ride lower in groove → rapid new belt failure.",type:"procedure"},
  { id:61,cat:"C",q:"What causes chain 'stretch'?",opts:["Steel links elongate","Wear on pins and bushings","Temperature expansion","Improper lubrication only"],ans:1,exp:"'Stretch' = accumulated wear on pins/bushings at each joint, not steel elongation. Replace at 3% over nominal.",type:"recall"},
  { id:62,cat:"C",q:"What gear type transmits motion between perpendicular shafts?",opts:["Spur gears","Bevel gears","Helical gears","Herringbone gears"],ans:1,exp:"Bevel gears transmit power between intersecting shafts (typically 90°). Worm gears also work at 90° but don't intersect.",type:"recall"},
  { id:63,cat:"C",q:"Gear reducer: 1750 RPM input, 5:1 ratio. Output speed?",opts:["8750 RPM","350 RPM","1750 RPM","175 RPM"],ans:1,exp:"Output = Input ÷ Ratio = 1750 ÷ 5 = 350 RPM. Speed decreases, torque increases.",type:"critical"},
  { id:64,cat:"C",q:"Pitting pattern on gear teeth indicates?",opts:["Proper break-in","Surface fatigue from overloading","Normal wear","Teeth too hard"],ans:1,exp:"Pitting = surface fatigue from repeated high contact stresses. Caused by overloading, misalignment, or poor lubrication.",type:"critical"},
  { id:65,cat:"C",q:"After replacing gears, what must be checked?",opts:["New gear dimensions only","Backlash, tooth contact pattern, lubrication","Oil level only","Gear color match"],ans:1,exp:"Check backlash with feeler gauge/dial indicator, verify contact pattern with marking compound, ensure proper lube.",type:"procedure"},
  { id:66,cat:"C",q:"Gear mesh frequency formula?",opts:["RPM × number of teeth","RPM ÷ number of teeth","Teeth ÷ RPM","RPM² × teeth"],ans:0,exp:"Gear mesh frequency = RPM × teeth. Used in vibration analysis to identify gear problems. On the Red Seal exam.",type:"recall"},
  { id:67,cat:"C",q:"Most accurate shaft alignment method?",opts:["Straight edge and feeler gauge","Reverse dial indicator","Laser alignment","Visual alignment"],ans:2,exp:"Laser = most accurate, fastest, most repeatable. Reverse dial indicator is also very accurate. Straight edge for rough only.",type:"recall"},
  { id:68,cat:"C",q:"Two types of shaft misalignment?",opts:["Vertical and horizontal","Angular and offset (parallel)","Axial and radial","Linear and rotational"],ans:1,exp:"Angular (shafts at an angle) and offset/parallel (shafts parallel but not collinear). Most real cases combine both.",type:"recall"},
  { id:69,cat:"C",q:"Dial indicator: 0.010\" at 12 o'clock, 0.002\" at 6 o'clock. Offset?",opts:["0.010\"","0.004\"","0.012\"","0.008\""],ans:1,exp:"Offset = (Top – Bottom) ÷ 2 = (0.010 – 0.002) ÷ 2 = 0.004\". Divide TIR by 2 for actual centerline offset.",type:"critical"},
  { id:70,cat:"C",q:"Why account for thermal growth during alignment?",opts:["Makes bolts tighter","Machines change position at operating temperature","Only affects foundation","Negligible in industry"],ans:1,exp:"Shafts, housings, supports expand with heat, shifting centerlines. Cold alignment must compensate for expected thermal growth.",type:"recall"},
  { id:71,cat:"C",q:"What corrects soft foot during alignment?",opts:["Hammer","Shims under machine feet","Level","Torque wrench only"],ans:1,exp:"Precision shims under affected foot ensure all feet bear evenly. Soft foot distorts the frame, preventing accurate alignment.",type:"procedure"},
  { id:72,cat:"C",q:"Alignment shim calculation uses which variables?",opts:["Shaft diameter only","Gap, distance between supports, distance to correction","Dial reading only","Coupling diameter and torque"],ans:1,exp:"Shims = G × (A/B) where G = gap/offset, A = distance to correction, B = distance between measurement points.",type:"critical"},
  { id:73,cat:"C",q:"A fluid coupling showing excess heat and reduced efficiency needs:",opts:["Paint touch-up","Check fluid level, type, and internal wear","Speed increase","Nothing, this is normal"],ans:1,exp:"Check fluid level, verify correct fluid type, inspect for internal component wear. Normal operation = smooth, minimal heat.",type:"critical"},
  { id:74,cat:"C",q:"Timing belt alignment requires:",opts:["Angular only","Both parallel and angular alignment","No alignment needed","Axial only"],ans:1,exp:"Both parallel and angular alignment are required. Misalignment causes uneven wear, tracking issues, premature failure.",type:"procedure"},

  // ═══ BLOCK D: Material Handling / Process Systems (24) ═══
  { id:75,cat:"D",q:"Before entering a robotic work cell for maintenance?",opts:["Slow robot to min speed","Full lockout/tagout, isolate all energy","Unplug teach pendant only","Inform operator"],ans:1,exp:"Full LOTO of all energy sources. Robots can move unexpectedly if not completely de-energized.",type:"procedure"},
  { id:76,cat:"D",q:"Centrifugal fan vibrating excessively — most likely cause?",opts:["Motor too powerful","Impeller imbalance from material buildup","Ductwork too long","Inlet damper open"],ans:1,exp:"Material buildup on impeller blades causes imbalance and vibration. Regular cleaning/balancing is essential PM.",type:"critical"},
  { id:77,cat:"D",q:"What determines airflow direction in a centrifugal fan?",opts:["Motor speed","Scroll housing design","Blade thickness","Shaft diameter"],ans:1,exp:"The scroll (volute) housing: air enters axially, is accelerated by impeller, discharged tangentially from scroll outlet.",type:"recall"},
  { id:78,cat:"D",q:"Replacing fan bearings — what must be checked?",opts:["Bearing size only","Fit, shaft condition, housing bore, alignment","Lubrication type only","Motor amps only"],ans:1,exp:"Check: bearing-to-shaft fit, shaft condition (no scoring), housing bore, seal condition, post-install alignment.",type:"procedure"},
  { id:79,cat:"D",q:"Axial fans are used when:",opts:["High pressure needed","High volume at low pressure needed","Air must be filtered","Hot gases must move"],ans:1,exp:"Axial fans = high volume, low pressure (ventilation/cooling). Centrifugal fans develop higher pressures for duct systems.",type:"recall"},
  { id:80,cat:"D",q:"Centrifugal pump cavitating — most likely cause?",opts:["Discharge pressure too low","Insufficient NPSHa (suction restriction)","Impeller too large","Motor running backwards"],ans:1,exp:"Cavitation: NPSHa < NPSHr. Causes: clogged suction, high suction lift, high fluid temp, restricted suction piping.",type:"critical"},
  { id:81,cat:"D",q:"Which pump type uses an impeller?",opts:["Gear pump","Centrifugal pump","Diaphragm pump","Piston pump"],ans:1,exp:"Centrifugal pumps use rotating impeller → velocity → volute converts to pressure. Others are positive displacement.",type:"recall"},
  { id:82,cat:"D",q:"How tight should pump packing be?",opts:["As tight as possible","Allow slight drip for cooling/lubrication","Hand tight only","No adjustment needed"],ans:1,exp:"Must drip slightly (few drops/min) for cooling and lubrication. Over-tight = burned packing, scored sleeve.",type:"procedure"},
  { id:83,cat:"D",q:"Positive displacement pumps deliver:",opts:["Variable flow","Constant flow per revolution","Constant pressure","Variable pressure"],ans:1,exp:"PD pumps deliver fixed volume per revolution regardless of discharge pressure. That's why they need pressure relief protection.",type:"recall"},
  { id:84,cat:"D",q:"Most common cause of mechanical seal failure?",opts:["Wrong material","Dry running (no lubrication between faces)","Pump too large","Bolt torque too high"],ans:1,exp:"Dry running is #1 killer. The thin fluid film between seal faces provides lubrication + cooling. Even brief dry running destroys faces.",type:"critical"},
  { id:85,cat:"D",q:"Excessive discharge temp in reciprocating compressor — causes?",opts:["Oversized motor","Worn rings, broken valves, insufficient cooling","Inlet filter too clean","Tank too large"],ans:1,exp:"Worn piston rings (recirculation), broken valves, fouled cooler, low oil. Can cause oil ignition from carbon buildup.",type:"critical"},
  { id:86,cat:"D",q:"Purpose of aftercooler on compressed air system?",opts:["Increase pressure","Cool air and remove moisture","Filter air","Regulate flow"],ans:1,exp:"Reduces compressed air temp → water condenses out → separator removes liquid. Protects downstream equipment from moisture.",type:"recall"},
  { id:87,cat:"D",q:"Screw compressor oil separator — excessive carryover. Check?",opts:["Motor bearings","Separator element condition and oil level","Inlet filter only","Discharge piping"],ans:1,exp:"Check: element (clogged/damaged), oil level, minimum pressure valve, oil return line for blockage.",type:"procedure"},
  { id:88,cat:"D",q:"How often should compressor safety valves be tested?",opts:["Once per year","Per manufacturer and jurisdictional regulations","Only when faulty","Every 5 years"],ans:1,exp:"Test per manufacturer AND local jurisdictional regulations (often annually or scheduled shutdowns). Some require certified testing.",type:"procedure"},
  { id:89,cat:"D",q:"Two-stage reciprocating compressor — purpose of intercooler?",opts:["Increase HP","Cool air between stages, improve efficiency","Filter contaminants","Reduce noise"],ans:1,exp:"Intercooler cools air between stages. Cooler = denser = less work to compress further. Improves efficiency, reduces discharge temp.",type:"recall"},
  { id:90,cat:"D",q:"Pipe schedule number indicates:",opts:["Pipe length","Wall thickness","Outside diameter","Thread count"],ans:1,exp:"Schedule (40, 80, etc.) = wall thickness for given nominal size. Higher schedule = thicker = higher pressure rating.",type:"recall"},
  { id:91,cat:"D",q:"Purpose of expansion joint in piping?",opts:["Filter contaminants","Absorb thermal expansion/contraction","Increase pressure","Change flow direction"],ans:1,exp:"Absorbs thermal growth, vibration, movement. Without them, thermal forces damage supports, flanges, equipment.",type:"recall"},
  { id:92,cat:"D",q:"Pressure vessel pitting corrosion — safety determination based on:",opts:["Visual only","Remaining wall thickness vs minimum design requirement","Vessel age","Corrosion color"],ans:1,exp:"Remaining wall must meet ASME minimum. UT thickness testing measures remaining wall. Below minimum → repair/retire.",type:"critical"},
  { id:93,cat:"D",q:"Conveyor belt tracking to one side — likely cause?",opts:["Belt too long","Uneven tension or misaligned idlers","Load too heavy","Motor too fast"],ans:1,exp:"Mistracking: unequal tension, misaligned idlers, worn crowned pulleys, uneven loading, or frame distortion.",type:"critical"},
  { id:94,cat:"D",q:"Purpose of a belt scraper (cleaner) on conveyor?",opts:["Increase speed","Remove carryback from return side","Increase friction","Align the belt"],ans:1,exp:"Removes residual material (carryback) to prevent buildup on return idlers, mistracking, and cleanup issues.",type:"recall"},
  { id:95,cat:"D",q:"Screw conveyor vibrating with grinding noise — inspect:",opts:["Motor nameplate","Flights, trough wear, hanger bearings","Drive belt only","Discharge opening only"],ans:1,exp:"Check: worn flights contacting trough, worn liner, seized hanger bearings, bent screw sections, foreign objects.",type:"procedure"},
  { id:96,cat:"D",q:"Best conveyor for moving bulk materials vertically?",opts:["Belt conveyor","Bucket elevator","Roller conveyor","Chain conveyor"],ans:1,exp:"Bucket elevators scoop at boot, carry up, discharge at head by centrifugal force. Purpose-built for vertical bulk handling.",type:"recall"},
  { id:97,cat:"D",q:"Conveyor belt tensioning — adjustment made at:",opts:["Head pulley","Tail pulley or take-up device","Belt midpoint","Nearest idler"],ans:1,exp:"Tension at tail pulley (screw take-up) or gravity take-up. Allows tension and tracking adjustment. Head pulleys are fixed.",type:"procedure"},
  { id:98,cat:"D",q:"Installing flanged pipe gasket — use as lubricant:",opts:["Motor oil","Compatible anti-seize compound","WD-40","Silicone spray"],ans:1,exp:"Use anti-seize/gasket compound compatible with process fluid, temperature, and pressure. Wrong lube attacks gasket or contaminates process.",type:"procedure"},

  // ═══ BLOCK E: Fluid Power Systems (21) ═══
  { id:99,cat:"E",q:"Hydraulic force formula?",opts:["Force = Flow × Speed","Force = Pressure × Area","Force = Volume ÷ Time","Force = Pressure ÷ Area"],ans:1,exp:"F = P × A. Fundamental hydraulic formula. Area = piston area (π × r²). On the Red Seal exam.",type:"recall"},
  { id:100,cat:"E",q:"Hydraulic system running hot — check first:",opts:["Fluid color","Oil level, cooler, relief valve, internal leakage","Pump speed only","Motor only"],ans:1,exp:"Causes: low oil, clogged cooler, relief set too low, internal leakage (worn pump/cylinders/valves), contaminated/wrong oil.",type:"critical"},
  { id:101,cat:"E",q:"Purpose of hydraulic accumulator?",opts:["Filter oil","Store pressurized fluid for peaks, absorb shock","Increase pump speed","Cool oil"],ans:1,exp:"Stores energy for peak demands, absorbs shock, maintains pressure, compensates for leakage.",type:"recall"},
  { id:102,cat:"E",q:"Hydraulic cylinder drifting under load — cause?",opts:["Pump worn","Internal seal leakage past piston","Oil too cold","Reservoir too large"],ans:1,exp:"Internal leakage past piston seals lets oil bypass. External rod seal leaks cause fluid loss, not drift.",type:"critical"},
  { id:103,cat:"E",q:"Flow control valve regulates:",opts:["System pressure","Actuator speed","Fluid temperature","Pump RPM"],ans:1,exp:"Flow control = flow rate to actuators = speed. Relief valves control pressure. Flow = speed; Pressure = force.",type:"recall"},
  { id:104,cat:"E",q:"Hydraulic schematic: square with diagonal arrow =",opts:["Fixed displacement pump","Variable displacement pump/motor","Check valve","Filter"],ans:1,exp:"Diagonal arrow through pump/motor symbol = variable displacement. Without arrow = fixed displacement.",type:"recall"},
  { id:105,cat:"E",q:"Which valve controls direction of fluid to actuators?",opts:["Relief valve","Directional control valve","Flow control","Sequence valve"],ans:1,exp:"DCVs direct flow to/from actuators — determining cylinder extend/retract or motor rotation direction.",type:"recall"},
  { id:106,cat:"E",q:"Noisy pump + foamy reservoir oil — cause?",opts:["Oil too thick","Air entering suction line (aeration)","Pump too slow","Filter too restrictive"],ans:1,exp:"Foamy oil + noise = air intrusion. Causes: low oil, suction leak, damaged shaft seal, return line above oil level. Destroys pump rapidly.",type:"critical"},
  { id:107,cat:"E",q:"Piston area of 4\" bore hydraulic cylinder?",opts:["12.57 sq.in.","16 sq.in.","25.13 sq.in.","8 sq.in."],ans:0,exp:"A = π × r² = 3.1416 × (2)² = 12.57 sq.in. Bore = 4\" diameter, radius = 2\".",type:"critical"},
  { id:108,cat:"E",q:"Why never pressurize hydraulic system with compressed air?",opts:["Air too clean","Explosive failure — air stores much more energy","Air reduces pressure","Air is cheaper"],ans:1,exp:"Compressed air is highly compressible and stores enormous energy. Container failure = explosive release. Hydraulic fluid is nearly incompressible.",type:"recall"},
  { id:109,cat:"E",q:"When changing hydraulic filters — prevent contamination by:",opts:["Work fast","Clean area, pre-fill new filter, minimize open time","Wipe with rag","Only change when hot"],ans:1,exp:"Clean housing, pre-fill filter with clean fluid, minimize open time, use lint-free materials. Contamination = #1 system killer.",type:"procedure"},
  { id:110,cat:"E",q:"Most common cause of hydraulic system failure?",opts:["Pump defects","Fluid contamination (dirt, water, air)","Electrical issues","Cylinder rod damage"],ans:1,exp:"70-80% of failures from contamination. Proper filtration, clean fill procedures, and oil analysis are essential.",type:"recall"},
  { id:111,cat:"E",q:"Standard operating pressure for industrial pneumatic systems?",opts:["200 PSI","80-100 PSI (550-690 kPa)","30-40 PSI","150-175 PSI"],ans:1,exp:"Most industrial pneumatics: 80-100 PSI. Higher pressures increase energy costs without proportional benefit.",type:"recall"},
  { id:112,cat:"E",q:"What is an FRL unit?",opts:["Flow Rate Limiter","Filter, Regulator, Lubricator","Frequency Response Leveler","Fluid Return Line"],ans:1,exp:"FRL conditions compressed air: filter contaminants/moisture, regulate pressure, add oil mist for tool lubrication.",type:"recall"},
  { id:113,cat:"E",q:"Pneumatic cylinder moving slowly — check:",opts:["Bore size","Flow control, supply pressure, exhaust restrictions","Paint condition","Rod thread size"],ans:1,exp:"Check flow controls, supply pressure, exhaust restrictions, internal seal wear, undersized supply lines.",type:"procedure"},
  { id:114,cat:"E",q:"Danger of non-rated components in compressed air systems?",opts:["Reduced air quality","Catastrophic burst failure under pressure","Increased noise only","Slight efficiency loss"],ans:1,exp:"Non-rated components can burst catastrophically. All pneumatic components must be rated for system max pressure.",type:"recall"},
  { id:115,cat:"E",q:"Vacuum system losing suction — inspect:",opts:["Motor speed only","All connections for leaks, filter, pump wear","Reservoir only","Gauge color"],ans:1,exp:"Check: fittings/hoses/gaskets for leaks, filter/strainer blockage, vacuum pump wear (vanes, seals), check valve function.",type:"procedure"},
  { id:116,cat:"E",q:"Quick exhaust valve function?",opts:["Increases supply pressure","Fast exhaust at actuator for higher speed","Filters air","Regulates pressure"],ans:1,exp:"Mounts on cylinder port, vents exhaust locally instead of through control valve — dramatically increases retraction speed.",type:"recall"},
  { id:117,cat:"E",q:"Why is water removal critical in pneumatics?",opts:["Increases pressure","Causes corrosion, washes lubrication, freezes","No effect","Only affects reservoir"],ans:1,exp:"Water: corrodes internals, washes away lube films, freezes in exhaust ports (valve failure), reduces equipment efficiency.",type:"recall"},
  { id:118,cat:"E",q:"Pneumatic valve actuated by electrical signal?",opts:["Manual valve","Solenoid valve","Pilot-operated check","Needle valve"],ans:1,exp:"Solenoid valves use electromagnetic coil to shift spool, directing air flow. Enables PLC/automated control.",type:"recall"},
  { id:119,cat:"E",q:"Hissing from a pneumatic cylinder indicates:",opts:["Normal operation","Air leak from seals, fittings, or connections","Excessive pressure","Proper lubrication"],ans:1,exp:"Hissing = air leak. Check piston/rod seals, fittings, connections. Use soapy water on external joints to locate.",type:"critical"},

  // ═══ BLOCK F: Preventive & Predictive Maintenance (16) ═══
  { id:120,cat:"F",q:"Primary goal of preventive maintenance?",opts:["Fix after breakdown","Prevent unexpected breakdowns, extend equipment life","Reduce staff","Track warranties"],ans:1,exp:"PM prevents unexpected failures through scheduled inspections, lubrication, adjustments, and component replacement.",type:"recall"},
  { id:121,cat:"F",q:"Vibration at 1× RPM with high amplitude indicates:",opts:["Bearing defect","Imbalance","Misalignment","Looseness"],ans:1,exp:"Dominant 1× RPM = mass imbalance. Misalignment shows 2× RPM. Bearings show at specific bearing frequencies.",type:"critical"},
  { id:122,cat:"F",q:"Infrared thermography in electrical systems detects:",opts:["Voltage levels","Hot spots from loose connections, overloads, failing parts","Wire color","Current direction"],ans:1,exp:"Detects abnormal heat from loose connections (high resistance), overloaded conductors, failing breakers — before failure or fire.",type:"recall"},
  { id:123,cat:"F",q:"Oil analysis reveals:",opts:["Oil color only","Wear metals, contamination, oil degradation","Viscosity only","Temperature only"],ans:1,exp:"Identifies: wear metals (Fe, Cu, Pb = component wear), contaminants (dirt, water), oil condition (viscosity, oxidation, additives).",type:"recall"},
  { id:124,cat:"F",q:"Vibration spike at BPFO frequency — what is it?",opts:["Ball Point Frequency Oscillation","Ball Pass Frequency Outer Race — outer race defect","Bearing Peak Frequency Output","Basic Pump Frequency"],ans:1,exp:"BPFO = Ball Pass Frequency Outer race. Spike = defect (spall, crack, pit) on outer bearing race. BPFI = inner race.",type:"critical"},
  { id:125,cat:"F",q:"Over-greasing a bearing causes:",opts:["Better protection","Excessive heat, premature failure from churning","No negative effect","Improved speed"],ans:1,exp:"Elements churn excess grease → heat → friction → grease breakdown → blown seals. Follow 1/3 fill rule.",type:"recall"},
  { id:126,cat:"F",q:"Ultrasonic testing in predictive maintenance detects:",opts:["Temperature","Early bearing wear, leaks, electrical discharge","Shaft speed","Alignment"],ans:1,exp:"Detects: early bearing wear (before vibration can), air/gas/vacuum leaks, steam trap issues, electrical arcing/corona.",type:"recall"},
  { id:127,cat:"F",q:"A CMMS is used for:",opts:["Tracking parts only","PM scheduling, work orders, inventory, analysis","Sending emails only","Recording downtime only"],ans:1,exp:"CMMS manages: PM scheduling, work orders, spare parts, equipment history, labor tracking, maintenance cost analysis.",type:"recall"},
  { id:128,cat:"F",q:"Correct procedure for oil analysis sampling:",opts:["Dip cup into reservoir","Clean sampling port, system at operating temp, circulated","Take from drain plug","Sample when cold/settled"],ans:1,exp:"Sample from dedicated port at operating temp with oil circulated. Use clean bottles. Avoid drains (settled contaminants).",type:"procedure"},
  { id:129,cat:"F",q:"Vibration pattern indicating mechanical looseness:",opts:["Single 1× peak","Multiple harmonics (1×, 2×, 3×, 4×...)","Random broadband only","Single high-frequency peak"],ans:1,exp:"Looseness generates multiple harmonics and sub-harmonics. Creates 'picket fence' appearance in spectrum.",type:"critical"},
  { id:130,cat:"F",q:"Thermal expansion formula (on Red Seal exam):",opts:["Temp × Mass","ΔT × Length × Coefficient of expansion","Pressure × Volume","Heat × Density"],ans:1,exp:"Expansion = ΔT × L × α. Each material has its own coefficient. Critical for piping, shafts, machine bases.",type:"recall"},
  { id:131,cat:"F",q:"During commissioning, verify before startup:",opts:["Power connected only","Alignment, lubrication, rotation, safety devices, connections","Paint finish only","Nameplate only"],ans:1,exp:"Checklist: alignment, fluids filled, rotation direction (bump test), guards, safety devices, connections tight, follow manufacturer procedure.",type:"procedure"},
  { id:132,cat:"F",q:"Decommissioning — hazardous fluids must be:",opts:["Drained on ground","Collected, labeled, disposed per environmental regs","Left in machine","Poured down drain"],ans:1,exp:"All hazardous fluids properly collected, labeled, and disposed per provincial/federal environmental regulations. Improper disposal is illegal.",type:"procedure"},
  { id:133,cat:"F",q:"Newly installed pump vibrates excessively — check first:",opts:["Model number","Alignment, foundation bolts, piping strain, rotation","Flow rate only","Paint"],ans:1,exp:"First: shaft alignment (most common cause), foundation bolts, piping strain (forces on flanges), rotation direction, priming.",type:"procedure"},
  { id:134,cat:"F",q:"Documentation to update after commissioning:",opts:["Nothing","Equipment records, PM schedules, parts lists, as-built drawings","Purchase order only","Warranty card only"],ans:1,exp:"Update: equipment register, PM schedules in CMMS, spare parts, as-built drawings, alignment records, baseline readings.",type:"procedure"},
  { id:135,cat:"F",q:"'Bump test' during commissioning verifies:",opts:["Load capacity","Correct rotation direction of motors/pumps","Structural integrity","Paint adhesion"],ans:1,exp:"Briefly energizes motor to check rotation before full speed. Wrong rotation destroys pumps, fans, compressors instantly.",type:"procedure"},
];

// ─── UTILITIES ──────────────────────────────────────────────
const shuffle = (a) => { const b=[...a]; for(let i=b.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[b[i],b[j]]=[b[j],b[i]];} return b; };
// Randomize each question's answer positions (banks were authored with the correct option
// almost always in slot B). Shuffle by index so duplicate option text can't break the remap.
const shuffleOpts = (q) => { const order = shuffle(q.opts.map((_, i) => i)); return { ...q, opts: order.map(i => q.opts[i]), ans: order.indexOf(q.ans) }; };
const hexRgb = (h) => { const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16); return `${r},${g},${b}`; };
const fmtTime = (s) => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,"0")}`;

// ─── STYLES ─────────────────────────────────────────────────
const T = {
  bg: "#07090f",
  bg2: "#0d1117",
  bg3: "#161b22",
  surface: "rgba(255,255,255,0.03)",
  border: "rgba(255,255,255,0.08)",
  text: "#e6edf3",
  text2: "#8b949e",
  accent: "#ff6b35",
  accent2: "#ffa726",
  green: "#2ea043",
  red: "#f85149",
  font: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', monospace",
  radius: 12,
};

// ─── MAIN APP ───────────────────────────────────────────────
export default function TradePrep() {
  const [page, setPage] = useState("landing");
  // Optimistic: treat stored token as subscribed until server says otherwise
  const [sub, setSub] = useState(() => {
    if (typeof window === "undefined") return false;
    return !!localStorage.getItem("rsp_token");
  });
  const [trade, setTrade] = useState(null);
  const [showActivate, setShowActivate]     = useState(false);
  const [activateEmail, setActivateEmail]   = useState("");
  const [activateLoading, setActivateLoading] = useState(false);
  const [activateError, setActivateError]   = useState("");
  const [activateSent, setActivateSent]     = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  // Annual plan appears once NEXT_PUBLIC_ANNUAL_PRICE (+ STRIPE_PRICE_ID_ANNUAL) is configured
  const ANNUAL_PRICE = process.env.NEXT_PUBLIC_ANNUAL_PRICE;
  const [plan, setPlan] = useState("monthly");
  const [showWrong, setShowWrong] = useState(false);
  const [quiz, setQuiz] = useState(null); // { questions, idx, selected, answered, score, answers, timer }
  const [chat, setChat] = useState({ open: false, messages: [], input: "", loading: false });
  const [stats, setStats] = useState({ sessions: 0, attempted: 0, correct: 0, best: 0 });
  const [hovered, setHovered] = useState(null);
  // ─── ACCOUNTS (Supabase magic-link + cross-device progress) ───
  const [authUser, setAuthUser]   = useState(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authSent, setAuthSent]   = useState(false);
  const [authBusy, setAuthBusy]   = useState(false);
  const [showSignIn, setShowSignIn] = useState(false);
  const [authErr, setAuthErr]     = useState("");

  // ─── SPACED REPETITION & STREAK ───────────────────────────
  const [wrongBank, setWrongBank] = useState(() => {
    if (typeof window === "undefined") return {};
    try { return JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}"); } catch { return {}; }
  });
  const [streak, setStreak] = useState(() => {
    if (typeof window === "undefined") return { days: 0, last: "" };
    try { return JSON.parse(localStorage.getItem("rsp_streak") || '{"days":0,"last":""}'); } catch { return { days: 0, last: "" }; }
  });
  const updateStreak = () => {
    const today = new Date().toISOString().slice(0, 10);
    setStreak(s => {
      if (s.last === today) return s;
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      const ns = { days: s.last === yesterday ? s.days + 1 : 1, last: today };
      localStorage.setItem("rsp_streak", JSON.stringify(ns));
      return ns;
    });
  };
  const saveWrong = (tradeId, answers, questions) => {
    const bank = JSON.parse(localStorage.getItem("rsp_wrong_" + tradeId) || "{}");
    answers.filter(a => !a.ok).forEach(a => {
      bank[a.qId] = (bank[a.qId] || 0) + 1;
    });
    // Remove questions answered correctly
    answers.filter(a => a.ok).forEach(a => {
      if (bank[a.qId]) { bank[a.qId]--; if (bank[a.qId] <= 0) delete bank[a.qId]; }
    });
    localStorage.setItem("rsp_wrong_" + tradeId, JSON.stringify(bank));
    setWrongBank(bank);
  };
  const getWeakCats = () => {
    const allQs = getQuestions();
    const cats = getCategories();
    const key = "rsp_catperf_" + (trade?.id || "");
    try { 
      const perf = JSON.parse(localStorage.getItem(key) || "{}");
      return cats.map(c => ({
        ...c, pct: perf[c.id] ? Math.round((perf[c.id].ok / perf[c.id].total) * 100) : -1,
        total: perf[c.id]?.total || 0, ok: perf[c.id]?.ok || 0
      })).filter(c => c.total > 0).sort((a, b) => a.pct - b.pct);
    } catch { return []; }
  };
  const saveCatPerf = (tradeId, answers, questions) => {
    const key = "rsp_catperf_" + tradeId;
    const perf = JSON.parse(localStorage.getItem(key) || "{}");
    answers.forEach(a => {
      const q = questions.find(qq => qq.id === a.qId);
      if (!q) return;
      if (!perf[q.cat]) perf[q.cat] = { ok: 0, total: 0 };
      perf[q.cat].total++;
      if (a.ok) perf[q.cat].ok++;
    });
    localStorage.setItem(key, JSON.stringify(perf));
  };
  const timerRef = useRef(null);
  const chatEndRef = useRef(null);

  // Load stats + verify subscription server-side
  useEffect(() => {
    (async () => {
      try {
        const raw = localStorage.getItem("tp-stats");
        if (raw) setStats(JSON.parse(raw));
      } catch(e) {}

      // Stripe success redirect → auto-activate from the checkout session,
      // falling back to the email-verification modal if that fails
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        if (params.get("sub") === "success") {
          const checkoutSessionId = params.get("session_id");
          window.history.replaceState({}, "", window.location.pathname);
          if (checkoutSessionId) {
            try {
              const res = await fetch("/api/verify-subscription", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ checkoutSessionId }),
              });
              const data = await res.json();
              if (data.subscribed && data.token) {
                localStorage.setItem("rsp_token", data.token);
                setSub(true);
                return;
              }
            } catch {}
          }
          setSub(false);
          localStorage.removeItem("rsp_token");
          setShowActivate(true);
          return;
        }
      }

      // Verify stored token against server
      const token = localStorage.getItem("rsp_token");
      if (token) {
        try {
          const res = await fetch("/api/verify-subscription", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
          });
          const data = await res.json();
          if (data.subscribed) {
            setSub(true);
            if (data.token) localStorage.setItem("rsp_token", data.token);
          } else {
            setSub(false);
            localStorage.removeItem("rsp_token");
          }
        } catch {
          // Network error — keep optimistic state, will re-check next load
        }
      }
    })();
  }, []);

  // Verify the signed-in Supabase session against Stripe; the server extracts
  // the email from the session token, so ownership of the address is proven.
  const verifySession = async () => {
    if (!supabase) return { subscribed: false };
    const { data } = await supabase.auth.getSession();
    const supabaseToken = data?.session?.access_token;
    if (!supabaseToken) return { subscribed: false };
    const res = await fetch("/api/verify-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ supabaseToken }),
    });
    return res.json();
  };

  // ─── Supabase auth + cross-device progress hydration ───
  useEffect(() => {
    if (!supabase) return;
    const hydrate = async (user) => {
      setAuthUser(user || null);
      if (!user) return;
      // Signed in with no access token → check Stripe for a subscription under
      // this (ownership-proven) email. Restores Pro on any device they sign into.
      if (!localStorage.getItem("rsp_token")) {
        const pending = localStorage.getItem("rsp_activate_pending");
        localStorage.removeItem("rsp_activate_pending");
        try {
          const data = await verifySession();
          if (data.subscribed && data.token) {
            localStorage.setItem("rsp_token", data.token);
            setSub(true);
            setShowActivate(false);
            setActivateSent(false);
          } else if (pending) {
            // They came back from an activation magic link but have no subscription
            setActivateSent(false);
            setShowActivate(true);
            setActivateError(`No active subscription found for ${user.email}. Retry with the email used at checkout, or contact support@redsealprep.pro`);
          }
        } catch {}
      }
      const cloud = await loadCloudProgress(user.id);
      if (cloud && Object.keys(cloud).length) {
        applyProgress(cloud);                       // pull their saved progress onto this device
        try { const s = localStorage.getItem("tp-stats"); if (s) setStats(JSON.parse(s)); } catch {}
        try { const st = localStorage.getItem("rsp_streak"); if (st) setStreak(JSON.parse(st)); } catch {}
        try { setWrongBank(JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}")); } catch {}
      } else {
        saveCloudProgress(user.id);                 // first sign-in: push whatever's already local
      }
    };
    supabase.auth.getSession().then(({ data }) => hydrate(data?.session?.user));
    const { data } = supabase.auth.onAuthStateChange((_e, session) => { setShowSignIn(false); setAuthSent(false); hydrate(session?.user); });
    return () => data?.subscription?.unsubscribe();
  }, []);

  const sendMagicLink = async () => {
    if (!supabase) { setAuthErr("Sign-in isn't enabled yet."); return; }
    if (!authEmail.includes("@")) { setAuthErr("Enter a valid email."); return; }
    setAuthBusy(true); setAuthErr("");
    try {
      const { error } = await supabase.auth.signInWithOtp({ email: authEmail.trim(), options: { emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined } });
      if (error) setAuthErr(error.message); else setAuthSent(true);
    } catch { setAuthErr("Couldn't send the link — try again."); }
    finally { setAuthBusy(false); }
  };
  const signOut = async () => { try { await supabase?.auth.signOut(); } catch {} setAuthUser(null); };
  const syncCloud = () => { if (authUser && supabase) saveCloudProgress(authUser.id); };

  const saveStats = async (s) => { try { localStorage.setItem("tp-stats", JSON.stringify(s)); } catch(e) {} };

  const activateSubscription = async () => {
    setActivateLoading(true);
    setActivateError("");
    try {
      // Already signed in — verify that email against Stripe directly
      if (authUser && supabase) {
        const data = await verifySession();
        if (data.subscribed && data.token) {
          localStorage.setItem("rsp_token", data.token);
          setSub(true);
          setShowActivate(false);
        } else {
          setActivateError(`No active subscription found for ${authUser.email}. Sign out and retry with the email used at checkout, or contact support@redsealprep.pro`);
        }
        return;
      }
      // Not signed in — email them a magic link to prove they own the address
      if (!activateEmail.includes("@")) { setActivateError("Enter the email you used at checkout."); return; }
      if (!supabase) { setActivateError("Verification is temporarily unavailable — contact support@redsealprep.pro"); return; }
      localStorage.setItem("rsp_activate_pending", "1");
      const { error } = await supabase.auth.signInWithOtp({
        email: activateEmail.trim().toLowerCase(),
        options: { emailRedirectTo: window.location.origin },
      });
      if (error) setActivateError(error.message);
      else setActivateSent(true);
    } catch {
      setActivateError("Connection error. Please try again.");
    } finally {
      setActivateLoading(false);
    }
  };

  // Timer
  useEffect(() => {
    if (quiz?.running) {
      timerRef.current = setInterval(() => setQuiz(q => {
        if (!q) return q;
        const updated = {...q, timer: q.timer+1};
        // Countdown for exam mode: auto-end when time runs out
        if (q.countdown > 0) {
          const remaining = q.countdown - q.timer - 1;
          if (remaining <= 0) {
            clearInterval(timerRef.current);
            return {...updated, running: false};
          }
        }
        return updated;
      }), 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [quiz?.running]);

  // Scroll chat
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat.messages]);

  // ─── TRADE-AWARE HELPERS ────────────────────────────────────
  const getQuestions = () => {
    if (trade?.id === "309A") return QUESTIONS_309A;
    if (trade?.id === "442A") return QUESTIONS_442A;
    if (trade?.id === "306A") return QUESTIONS_306A;
    if (trade?.id === "430A") return QUESTIONS_430A;
    if (trade?.id === "307A") return QUESTIONS_307A;
    if (trade?.id === "403A") return QUESTIONS_403A;
    if (trade?.id === "310S") return QUESTIONS_310S;
    if (trade?.id === "456A") return QUESTIONS_456A;
    return QUESTIONS_433A;
  };
  const getCategories = () => {
    if (trade?.id === "309A") return CATEGORIES_309A;
    if (trade?.id === "442A") return CATEGORIES_442A;
    if (trade?.id === "306A") return CATEGORIES_306A;
    if (trade?.id === "430A") return CATEGORIES_430A;
    if (trade?.id === "307A") return CATEGORIES_307A;
    if (trade?.id === "403A") return CATEGORIES_403A;
    if (trade?.id === "310S") return CATEGORIES_310S;
    if (trade?.id === "456A") return CATEGORIES_456A;
    return CATEGORIES;
  };

  // ─── QUIZ LOGIC ───────────────────────────────────────────
  const startQuiz = (mode, cat) => {
    const allQs = getQuestions();
    let qs = allQs;
    let countdown = 0;

    if (mode === "cat") qs = qs.filter(q => q.cat === cat);
    else if (mode === "daily") qs = shuffle(qs).slice(0, 20);
    else if (mode === "hard") qs = shuffle(qs.filter(q => q.type === "critical")).slice(0, 20);
    else if (mode === "exam") {
      // Real exam simulator: exact question count per trade, 4hr timer
      const examCount = trade?.questions || 120;
      qs = shuffle(allQs).slice(0, Math.min(examCount, allQs.length));
      countdown = 4 * 60 * 60; // 4 hours in seconds
    }
    else if (mode === "review") {
      // Spaced repetition: pull questions from wrong bank
      const bank = JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}");
      const wrongIds = Object.keys(bank).map(Number);
      qs = allQs.filter(q => wrongIds.includes(q.id));
      if (qs.length === 0) { alert("No wrong answers to review! Keep practicing."); return; }
      qs = shuffle(qs).slice(0, Math.min(30, qs.length));
    }
    else if (mode === "weak") {
      // Weakest category drill
      const weak = getWeakCats();
      if (weak.length === 0) { alert("Complete some sessions first to identify weak spots."); return; }
      const weakestCat = weak[0].id;
      qs = shuffle(allQs.filter(q => q.cat === weakestCat)).slice(0, 20);
    }
    else qs = shuffle(qs);

    if (!sub && !["daily"].includes(mode)) {
      qs = shuffle(allQs).slice(0, 20);
    }

    // Free tier: one 20-question session per day (any trade), as advertised
    if (!sub) {
      const today = new Date().toISOString().slice(0, 10);
      if (localStorage.getItem("rsp_free_day") === today) {
        alert("That's your free 20 questions done for today — come back tomorrow, or go Pro for unlimited practice, every mode, and the AI tutor.");
        setPage("landing");
        return;
      }
      try { localStorage.setItem("rsp_free_day", today); } catch {}
    }

    updateStreak();
    setQuiz({ questions: shuffle(qs).map(shuffleOpts), idx: 0, selected: null, answered: false, score: 0, answers: [], timer: 0, running: true, mode, countdown });
    setPage("quiz");
  };

  const selectAnswer = (i) => {
    if (quiz.answered) return;
    const correct = i === quiz.questions[quiz.idx].ans;
    setQuiz(q => ({
      ...q, selected: i, answered: true,
      score: correct ? q.score + 1 : q.score,
      answers: [...q.answers, { qId: q.questions[q.idx].id, sel: i, ok: correct }]
    }));
  };

  const nextQ = () => {
    if (quiz.idx < quiz.questions.length - 1) {
      setQuiz(q => ({ ...q, idx: q.idx + 1, selected: null, answered: false }));
    } else {
      const newStats = {
        sessions: stats.sessions + 1,
        attempted: stats.attempted + quiz.questions.length,
        correct: stats.correct + quiz.score,
        best: Math.max(stats.best, Math.round((quiz.score / quiz.questions.length) * 100))
      };
      setStats(newStats);
      saveStats(newStats);
      // Save wrong answers for spaced repetition + category performance
      const finalAnswers = [...quiz.answers, { qId: quiz.questions[quiz.idx].id, sel: quiz.selected, ok: quiz.selected === quiz.questions[quiz.idx].ans }];
      saveWrong(trade?.id, finalAnswers, quiz.questions);
      saveCatPerf(trade?.id, finalAnswers, quiz.questions);
      syncCloud();   // push this session's progress to the signed-in account (if any)
      setQuiz(q => ({ ...q, running: false }));
      setPage("results");
    }
  };

  // ─── AI TUTOR ─────────────────────────────────────────────
  const sendChat = async () => {
    if (!chat.input.trim() || chat.loading) return;
    const userMsg = chat.input.trim();
    const newMsgs = [...chat.messages, { role: "user", text: userMsg }];
    setChat(c => ({ ...c, messages: newMsgs, input: "", loading: true }));

    try {
      const contextQ = quiz?.questions?.[quiz.idx];
      const questionContext = contextQ ? { question: contextQ.q, options: contextQ.opts, correct: contextQ.opts[contextQ.ans], explanation: contextQ.exp, category: contextQ.cat } : null;

      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newMsgs,
          questionContext,
          token: typeof window !== "undefined" ? localStorage.getItem("rsp_token") : null,
          trade: trade ? { id: trade.id, name: trade.name } : null,
        })
      });
      if (resp.status === 401) {
        setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: "🔒 AI Tutor is a Pro feature. Subscribe to unlock unlimited tutoring." }], loading: false }));
        return;
      }
      const data = await resp.json();
      const aiText = data.text || "I couldn't process that. Try again.";
      setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: aiText }], loading: false }));
    } catch (e) {
      setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: "Connection issue. Check your network and try again." }], loading: false }));
    }
  };

  // ─── SHARED STYLES ────────────────────────────────────────
  const btn = (primary) => ({
    background: primary ? `linear-gradient(135deg, ${T.accent}, #e65100)` : T.surface,
    border: primary ? "none" : `1px solid ${T.border}`,
    borderRadius: T.radius, padding: "14px 24px", color: T.text,
    fontSize: 15, fontWeight: 700, cursor: "pointer", fontFamily: T.font,
    letterSpacing: "0.3px", transition: "all 0.2s", width: "100%", boxSizing: "border-box"
  });

  const wrap = { maxWidth: 800, margin: "0 auto", padding: "16px" };

  // ═══════════════════════════════════════════════════════════
  // Sign-in modal — shared across pages (landing header + results nudge)
  const signInModal = showSignIn && (
    <div onClick={() => setShowSignIn(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: T.bg2, border: `1px solid ${T.border}`, borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%" }}>
        {authSent ? (
          <>
            <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>✉️</div>
            <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Check your email</h2>
            <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
              We sent a sign-in link to <b style={{ color: T.text }}>{authEmail}</b>. Click it to log in — your progress will then sync across all your devices.
            </p>
            <button onClick={() => setShowSignIn(false)} style={{ ...btn(true) }}>Done</button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>☁️</div>
            <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Save your progress</h2>
            <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 28, lineHeight: 1.6 }}>
              Sign in to keep your scores, streak, and weak spots — and pick up right where you left off on any device. No password; we just email you a link.
            </p>
            <input
              type="email" value={authEmail} autoFocus
              onChange={e => { setAuthEmail(e.target.value); setAuthErr(""); }}
              onKeyDown={e => e.key === "Enter" && sendMagicLink()}
              placeholder="your@email.com"
              style={{ width: "100%", background: T.surface, border: `1px solid ${authErr ? T.red : T.border}`, borderRadius: 10, padding: "14px 16px", color: T.text, fontSize: 15, fontFamily: T.font, outline: "none", boxSizing: "border-box", marginBottom: authErr ? 8 : 16 }}
            />
            {authErr && <p style={{ color: T.red, fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>{authErr}</p>}
            <button onClick={sendMagicLink} disabled={authBusy} style={{ ...btn(true), opacity: authBusy ? 0.7 : 1 }}>
              {authBusy ? "Sending..." : "Email me a sign-in link →"}
            </button>
          </>
        )}
      </div>
    </div>
  );

  // LANDING PAGE
  // ═══════════════════════════════════════════════════════════
  if (page === "landing") return (
    <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
      {/* NAV */}
      <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${T.border}`, position: "sticky", top: 0, background: "rgba(7,9,15,0.92)", backdropFilter: "blur(20px)", zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 32, height: 32, background: `linear-gradient(135deg, ${T.accent}, #e65100)`, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>⚙️</div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.3px" }}>RedSeal<span style={{ color: T.accent }}>Prep</span></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {supabase && (authUser
            ? <button onClick={signOut} style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.text2, borderRadius: 8, padding: "9px 12px", fontSize: 12, cursor: "pointer", fontWeight: 600 }}>✓ {(authUser.email||"").split("@")[0]} · Sign out</button>
            : <button onClick={() => { setShowSignIn(true); setAuthSent(false); setAuthErr(""); }} style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "9px 14px", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>Sign in</button>)}
          <button onClick={() => setPage("trades")} style={{ ...btn(true), width: "auto", padding: "10px 20px", fontSize: 13 }}>Start Free →</button>
        </div>
      </div>

      {/* HERO */}
      <div style={{ ...wrap, textAlign: "center", padding: "60px 20px 40px" }}>
        <div style={{ display: "inline-block", background: "rgba(255,107,53,0.1)", border: `1px solid rgba(255,107,53,0.25)`, borderRadius: 20, padding: "6px 16px", fontSize: 12, color: T.accent, fontWeight: 600, marginBottom: 20, letterSpacing: "1px" }}>
          🇨🇦 CANADA'S #1 RED SEAL EXAM PREP
        </div>
        <h1 style={{ fontSize: "clamp(2rem, 6vw, 3.5rem)", fontWeight: 900, lineHeight: 1.1, marginBottom: 16, letterSpacing: "-1px" }}>
          Practice Tests for Your <span style={{ background: `linear-gradient(135deg, ${T.accent}, ${T.accent2})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Red Seal</span> Exam<br/>to Help You Pass
        </h1>
        <p style={{ fontSize: "clamp(1rem, 2.5vw, 1.2rem)", color: T.text2, maxWidth: 520, margin: "0 auto 32px", lineHeight: 1.6 }}>
          1,145+ practice questions across 9 trades with AI-powered tutoring. Built by tradespeople, for tradespeople.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={() => setPage("trades")} style={{ ...btn(true), width: "auto", padding: "16px 32px", fontSize: 16 }}>Start Free Trial →</button>
        </div>
        <div style={{ display: "flex", gap: 24, justifyContent: "center", marginTop: 32, flexWrap: "wrap" }}>
          {[["1,145+", "Questions"], ["9", "Trades Live"], ["70%", "Pass Mark"], ["AI", "Tutor"]].map(([n, l]) => (
            <div key={l} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 24, fontWeight: 900, color: T.accent }}>{n}</div>
              <div style={{ fontSize: 11, color: T.text2, textTransform: "uppercase", letterSpacing: "1px" }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* FEATURES */}
      <div style={{ ...wrap, padding: "40px 20px" }}>
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.4rem, 4vw, 2rem)", fontWeight: 800, marginBottom: 32 }}>Everything You Need to Pass</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {[
            { icon: "🧠", title: "AI Tutor", desc: "Ask any question and get instant expert explanations powered by AI" },
            { icon: "📊", title: "Progress Tracking", desc: "Track your accuracy by category to focus on weak areas" },
            { icon: "⚡", title: "Daily Practice", desc: "20-question daily quizzes keep you sharp over months of prep" },
            { icon: "🎯", title: "Exam-Matched", desc: "Questions follow the exact Red Seal NOA breakdown" },
            { icon: "📱", title: "Works Everywhere", desc: "Phone, tablet, laptop — study on break, at home, anywhere" },
            { icon: "🔧", title: "9 Trades Live", desc: "Millwright, Electrician, Plumber, Welder, Carpenter, Auto Tech & more — all included" },
          ].map(f => (
            <div key={f.title} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: T.radius, padding: 20 }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>{f.icon}</div>
              <div style={{ fontWeight: 700, marginBottom: 4, fontSize: 15 }}>{f.title}</div>
              <div style={{ fontSize: 13, color: T.text2, lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* PRICING */}
      <div style={{ ...wrap, padding: "40px 20px" }} id="pricing">
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.4rem, 4vw, 2rem)", fontWeight: 800, marginBottom: 8 }}>Simple Pricing</h2>
        <p style={{ textAlign: "center", color: T.text2, marginBottom: 32, fontSize: 14 }}>Less than the cost of one failed exam attempt</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          {/* Free */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 28 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 8 }}>Free</div>
            <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>$0</div>
            <div style={{ fontSize: 13, color: T.text2, marginBottom: 20 }}>Try before you buy</div>
            {["20 free questions daily", "All 9 trades", "Score & streak tracking"].map(f => (
              <div key={f} style={{ fontSize: 13, color: T.text2, padding: "6px 0", display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: T.green }}>✓</span> {f}
              </div>
            ))}
            <button onClick={() => setPage("trades")} style={{ ...btn(false), marginTop: 20 }}>Get Started</button>
          </div>
          {/* Pro */}
          <div style={{ background: `linear-gradient(135deg, rgba(255,107,53,0.08), rgba(255,167,38,0.04))`, border: `2px solid ${T.accent}`, borderRadius: 16, padding: 28, position: "relative" }}>
            <div style={{ position: "absolute", top: -12, right: 20, background: T.accent, color: "white", fontSize: 11, fontWeight: 800, padding: "4px 12px", borderRadius: 12 }}>MOST POPULAR</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.accent, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 8 }}>Pro</div>
            {ANNUAL_PRICE && (
              <div style={{ display: "inline-flex", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: 3, marginBottom: 10 }}>
                {[["monthly", "Monthly"], ["annual", `Annual · save ${Math.round((1 - Number(ANNUAL_PRICE) / 144) * 100)}%`]].map(([p, label]) => (
                  <button key={p} onClick={() => setPlan(p)} style={{ background: plan === p ? T.accent : "transparent", color: plan === p ? "#fff" : T.text2, border: "none", borderRadius: 6, padding: "6px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: T.font }}>
                    {label}
                  </button>
                ))}
              </div>
            )}
            {plan === "annual" && ANNUAL_PRICE
              ? <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>${ANNUAL_PRICE}<span style={{ fontSize: 16, color: T.text2 }}>/yr</span></div>
              : <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>$12<span style={{ fontSize: 16, color: T.text2 }}>/mo</span></div>}
            <div style={{ fontSize: 13, color: T.text2, marginBottom: 20 }}>Everything you need to prepare</div>
            {["All 135+ questions per trade", "Full exam simulation (timed)", "AI Tutor — unlimited questions", "Category deep-dive mode", "Hard mode (critical thinking)", "Progress analytics", "All trades included", "New questions added monthly"].map(f => (
              <div key={f} style={{ fontSize: 13, color: T.text, padding: "6px 0", display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: T.accent }}>✓</span> {f}
              </div>
            ))}
            <button onClick={async () => {
              if (checkoutLoading) return;
              setCheckoutLoading(true);
              try {
                const res = await fetch("/api/stripe/checkout", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ plan })
                });
                const data = await res.json();
                if (data.url) window.location.href = data.url;
                else alert("Payment setup error. Please try again.");
              } catch (e) { alert("Connection error. Please try again."); }
              finally { setCheckoutLoading(false); }
            }} disabled={checkoutLoading} style={{ ...btn(true), marginTop: 20, opacity: checkoutLoading ? 0.7 : 1 }}>
              {checkoutLoading ? "Loading..." : "Start 7-Day Free Trial →"}
            </button>
            <p style={{ textAlign: "center", marginTop: 12, fontSize: 12, color: T.text2 }}>
              Already subscribed?{" "}
              <span onClick={() => setShowActivate(true)} style={{ color: T.accent, cursor: "pointer", textDecoration: "underline" }}>
                Restore access →
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* TRADES PREVIEW */}
      <div style={{ ...wrap, padding: "40px 20px 60px" }}>
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.2rem, 3vw, 1.6rem)", fontWeight: 800, marginBottom: 20 }}>Trades Available</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 8 }}>
          {TRADES.map(t => (
            <div key={t.id} style={{ background: T.surface, border: `1px solid ${t.active ? `rgba(${hexRgb(t.color)},0.3)` : T.border}`, borderRadius: 10, padding: "12px", textAlign: "center", opacity: t.active ? 1 : 0.5 }}>
              <div style={{ fontSize: 24 }}>{t.icon}</div>
              <div style={{ fontSize: 12, fontWeight: 700, marginTop: 4 }}>{t.id}</div>
              <div style={{ fontSize: 10, color: T.text2, marginTop: 2 }}>{t.active ? `${t.questions}Q Ready` : "Coming Soon"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* DISCLAIMER FOOTER */}
      <div style={{ borderTop: `1px solid ${T.border}`, padding: "30px 20px", textAlign: "center" }}>
        <div style={{ maxWidth: 680, margin: "0 auto" }}>
          <p style={{ fontSize: 11, color: T.text2, lineHeight: 1.7, marginBottom: 12 }}>
            RedSeal Prep is an independent study tool and is not affiliated with, endorsed by, or sponsored by the Canadian Council of Directors of Apprenticeship (CCDA), the Red Seal Program, or any provincial/territorial apprenticeship authority. &quot;Red Seal&quot; refers to the Interprovincial Standards Red Seal Program. All practice questions are original content created for exam preparation purposes.
          </p>
          <p style={{ fontSize: 10, color: "rgba(139,148,158,0.5)" }}>
            © {new Date().getFullYear()} RedSeal Prep. All rights reserved. &nbsp;|&nbsp;
            <a href="/terms" target="_blank" rel="noopener noreferrer" style={{ color: "rgba(139,148,158,0.5)", textDecoration: "none", cursor: "pointer" }}> Terms</a> &nbsp;|&nbsp;
            <a href="/privacy" target="_blank" rel="noopener noreferrer" style={{ color: "rgba(139,148,158,0.5)", textDecoration: "none", cursor: "pointer" }}>Privacy</a>
          </p>
        </div>
      </div>

      {/* ACTIVATION MODAL */}
      {showActivate && (
        <div onClick={() => setShowActivate(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: T.bg2, border: `1px solid ${T.border}`, borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%" }}>
            {activateSent ? (
              <>
                <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>✉️</div>
                <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Check your email</h2>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
                  We sent a secure verification link to <b style={{ color: T.text }}>{activateEmail}</b>. Click it and your Pro access unlocks automatically — on whichever device you open it.
                </p>
                <button onClick={() => setShowActivate(false)} style={{ ...btn(true) }}>Done</button>
              </>
            ) : (
              <>
                <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>🎉</div>
                <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Activate Your Pro Access</h2>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 28, lineHeight: 1.6 }}>
                  {authUser
                    ? <>You&apos;re signed in as <b style={{ color: T.text }}>{authUser.email}</b>. We&apos;ll check for a subscription under this email.</>
                    : <>Enter the email you used at checkout. We&apos;ll send you a secure link to verify it&apos;s you and unlock full access.</>}
                </p>
                {!authUser && (
                  <input
                    type="email"
                    value={activateEmail}
                    onChange={e => { setActivateEmail(e.target.value); setActivateError(""); }}
                    onKeyDown={e => e.key === "Enter" && activateSubscription()}
                    placeholder="your@email.com"
                    autoFocus
                    style={{
                      width: "100%", background: T.surface,
                      border: `1px solid ${activateError ? T.red : T.border}`,
                      borderRadius: 10, padding: "14px 16px", color: T.text,
                      fontSize: 15, fontFamily: T.font, outline: "none",
                      boxSizing: "border-box", marginBottom: activateError ? 8 : 16,
                    }}
                  />
                )}
                {activateError && (
                  <p style={{ color: T.red, fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>{activateError}</p>
                )}
                <button
                  onClick={activateSubscription}
                  disabled={activateLoading}
                  style={{ ...btn(true), opacity: activateLoading ? 0.7 : 1 }}
                >
                  {activateLoading ? "Verifying..." : authUser ? "Verify My Subscription →" : "Email Me a Verification Link →"}
                </button>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 12, marginTop: 16 }}>
                  Issues? Email{" "}
                  <a href="mailto:support@redsealprep.pro" style={{ color: T.accent }}>support@redsealprep.pro</a>
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* SIGN-IN MODAL — Supabase magic link */}
      {signInModal}
    </div>
  );

  // ═══════════════════════════════════════════════════════════
  // TRADE SELECTION
  // ═══════════════════════════════════════════════════════════
  if (page === "trades") return (
    <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
      <div style={wrap}>
        <button onClick={() => setPage("landing")} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font, padding: "8px 0", marginBottom: 16 }}>← Back</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Choose Your Trade</h1>
        <p style={{ color: T.text2, fontSize: 14, marginBottom: 24 }}>Select the Red Seal exam you're preparing for</p>
        <div style={{ display: "grid", gap: 10 }}>
          {TRADES.map(t => (
            <div key={t.id}
              onClick={() => { if(t.active) { setTrade(t); setPage("dashboard"); } }}
              style={{
                background: t.active ? `rgba(${hexRgb(t.color)},0.06)` : T.surface,
                border: `1px solid ${t.active ? `rgba(${hexRgb(t.color)},0.2)` : T.border}`,
                borderRadius: T.radius, padding: "16px 18px",
                cursor: t.active ? "pointer" : "default",
                opacity: t.active ? 1 : 0.45,
                display: "flex", alignItems: "center", gap: 14, transition: "all 0.2s"
              }}>
              <div style={{ fontSize: 28 }}>{t.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{t.id} — {t.name}</div>
                <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>{t.active ? `${t.questions} questions ready` : "Coming soon — join waitlist"}</div>
              </div>
              {t.active && <div style={{ color: t.color, fontSize: 18 }}>→</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ═══════════════════════════════════════════════════════════
  // DASHBOARD
  // ═══════════════════════════════════════════════════════════
  if (page === "dashboard") {
    const pct = stats.attempted > 0 ? Math.round((stats.correct / stats.attempted) * 100) : 0;
    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          <button onClick={() => setPage("trades")} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font, padding: "8px 0" }}>← Trades</button>

          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "12px 0 20px" }}>
            <div style={{ width: 40, height: 40, background: `linear-gradient(135deg, ${trade?.color || T.accent}, ${T.accent})`, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>{trade?.icon}</div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18 }}>{trade?.id} {trade?.name?.split("(")[0]}</div>
              <div style={{ fontSize: 12, color: T.text2 }}>Red Seal Exam Prep</div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 24 }}>
            {[[`🔥${streak.days}`, "Streak"], [stats.sessions, "Sessions"], [`${pct}%`, "Accuracy"], [`${stats.best}%`, "Best"]].map(([v, l]) => (
              <div key={l} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 8px", textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 900, color: l === "Accuracy" ? (pct >= 70 ? T.green : T.red) : T.accent2 }}>{v}</div>
                <div style={{ fontSize: 9, color: T.text2, textTransform: "uppercase", letterSpacing: "1px", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>

          {/* Modes */}
          <div style={{ fontSize: 11, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 10 }}>Practice Modes</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 24 }}>
            {(() => {
              const wb = typeof window !== "undefined" ? JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}") : {};
              const wrongCount = Object.keys(wb).length;
              const weakCats = getWeakCats();
              const weakLabel = weakCats.length > 0 ? `Block ${weakCats[0].id} (${weakCats[0].pct}%)` : "Complete sessions first";
              return [
              { m: "daily", icon: "⚡", name: "Daily 20", desc: "Quick daily practice", n: 20, free: true },
              { m: "exam", icon: "🎯", name: "Exam Simulator", desc: `Real ${trade?.questions || 120}Q timed exam`, n: trade?.questions || 120, free: false },
              { m: "review", icon: "🔁", name: "Review Wrong", desc: `${wrongCount} saved mistakes`, n: Math.min(wrongCount, 30) || "—", free: false },
              { m: "weak", icon: "📊", name: "Weak Spots", desc: weakLabel, n: 20, free: false },
              { m: "hard", icon: "🧠", name: "Hard Mode", desc: "Critical thinking only", n: 20, free: false },
              { m: "ai", icon: "🤖", name: "AI Tutor", desc: "Ask anything", n: "∞", free: false },
            ];})().map(mode => (
              <div key={mode.m}
                onClick={() => mode.m === "ai" ? setChat(c => ({ ...c, open: true })) : (mode.free || sub) ? startQuiz(mode.m) : setPage("landing")}
                style={{
                  background: T.surface, border: `1px solid ${T.border}`, borderRadius: T.radius,
                  padding: 16, cursor: "pointer", position: "relative", transition: "all 0.2s"
                }}>
                {!mode.free && !sub && <div style={{ position: "absolute", top: 8, right: 8, fontSize: 9, background: "rgba(255,107,53,0.15)", color: T.accent, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>PRO</div>}
                <div style={{ fontSize: 10, color: T.accent, fontWeight: 700, marginBottom: 2 }}>{mode.n}Q</div>
                <div style={{ fontSize: 15, marginBottom: 2 }}>{mode.icon} {mode.name}</div>
                <div style={{ fontSize: 11, color: T.text2 }}>{mode.desc}</div>
              </div>
            ))}
          </div>

          {/* Categories */}
          <div style={{ fontSize: 11, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 10 }}>By Category</div>
          {getCategories().map(cat => (
            <div key={cat.id}
              onClick={() => sub ? startQuiz("cat", cat.id) : setPage("landing")}
              style={{
                background: `rgba(${hexRgb(cat.color)},0.05)`, border: `1px solid rgba(${hexRgb(cat.color)},0.15)`,
                borderRadius: 10, padding: "12px 14px", marginBottom: 8,
                display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer"
              }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 800, color: cat.color }}>BLOCK {cat.id}</div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{cat.name}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {!sub && <span style={{ fontSize: 9, color: T.accent }}>PRO</span>}
                <span style={{ fontSize: 12, fontWeight: 700, color: cat.color }}>{cat.target}Q →</span>
              </div>
            </div>
          ))}
        </div>

        {/* AI TUTOR CHAT PANEL */}
        {chat.open && (
          <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, top: 0, background: "rgba(0,0,0,0.7)", zIndex: 200, display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: 800, margin: "0 auto", width: "100%" }}>
              <div style={{ padding: "16px 20px", background: T.bg2, borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>🤖 AI Tutor</div>
                <button onClick={() => setChat(c => ({ ...c, open: false }))} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 20, fontFamily: T.font }}>✕</button>
              </div>
              <div style={{ flex: 1, overflowY: "auto", padding: 16, background: T.bg }}>
                {chat.messages.length === 0 && (
                  <div style={{ textAlign: "center", padding: "40px 20px", color: T.text2 }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
                    <div style={{ fontWeight: 700, fontSize: 16, color: T.text, marginBottom: 8 }}>Ask Me Anything</div>
                    <div style={{ fontSize: 13, lineHeight: 1.6 }}>I'm your Red Seal 433A exam tutor. Ask about hydraulics, alignment, rigging, gear ratios — anything on the exam.</div>
                  </div>
                )}
                {chat.messages.map((m, i) => (
                  <div key={i} style={{ marginBottom: 12, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: "85%", padding: "12px 16px", borderRadius: 14,
                      background: m.role === "user" ? T.accent : T.bg3,
                      color: T.text, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap"
                    }}>{m.text}</div>
                  </div>
                ))}
                {chat.loading && <div style={{ color: T.text2, fontSize: 13, padding: 8 }}>Thinking...</div>}
                <div ref={chatEndRef} />
              </div>
              <div style={{ padding: "12px 16px", background: T.bg2, borderTop: `1px solid ${T.border}`, display: "flex", gap: 8 }}>
                <input
                  value={chat.input}
                  onChange={e => setChat(c => ({ ...c, input: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && sendChat()}
                  placeholder="Ask about any exam topic..."
                  style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 16px", color: T.text, fontSize: 14, fontFamily: T.font, outline: "none" }}
                />
                <button onClick={sendChat} style={{ ...btn(true), width: "auto", padding: "12px 18px" }}>Send</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════
  // QUIZ
  // ═══════════════════════════════════════════════════════════
  if (page === "quiz" && quiz) {
    const q = quiz.questions[quiz.idx];
    const cat = getCategories().find(c => c.id === q.cat);
    const pct = ((quiz.idx + (quiz.answered ? 1 : 0)) / quiz.questions.length) * 100;
    const letters = ["A", "B", "C", "D"];

    const getState = (i) => {
      if (!quiz.answered) return null;
      if (i === q.ans) return "correct";
      if (i === quiz.selected && i !== q.ans) return "wrong";
      return null;
    };

    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          {/* Progress */}
          <div style={{ height: 4, background: T.surface, borderRadius: 2, overflow: "hidden", marginBottom: 16 }}>
            <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${T.accent}, ${T.accent2})`, borderRadius: 2, transition: "width 0.4s" }} />
          </div>

          {/* Meta */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 6 }}>
            <span style={{ fontSize: 12, color: T.text2, fontWeight: 600 }}>Q{quiz.idx + 1}/{quiz.questions.length}</span>
            <span style={{ fontSize: 10, color: cat.color, background: `rgba(${hexRgb(cat.color)},0.12)`, padding: "2px 8px", borderRadius: 4, fontWeight: 700 }}>Block {q.cat}</span>
            <span style={{ fontSize: 10, color: T.text2, background: T.surface, padding: "2px 8px", borderRadius: 4 }}>
              {q.type === "recall" ? "📖 Recall" : q.type === "procedure" ? "🔧 Procedure" : "🧠 Critical"}
            </span>
            <span style={{ fontSize: 12, color: quiz.countdown > 0 && (quiz.countdown - quiz.timer) < 600 ? T.red : T.accent2, fontWeight: 700, fontFamily: T.mono }}>
              {quiz.countdown > 0 ? `⏱ ${fmtTime(Math.max(0, quiz.countdown - quiz.timer))} left` : `⏱ ${fmtTime(quiz.timer)}`}
            </span>
            {quiz.mode === "exam" && <span style={{ fontSize: 9, background: "rgba(255,107,53,0.15)", color: T.accent, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>EXAM MODE</span>}
            {quiz.mode === "review" && <span style={{ fontSize: 9, background: "rgba(76,175,80,0.15)", color: T.green, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>REVIEW</span>}
          </div>

          {/* Question */}
          <div style={{ fontSize: "clamp(0.95rem, 2.5vw, 1.15rem)", fontWeight: 700, lineHeight: 1.55, marginBottom: 20 }}>{q.q}</div>

          {/* Options */}
          {q.opts.map((opt, i) => {
            const st = getState(i);
            const bg = st === "correct" ? `rgba(${hexRgb(T.green)},0.1)` : st === "wrong" ? `rgba(${hexRgb(T.red)},0.1)` : T.surface;
            const bdr = st === "correct" ? T.green : st === "wrong" ? T.red : T.border;
            return (
              <div key={i} onClick={() => selectAnswer(i)} style={{
                background: bg, border: `2px solid ${bdr}`, borderRadius: 10, padding: "14px 16px",
                marginBottom: 8, display: "flex", alignItems: "center", gap: 12, cursor: quiz.answered ? "default" : "pointer", transition: "all 0.2s"
              }}>
                <div style={{
                  width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, fontWeight: 800, flexShrink: 0,
                  background: st === "correct" ? `rgba(${hexRgb(T.green)},0.2)` : st === "wrong" ? `rgba(${hexRgb(T.red)},0.2)` : T.surface,
                  color: st === "correct" ? T.green : st === "wrong" ? T.red : T.text2
                }}>
                  {quiz.answered && st === "correct" ? "✓" : quiz.answered && st === "wrong" ? "✗" : letters[i]}
                </div>
                <div style={{ fontSize: "clamp(0.82rem, 2vw, 0.95rem)", lineHeight: 1.4, color: st ? (st === "correct" ? T.green : T.red) : T.text }}>{opt}</div>
              </div>
            );
          })}

          {/* Explanation */}
          {quiz.answered && (
            <div style={{ background: "rgba(255,167,38,0.06)", border: "1px solid rgba(255,167,38,0.15)", borderRadius: 10, padding: 14, marginTop: 16, fontSize: 13, lineHeight: 1.65, color: "#c4a35a" }}>
              <strong style={{ color: T.accent2 }}>💡 </strong>{q.exp}
            </div>
          )}

          {/* Actions */}
          {quiz.answered && (
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              {sub && <button onClick={() => setChat(c => ({ ...c, open: true }))} style={{ ...btn(false), flex: "0 0 auto", width: "auto", padding: "14px 16px", fontSize: 18 }}>🤖</button>}
              <button onClick={nextQ} style={{ ...btn(true), flex: 1 }}>
                {quiz.idx < quiz.questions.length - 1 ? "Next →" : "See Results →"}
              </button>
            </div>
          )}

          <div style={{ textAlign: "center", marginTop: 16 }}>
            <button onClick={() => { setQuiz(null); setPage("dashboard"); }} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font }}>← Exit Quiz</button>
          </div>
        </div>

        {/* AI Chat overlay in quiz too */}
        {chat.open && (
          <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: "60vh", background: T.bg2, zIndex: 200, display: "flex", flexDirection: "column", borderTop: `2px solid ${T.accent}`, borderRadius: "16px 16px 0 0" }}>
            <div style={{ padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>🤖 AI Tutor — ask about this question</span>
              <button onClick={() => setChat(c => ({ ...c, open: false }))} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
              {chat.messages.map((m, i) => (
                <div key={i} style={{ marginBottom: 8, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                  <div style={{ maxWidth: "85%", padding: "10px 14px", borderRadius: 12, background: m.role === "user" ? T.accent : T.bg3, fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{m.text}</div>
                </div>
              ))}
              {chat.loading && <div style={{ color: T.text2, fontSize: 12, padding: 8 }}>Thinking...</div>}
              <div ref={chatEndRef} />
            </div>
            <div style={{ padding: "10px 12px", display: "flex", gap: 8, borderTop: `1px solid ${T.border}` }}>
              <input value={chat.input} onChange={e => setChat(c => ({ ...c, input: e.target.value }))} onKeyDown={e => e.key === "Enter" && sendChat()}
                placeholder="Why is B correct?" style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 13, fontFamily: T.font, outline: "none" }} />
              <button onClick={sendChat} style={{ ...btn(true), width: "auto", padding: "10px 16px", fontSize: 13 }}>→</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════
  // RESULTS
  // ═══════════════════════════════════════════════════════════
  if (page === "results" && quiz) {
    const pct = Math.round((quiz.score / quiz.questions.length) * 100);
    const passed = pct >= 70;

    const catBreak = getCategories().map(cat => {
      const qs = quiz.answers.filter(a => quiz.questions.find(q => q.id === a.qId)?.cat === cat.id);
      const ok = qs.filter(a => a.ok).length;
      return { ...cat, total: qs.length, ok, pct: qs.length ? Math.round((ok / qs.length) * 100) : 0 };
    }).filter(c => c.total > 0);

    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          <div style={{ textAlign: "center", margin: "20px 0 24px" }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>{passed ? "🏆" : "📚"}</div>
            <div style={{
              width: 130, height: 130, borderRadius: "50%", margin: "0 auto 16px",
              background: `linear-gradient(135deg, rgba(${hexRgb(passed ? T.green : T.red)},0.15), rgba(${hexRgb(passed ? T.green : T.red)},0.05))`,
              border: `3px solid ${passed ? T.green : T.red}`,
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"
            }}>
              <div style={{ fontSize: 40, fontWeight: 900, color: passed ? T.green : T.red, lineHeight: 1 }}>{pct}%</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: passed ? T.green : T.red, marginTop: 2 }}>{quiz.score}/{quiz.questions.length}</div>
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: passed ? T.green : T.red }}>
              {quiz.mode === "exam" ? (passed ? "RED SEAL READY! 🏆" : "NOT YET — KEEP GOING 💪") : (passed ? "PASSED! 🎉" : "KEEP STUDYING")}
            </div>
            {quiz.mode === "exam" && <div style={{ fontSize: 11, color: T.text2, marginTop: 4, background: T.surface, display: "inline-block", padding: "4px 10px", borderRadius: 6 }}>
              Exam Simulation: {quiz.questions.length} questions in {fmtTime(quiz.timer)}
            </div>}
            <div style={{ fontSize: 12, color: T.text2, marginTop: 4 }}>Time: {fmtTime(quiz.timer)} • {Math.round(quiz.timer / quiz.questions.length)}s avg</div>
          </div>

          {/* Category breakdown */}
          <div style={{ marginBottom: 20 }}>
            {catBreak.map(c => (
              <div key={c.id} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: c.color, fontWeight: 700 }}>Block {c.id}</span>
                  <span style={{ color: c.pct >= 70 ? T.green : T.red, fontWeight: 800 }}>{c.ok}/{c.total} ({c.pct}%)</span>
                </div>
                <div style={{ height: 6, background: T.surface, borderRadius: 3 }}>
                  <div style={{ height: "100%", width: `${c.pct}%`, background: c.pct >= 70 ? c.color : T.red, borderRadius: 3, transition: "width 0.5s" }} />
                </div>
              </div>
            ))}
          </div>

          {/* Wrong answers review */}
          <button onClick={() => setShowWrong(!showWrong)} style={{ ...btn(false), marginBottom: 12 }}>
            {showWrong ? "Hide" : "📝 Review"} Wrong Answers ({quiz.answers.filter(a => !a.ok).length})
          </button>

          {showWrong && quiz.answers.filter(a => !a.ok).map((a, i) => {
            const q = getQuestions().find(q => q.id === a.qId);
            if (!q) return null;
            return (
              <div key={i} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14, marginBottom: 8 }}>
                <div style={{ fontWeight: 700, color: T.red, fontSize: 11, marginBottom: 4 }}>✗ Q{q.id}</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{q.q}</div>
                <div style={{ fontSize: 12, color: T.red }}>Yours: {q.opts[a.sel]}</div>
                <div style={{ fontSize: 12, color: T.green, fontWeight: 700 }}>Correct: {q.opts[q.ans]}</div>
                <div style={{ fontSize: 11, color: "#c4a35a", marginTop: 6, lineHeight: 1.5 }}>{q.exp}</div>
              </div>
            );
          })}

          {/* Weak Spot Analysis */}
          {(() => {
            const weak = getWeakCats();
            if (weak.length === 0) return null;
            const worst = weak.filter(c => c.pct < 70).slice(0, 3);
            if (worst.length === 0) return null;
            return (
              <div style={{ background: "rgba(255,107,53,0.05)", border: `1px solid rgba(255,107,53,0.15)`, borderRadius: 10, padding: 14, marginTop: 16, marginBottom: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: T.accent, marginBottom: 8 }}>📊 YOUR WEAK SPOTS</div>
                {worst.map(c => (
                  <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: T.text }}>Block {c.id}: {c.name}</span>
                    <span style={{ color: T.red, fontWeight: 700 }}>{c.pct}%</span>
                  </div>
                ))}
                <button onClick={() => sub ? startQuiz("weak") : setPage("landing")} style={{ ...btn(true), marginTop: 8, padding: "10px 16px", fontSize: 13 }}>🎯 Drill Weakest Category</button>
              </div>
            );
          })()}

          {/* Spaced repetition prompt */}
          {Object.keys(wrongBank).length > 0 && (
            <button onClick={() => startQuiz("review")} style={{ ...btn(false), marginTop: 8, marginBottom: 8, border: `1px solid ${T.green}`, color: T.green }}>
              🔁 Review {Object.keys(wrongBank).length} Saved Mistakes
            </button>
          )}

          {/* Email capture — nudge anonymous users to save this result */}
          {supabase && !authUser && (
            <div style={{ background: "rgba(88,166,255,0.06)", border: "1px solid rgba(88,166,255,0.2)", borderRadius: 10, padding: 14, marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.5 }}>
                <b style={{ color: T.text }}>☁️ Don&apos;t lose this progress.</b> Sign in free to keep your scores and streak on any device.
              </div>
              <button onClick={() => setShowSignIn(true)} style={{ ...btn(false), width: "auto", padding: "9px 16px", fontSize: 12, whiteSpace: "nowrap" }}>Sign in free →</button>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={() => { setQuiz(null); setPage("dashboard"); }} style={{ ...btn(false), flex: 1 }}>← Dashboard</button>
            <button onClick={() => startQuiz("daily")} style={{ ...btn(true), flex: 1 }}>🔄 Quick 20</button>
          </div>
        </div>
        {signInModal}
      </div>
    );
  }

  return null;
}
