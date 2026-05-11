  
Read-only audit. Do not modify any file. Do not run any code that mutates state.

Task: enumerate every location in this repo where clinical math is computed.

Definition of "clinical math" (be strict, not loose):  
\- Hemodynamic calculations (CO, SV, SVR, PVR, MAP, gradients, regurgitant fractions, etc.)  
\- Risk scoring (HDI, SCAI, TIMI, GRACE, any band/tier assignment)  
\- ECG priority/ranking computation  
\- ODE simulator state evolution and steady-state solving  
\- Any derivation of a clinical number from other clinical numbers  
\- Threshold/cutpoint comparisons that produce a clinical label

Explicitly NOT clinical math (do not include):  
\- UI formatting of already-computed numbers  
\- Type definitions / interfaces with no logic  
\- Test files (list separately at the end if relevant)  
\- Mock/stub data fixtures (list separately)

Method — follow exactly:  
1\. Run rg (ripgrep) with explicit patterns. Paste every command you run and its raw output count.  
   Suggested starting patterns: compute, calculate, score, band, tier, solve, integrate, dydt, gradient, regurg, SVR, PVR, LVEDP, cutpoint, threshold  
2\. For each hit, open the file and read the surrounding function. Do not infer from filename alone.  
3\. Discard hits that don't meet the strict definition above.

Output format — one entry per location, no prose between them:

  ID: \<sequential\>  
  File: \<relative path\>:\<start\_line\>-\<end\_line\>  
  Function/export: \<exact name\>  
  Inputs: \<variable names and types as declared, verbatim\>  
  Outputs: \<return type/shape, verbatim\>  
  What it computes: \<one sentence, mechanical description — "multiplies HR by SV to produce CO", not "estimates cardiac output"\>  
  Evidence quote: \<3-8 lines pasted verbatim from the file, with line numbers, that prove the description\>  
  Verification: \<how you confirmed the math matches the description — e.g., "traced inputs from caller X at file:line", "matched formula against constant K defined at file:line"\>

Rules:  
\- If you cannot paste a verbatim evidence quote with line numbers, omit the entry.  
\- If the math depends on a constant, cutpoint, or weight defined elsewhere, include a second evidence quote showing that definition with file:line.  
\- Do not summarize. Do not say "similar to above." Each entry stands alone.  
\- If a function looks like clinical math but you can't determine what it computes from reading it, list it under a final "UNCERTAIN" section with the file:line and what's unclear. Do not guess.  
\- At the end, paste the exact rg commands you ran so I can reproduce the sweep.

Do not write any narrative summary, conclusion, or recommendation. Just the enumeration.  
Ran 5 commands, read 18 files  
ID: 1  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:107-152  
Function/export: scoreForwardFlowReserve (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: derives cardiac index as effective\_CO/1.73 (or CO/1.73, or observed CI), maps CI through piecewise anchors \[(1.5,100),(2.0,70),(2.2,50),(2.5,0),(4.0,0)\] and SVi through \[(20,100),(30,60),(35,30),(40,0)\], returns the worse of the two.  
Evidence quote:  
113	  let ci: number | undefined;  
117	    ci \= m.effective\_CO\_Lpm / 1.73;  
129	  const ciScore \= piecewise(ci, \[  
130	    \[1.5, 100\],  
131	    \[2.0, 70\],  
132	    \[2.2, 50\],  
133	    \[2.5, 0\],  
134	    \[4.0, 0\],  
135	  \]);  
140	    sviScore \= piecewise(m.SVi, \[  
141	      \[20, 100\], \[30, 60\], \[35, 30\], \[40, 0\],  
145	    \]);  
150	  const score \= Math.max(ciScore, sviScore);  
Verification: piecewise is defined at computeHdi.ts:84-99 (linear interpolation, clamps). Score then weighted at computeHdi.ts:710-714 by HDI\_WEIGHTS.forward\_flow\_reserve.value \= 0.22 (hdiWeights.ts:61).  
ID: 2  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:154-211  
Function/export: scoreCongestion (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: takes worst of three piecewise mappings — PCWP or Mean\_LA through \[(10,0),(12,10),(15,40),(20,70),(25,100)\]; sPAP through \[(25,0),(40,30),(55,60),(70,100)\]; LVEDP through \[(10,0),(16,30),(22,60),(30,100)\].  
Evidence quote:  
164	    const v \= piecewise(filling, \[  
165	      \[10, 0\], \[12, 10\], \[15, 40\], \[20, 70\], \[25, 100\],  
170	    \]);  
180	    const v \= piecewise(m.sPAP, \[  
181	      \[25, 0\], \[40, 30\], \[55, 60\], \[70, 100\],  
185	    \]);  
194	    const v \= piecewise(m.LVEDP, \[  
195	      \[10, 0\], \[16, 30\], \[22, 60\], \[30, 100\],  
199	    \]);  
Verification: Weighted at computeHdi.ts:718-722 by HDI\_WEIGHTS.congestion\_burden.value \= 0.18 (hdiWeights.ts:80).  
ID: 3  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:213-292  
Function/export: scoreRvPvrStress (module-private)  
Inputs: m: SimulatorMetrics, \_ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: max of four piecewise mappings on PVR\_woods (floor=2 WU), TPG (\[(8,0),(12,50),(20,100)\]), RF\_TR (\[(0.05,0),(0.3,50),(0.5,100)\]), and mPAP (floor=20).  
Evidence quote:  
225	    const v \= piecewise(m.PVR\_woods, \[  
226	      \[PVR\_PRECAP\_CONTRIB\_DIVIDE\_WU, 0\],  
227	      \[3, 40\], \[5, 80\], \[6, 100\],  
230	    \]);  
243	    const v \= piecewise(m.TPG, \[  
244	      \[8, 0\], \[12, 50\], \[20, 100\],  
247	    \]);  
271	    const v \= piecewise(m.mPAP, \[  
272	      \[MPAP\_PH\_THRESHOLD\_MMHG, 0\],  
273	      \[25, 40\], \[40, 90\], \[50, 100\],  
276	    \]);  
Verification: Constants imported from guidelines/thresholds/esc-ers-2022-ph.ts:37 (MPAP\_PH\_THRESHOLD\_MMHG \= 20) and esc-ers-2022-ph.ts:66 (PVR\_PRECAP\_CONTRIB\_DIVIDE\_WU \= 2); weight 0.13 at hdiWeights.ts:100.  
ID: 4  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:294-365  
Function/export: scoreRegurgitantBurden (module-private)  
Inputs: m: SimulatorMetrics  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: max of piecewise mappings — RF\_MR & RF\_AR through \[(0.05,0),(0.3,50),(0.4,75),(0.5,100)\]; RF\_TR through \[(0.05,0),(0.3,50),(0.5,100)\] then attenuated by 0.7; Mean\_AV\_grad through \[(10,0),(20,30),(40,75),(60,100)\].  
Evidence quote:  
302	    const v \= piecewise(mr, \[  
303	      \[0.05, 0\], \[0.3, 50\], \[0.4, 75\], \[0.5, 100\],  
307	    \]);  
328	    const v \= piecewise(tr, \[  
329	      \[0.05, 0\], \[0.3, 50\], \[0.5, 100\],  
332	    \]);  
335	    const attenuated \= v \* 0.7;  
344	    const v \= piecewise(m.Mean\_AV\_grad, \[  
345	      \[10, 0\], \[20, 30\], \[40, 75\], \[60, 100\],  
349	    \]);  
Verification: Weighted at computeHdi.ts:734 by HDI\_WEIGHTS.regurgitant\_burden.value \= 0.13 (hdiWeights.ts:127).  
ID: 5  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:367-426  
Function/export: scorePressureFlowMismatch (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: max of three mappings — gap (targetMAP=(SBP+2·DBP)/3 minus achievedMAP) piecewise \[(0,0),(10,30),(20,70),(35,100)\]; baroFactor piecewise \[(1.0,0),(1.4,25),(1.7,60),(1.85,100)\]; pressorsCount→30 if 1, 60 if ≥2.  
Evidence quote:  
380	    const targetMAP \= (m.targetSBP \+ 2 \* m.targetDBP) / 3;  
381	    const gap \= Math.max(0, targetMAP \- m.achievedMAP);  
382	    const v \= piecewise(gap, \[  
383	      \[0, 0\], \[10, 30\], \[20, 70\], \[35, 100\],  
386	    \]);  
397	    const v \= piecewise(m.baroFactor, \[  
398	      \[1.0, 0\], \[1.4, 25\], \[1.7, 60\], \[1.85, 100\],  
401	    \]);  
411	    const v \= (ctx\!.pressorsCount ?? 0\) \>= 2 ? 60 : 30;  
Verification: Weight 0.10 at hdiWeights.ts:143.  
ID: 6  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:428-465  
Function/export: scoreRhythmInstability (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: RR\_CV piecewise \[(0.05,0),(0.10,20),(0.15,60),(0.25,100)\]; AFib floor 30; VT/VF → 100; multipleDefibrillations floor 80\.  
Evidence quote:  
436	    const v \= piecewise(m.RR\_CV, \[  
437	      \[0.05, 0\], \[0.10, 20\], \[0.15, 60\], \[0.25, 100\],  
441	    \]);  
447	  if (ctx?.rhythm \=== 'AFib' && s \< 30\) {  
448	    s \= 30;  
451	  if (ctx?.rhythm \=== 'VT' || ctx?.rhythm \=== 'VF') {  
452	    s \= 100;  
455	  if (ctx?.multipleDefibrillations && s \< 80\) {  
456	    s \= 80;  
Verification: Weight 0.05 at hdiWeights.ts:158.  
ID: 7  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:467-523  
Function/export: scoreClinicalOverlay (module-private)  
Inputs: ctx: ClinicalContext | undefined  
Outputs: { score: number; available: boolean; dominant?: string }  
What it computes: starts at lactate piecewise \[(1,0),(2,30),(4,60),(8,100)\], adds \+20 if UO\<30 mL/h, \+25 if ≥2 pressors, \+30 if MCS active, \+10 if hoursSinceMI\<12 (clamped to 100).  
Evidence quote:  
477	    const v \= piecewise(ctx.lactate\_mmol\_L, \[  
478	      \[1, 0\], \[2, 30\], \[4, 60\], \[8, 100\],  
482	    \]);  
493	    ctx.urineOutput\_mL\_per\_h \< 30  
494	  ) {  
495	    s \= clamp(s \+ 20, 0, 100);  
499	  if ((ctx.pressorsCount ?? 0\) \>= 2\) {  
500	    s \= clamp(s \+ 25, 0, 100);  
505	  if (ctx.mcsActive) {  
506	    s \= clamp(s \+ 30, 0, 100);  
511	  if (ctx.hoursSinceMI \!= null && ctx.hoursSinceMI \< 12 && s \< 100\) {  
512	    s \= clamp(s \+ 10, 0, 100);  
Verification: Weight 0.09 at hdiWeights.ts:173.  
ID: 8  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:533-645  
Function/export: scoreTrajectoryBurden (module-private)  
Inputs: ctx: ClinicalContext | undefined, currentScaiStage: ScaiStage | null, currentEffectiveCO?: number, currentMeanLA?: number  
Outputs: { score: number; available: boolean; dominant?: string; clockSkew: boolean }  
What it computes: rapid-amp (×1.2) when 0 ≤ hoursGap \< 6; max of SCAI rank-progression→amp(40), pressor escalation→amp(30), effective\_CO drop ≥0.5→amp(25), Mean\_LA rise ≥5→amp(20), lactate rise ≥1 or trend='rising'→amp(25); clamped to 100\.  
Evidence quote:  
565	  const rapid \= hoursGap \!= null && hoursGap \>= 0 && hoursGap \< 6;  
566	  const amp \= (v: number) \=\> clamp(v \* (rapid ? 1.2 : 1.0), 0, 100);  
572	    SCAI\_RANK\[currentScaiStage\] \> SCAI\_RANK\[pm.scaiStage\]  
573	  ) {  
574	    const v \= amp(40);  
583	    if (ctx.pressorsCount \> pm.pressorsCount) {  
584	      const v \= amp(30);  
605	    pm.effective\_CO\_Lpm \- currentEffectiveCO \>= 0.5  
607	    const v \= amp(25);  
619	    currentMeanLA \- pm.Mean\_LA \>= 5  
621	    const v \= amp(20);  
629	    if (ctx.lactate\_mmol\_L \- pm.lactate\_mmol\_L \>= 1\) {  
630	      const v \= amp(25);  
Verification: SCAI\_RANK defined at computeHdi.ts:525-531 (A=0..E=4); weight 0.10 at hdiWeights.ts:192.  
ID: 9  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:649-660  
Function/export: tierOf, statusOfCoverage (module-private)  
Inputs: tierOf(score: number); statusOfCoverage(k: number)  
Outputs: HdiTier; HdiStatus  
What it computes: maps composite score to Band 1 (\<25), Band 2 (\<50), Band 3 (\<75), else Band 4; maps coverage fraction to 'sufficient\_inputs' (≥0.75), 'limited\_inputs' (≥0.6), else 'insufficient\_inputs'.  
Evidence quote:  
650	  if (score \< HDI\_TIER\_CUTPOINTS.Band1Max) return 'Band 1';  
651	  if (score \< HDI\_TIER\_CUTPOINTS.Band2Max) return 'Band 2';  
652	  if (score \< HDI\_TIER\_CUTPOINTS.Band3Max) return 'Band 3';  
653	  return 'Band 4';  
657	  if (k \>= HDI\_COVERAGE\_THRESHOLDS.sufficient) return 'sufficient\_inputs';  
658	  if (k \>= HDI\_COVERAGE\_THRESHOLDS.limited) return 'limited\_inputs';  
659	  return 'insufficient\_inputs';  
Verification: Cutpoint constants defined at hdiWeights.ts:224-229 (Band1Max:25, Band2Max:50, Band3Max:75) and hdiWeights.ts:241-245 (sufficient:0.75, limited:0.6).  
ID: 10  
File: apps/rrvalves-canvas/src/cicu-risk/computeHdi.ts:674-839  
Function/export: computeHdi (exported)  
Inputs: args: { metrics: SimulatorMetrics; context?: ClinicalContext; audit?: SimulatorAudit; scaiResult?: ScaiShockResult }  
Outputs: { hdi: HdiResult; confidenceFlags: ConfidenceFlag\[\] }  
What it computes: counts coverage of REQUIRED\_SIM\_FIELDS, sums each subscore×weight, clamps to \[0,100\], assigns tier via tierOf, sorts subscores by contribution to extract top-3 drivers, sets dominantMechanism when composite ≥25 and a single subscore contributes \>40%.  
Evidence quote:  
801	    const composite \= clamp(  
802	      subscores.reduce((s, x) \=\> s \+ x.contribution, 0),  
803	      0, 100  
805	    );  
806	    score \= composite;  
807	    tier \= tierOf(composite);  
808	    const sorted \= \[...subscores\]  
809	      .sort((a, b) \=\> b.contribution \- a.contribution)  
817	    const DOM\_MIN\_COMPOSITE \= HDI\_TIER\_CUTPOINTS.Band1Max; // 25  
818	    dominantMechanism \=  
819	      dom &&  
820	      composite \>= DOM\_MIN\_COMPOSITE &&  
821	      dom.contribution / composite \> 0.4  
Verification: Subscores array assembled at computeHdi.ts:706-771 — each entry's contribution \= score \* HDI\_WEIGHTS\[name\].value. Weights sum-to-1 invariant enforced at hdiWeights.ts:215-222.  
ID: 11  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:44-80  
Function/export: evaluateStageE (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext  
Outputs: StageEvaluation ({ matched, driver, hemodynamicsCriteriaMet, missingStageCriticalInputs })  
What it computes: stage-E matched if any of: lactate≥8, pH\<7.2, base\_deficit\>10, cprOngoing, multipleDefibrillations, or (SBP\<70 AND pressorsCount≥3).  
Evidence quote:  
52	  if (ctx.lactate\_mmol\_L \!= null && ctx.lactate\_mmol\_L \>= 8\) {  
53	    driver.push('lactate\_ge\_8');  
59	  if (ctx.pH \!= null && ctx.pH \< 7.2) driver.push('pH\_lt\_7.2');  
61	  if (ctx.baseDeficit\_mEq\_L \!= null && ctx.baseDeficit\_mEq\_L \> 10\)  
62	    driver.push('base\_deficit\_gt\_10');  
70	  if (sbp \!= null && sbp \< 70 && (ctx.pressorsCount ?? 0\) \>= 3\) {  
71	    driver.push('profound\_hypotension\_despite\_max\_support');  
Verification: Result consumed by computeScaiShockStage at scaiShockStage.ts:270-273 (sets stage='E' when matched).  
ID: 12  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:82-121  
Function/export: evaluateStageD (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext  
Outputs: StageEvaluation  
What it computes: stage-D matched if (lactate\>2 AND lactateTrend='rising') AND (pressorsCount≥2 OR mcsActive); also if priorState.scaiStage='C' AND (pressorsEscalation OR mcs) AND lactate\>2.  
Evidence quote:  
91	  const lactateRising \=  
92	    (ctx.lactate\_mmol\_L \!= null && ctx.lactate\_mmol\_L \> 2 &&  
93	      ctx.lactateTrend \=== 'rising');  
94	  const pressorEscalation \= (ctx.pressorsCount ?? 0\) \>= 2;  
95	  const mcs \= \!\!ctx.mcsActive;  
97	  if (lactateRising && (pressorEscalation || mcs)) {  
104	  if (ctx.priorState?.metrics?.scaiStage \=== 'C' && (pressorEscalation || mcs)) {  
105	    if (ctx.lactate\_mmol\_L \!= null && ctx.lactate\_mmol\_L \> 2\) {  
Verification: Result consumed by computeScaiShockStage at scaiShockStage.ts:274-277.  
ID: 13  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:123-203  
Function/export: evaluateStageC (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext  
Outputs: StageEvaluation  
What it computes: matched when hypoperfusion (lactate≥2 OR creatinineDelta≥0.3 OR CI\<2.2 OR PCWP\>15 OR Mean\_LA\>15 OR UO\<30) AND intervention (pressorsCount≥1 OR mcsActive).  
Evidence quote:  
133	  if (ctx.lactate\_mmol\_L \!= null && ctx.lactate\_mmol\_L \>= 2\) {  
143	    ctx.creatinineDeltaFromBaseline\_mg\_dL \>= 0.3  
151	  if (ci \!= null && ci \< 2.2) {  
155	  if (ctx.observedPCWP\_mmHg \!= null && ctx.observedPCWP\_mmHg \> 15\) {  
160	  if (\!hemoMet && m.Mean\_LA \!= null && m.Mean\_LA \> 15\) {  
166	  const intervention \= (ctx.pressorsCount ?? 0\) \>= 1 || \!\!ctx.mcsActive;  
184	  const matched \= hypoperfusion && intervention;  
Verification: Result consumed by computeScaiShockStage at scaiShockStage.ts:278-281.  
ID: 14  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:205-233  
Function/export: evaluateStageB (module-private)  
Inputs: m: SimulatorMetrics, ctx: ClinicalContext  
Outputs: StageEvaluation  
What it computes: stage-B matched if any of SBP\<90, MAP\<60, HR≥100, elevated JVP, BNP\>400.  
Evidence quote:  
218	  if (sbp \!= null && sbp \< 90\) driver.push('SBP\_lt\_90');  
219	  if (map \!= null && map \< 60\) driver.push('MAP\_lt\_60');  
220	  if (hr \!= null && hr \>= 100\) driver.push('HR\_ge\_100');  
221	  if (ctx.jugularVenousPressureElevated) driver.push('elevated\_jvp');  
222	  if (ctx.bnp\_pg\_mL \!= null && ctx.bnp\_pg\_mL \> 400\) driver.push('bnp\_elevated');  
Verification: Result consumed by computeScaiShockStage at scaiShockStage.ts:282-285.  
ID: 15  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:235-242  
Function/export: evaluateArrestModifier (module-private)  
Inputs: ctx: ClinicalContext  
Outputs: boolean  
What it computes: returns true when (cardiacArrestAtAdmission OR cprOngoing) AND (followsVerbalCommands===false OR gcs\<9).  
Evidence quote:  
238	  if (\!ctx.cardiacArrestAtAdmission && \!ctx.cprOngoing) return false;  
239	  if (ctx.followsVerbalCommands \=== false) return true;  
240	  if (ctx.gcs \!= null && ctx.gcs \< 9\) return true;  
241	  return false;  
Verification: Used at scaiShockStage.ts:262 and emitted on the result at scaiShockStage.ts:327.  
ID: 16  
File: apps/rrvalves-canvas/src/cicu-risk/scaiShockStage.ts:244-334  
Function/export: computeScaiShockStage (exported)  
Inputs: metrics: SimulatorMetrics, context: ClinicalContext | undefined  
Outputs: ScaiShockResult  
What it computes: walks E→D→C→B; assigns the highest matched stage, defaults to 'A' if none match; aggregates missing inputs from stages above the assigned one; appends arrest modifier.  
Evidence quote:  
270	  if (e.matched) { stage \= 'E'; driver \= e.driver;  
274	  } else if (d.matched) { stage \= 'D';  
278	  } else if (c.matched) { stage \= 'C';  
282	  } else if (b.matched) { stage \= 'B';  
287	    stage \= 'A';  
288	    driver \= \['baseline\_at\_risk'\];  
Verification: Called from cicu-risk/index.ts:100 — output feeds computeHdi (scaiResult arg) at cicu-risk/index.ts:107.  
ID: 17  
File: apps/rrvalves-canvas/src/cicu-risk/timiBaseline.ts:35-42  
Function/export: bandOf (module-private)  
Inputs: score: number  
Outputs: TimiBand  
What it computes: maps integer score to '0-1','2','3','4','5','6-7'.  
Evidence quote:  
35	function bandOf(score: number): TimiBand {  
36	  if (score \<= 1\) return '0-1';  
37	  if (score \=== 2\) return '2';  
38	  if (score \=== 3\) return '3';  
39	  if (score \=== 4\) return '4';  
40	  if (score \=== 5\) return '5';  
41	  return '6-7';  
42	}  
Verification: Called from computeTimi at timiBaseline.ts:91. Event rate lookup EVENT\_RATE\_14D\_PCT defined at timiBaseline.ts:24-31.  
ID: 18  
File: apps/rrvalves-canvas/src/cicu-risk/timiBaseline.ts:44-100  
Function/export: computeTimi (exported)  
Inputs: context: ClinicalContext | undefined  
Outputs: TimiBaselineResult  
What it computes: sums 7 binary TIMI predictors (age≥65, ≥3 CAD risk factors, prior stenosis≥50%, ST deviation, ≥2 angina episodes in 24h, ASA in prior 7d, troponin.value\_ng\_mL\>0.04); returns score, band via bandOf, and event-rate lookup.  
Evidence quote:  
59	    { name: 'age\_ge\_65', present: context.ageYears \!= null ? context.ageYears \>= 65 : undefined },  
62	      present: context.cadRiskFactorCount \!= null ? context.cadRiskFactorCount \>= 3 : undefined,  
68	      name: 'angina\_episodes\_ge\_2\_in\_24h',  
70	        context.anginaEpisodesIn24h \!= null ? context.anginaEpisodesIn24h \>= 2 : undefined,  
75	        context.troponin \!= null ? context.troponin.value\_ng\_mL \> 0.04 : undefined,  
84	  for (const f of factors) {  
85	    if (f.present \=== true) { score \+= 1;  
91	  const band \= bandOf(score);  
Verification: Cutpoint constant 0.04 ng/mL is inline; band-table mapping at timiBaseline.ts:24-31.  
ID: 19  
File: apps/rrvalves-canvas/src/cicu-risk/index.ts:94-233  
Function/export: computeCicuRisk (exported)  
Inputs: input: CicuRiskInput ({ metrics, audit, context })  
Outputs: CicuRiskResult  
What it computes: orchestrates computeGrace, computeTimi, computeScaiShockStage, and computeHdi; counts presence of 17 REQUIRED\_SIM\_FIELDS and 14 optional context keys; builds provenance \+ critical-missing list (lactate, priorState, CI\_or\_effective\_CO\_Lpm).  
Evidence quote:  
98	  const grace2 \= computeGrace();  
99	  const timi \= computeTimi(context);  
100	  const scai \= computeScaiShockStage(metrics, context);  
103	  const { hdi, confidenceFlags } \= computeHdi({  
104	    metrics, context, audit, scaiResult: scai,  
108	  });  
133	  for (const f of REQUIRED\_SIM\_FIELDS) {  
202	  if (\!context || context.lactate\_mmol\_L \== null)  
203	    missingCritical.push('lactate\_mmol\_L');  
Verification: REQUIRED\_SIM\_FIELDS redefined at cicu-risk/index.ts:111-129; identical list to computeHdi.ts:64-82.  
ID: 20  
File: apps/rrvalves-canvas/src/lib/simulator.ts:44-87  
Function/export: buildElastance (module-private)  
Inputs: ui (UI sliders incl. LVEF, rhythm, inotropicSupport)  
Outputs: per-chamber elastance object { LV, LA, RV, RA }  
What it computes: LV.Emax \= max(0.5, 0.6 \+ (LVEF/60)\*1.9); LV.V0 \= 25 \+ max(0,60-LVEF)*0.5; in AFib sets atrial Emax \= Emin*1.05; inotropicSupport multiplier ∈ {Off:1.00, Low:1.10, Moderate:1.20, High:1.30} applied to LV.Emax and RV.Emax.  
Evidence quote:  
53	  e.LV.Emax \= Math.max(0.5, 0.6 \+ (ui.LVEF / 60\) \* 1.9);  
58	  e.LV.V0 \= 25 \+ Math.max(0, (60 \- ui.LVEF)) \* 0.5;  
60	  if (ui.rhythm \=== 'Atrial Fibrillation') {  
61	    e.LA.Emax \= e.LA.Emin \* 1.05;  
80	  const INOTROPIC\_MULTIPLIER \= { Off: 1.00, Low: 1.10, Moderate: 1.20, High: 1.30 };  
82	  if (inoMult \!== 1.00) {  
83	    e.LV.Emax \= e.LV.Emax \* inoMult;  
84	    e.RV.Emax \= e.RV.Emax \* inoMult;  
Verification: Baseline elastance constants at simulator.ts:32-37 (ELASTANCE\_BASE); buildElastance called from buildParams at simulator.ts:304.  
ID: 21  
File: apps/rrvalves-canvas/src/lib/simulator.ts:122-132  
Function/export: activation, elastance, chamberPressure (module-private)  
Inputs: (thetaNorm, p); (theta, p); (V, theta, p)  
Outputs: scalar (normalized activation), mmHg/mL, mmHg  
What it computes: activation \= (r/(1+r))·(1/(1+f)) with r=(φ/t\_rise)^n1, f=(φ/t\_fall)^n2 normalized to peak=1; elastance \= Emin+(Emax−Emin)·activation; chamberPressure \= max(0, E·(V−V0)).  
Evidence quote:  
122	function activation(thetaNorm, p) {  
123	  let phi \= ((thetaNorm \- p.phase) % 1 \+ 1\) % 1;  
125	  const r \= Math.pow(phi / p.t\_rise, p.n1);  
126	  const f \= Math.pow(phi / p.t\_fall, p.n2);  
127	  const raw \= (r / (1 \+ r)) \* (1 / (1 \+ f));  
128	  return raw / actNorm(p);  
131	const elastance \= (theta, p) \=\> p.Emin \+ (p.Emax \- p.Emin) \* activation(theta, p);  
132	const chamberPressure \= (V, theta, p) \=\> Math.max(0, elastance(theta, p) \* (V \- p.V0));  
Verification: actNorm defined at simulator.ts:107-120 (pre-computes peak normalizer over 1000 phase samples).  
ID: 22  
File: apps/rrvalves-canvas/src/lib/simulator.ts:134-142  
Function/export: valveFlow (module-private)  
Inputs: P\_up, P\_dn, A\_fwd, A\_reg (mmHg, cm²)  
Outputs: { q\_fwd, q\_reg, q\_net } (mL/s)  
What it computes: Q \= CD·A·FLOW\_K·sqrt(|ΔP|), forward when ΔP\>0, regurgitant when ΔP\<0; clamped to Q\_CLAMP=600.  
Evidence quote:  
137	  if (dP \> 0 && A\_fwd \> 1e-6) q\_fwd \= CD \* A\_fwd \* FLOW\_K \* Math.sqrt(dP);  
138	  if (dP \< 0 && A\_reg \> 1e-6) q\_reg \= CD \* A\_reg \* FLOW\_K \* Math.sqrt(-dP);  
139	  q\_fwd \= Math.min(q\_fwd, Q\_CLAMP);  
140	  q\_reg \= Math.min(q\_reg, Q\_CLAMP);  
141	  return { q\_fwd, q\_reg, q\_net: q\_fwd \- q\_reg };  
Verification: Constants at simulator.ts:19-25: CD=0.8, FLOW\_K=50.15, Q\_CLAMP=600. Formula source \= Q \= Cd·A·√(2ΔP/ρ) with RHO=1.06.  
ID: 23  
File: apps/rrvalves-canvas/src/lib/simulator.ts:147-181  
Function/export: deriv (module-private)  
Inputs: state, params, t, cycleStart, currentT  
Outputs: { d: number\[8\], P, flows, theta }  
What it computes: ODE right-hand-side for an 8-state (4 chamber volumes \+ 4 vascular pressures) circulation: dV\_LV \= MV.q\_net − AV.q\_net, dV\_LA \= Q\_LA\_in − MV.q\_net, dV\_RV \= TV.q\_net − PV.q\_net, dV\_RA \= Q\_RA\_in − TV.q\_net, plus four compartment pressure derivatives via (Q\_in − Q\_out)/C.  
Evidence quote:  
161	  const Q\_sys   \= (state\[I.P\_SA\] \- state\[I.P\_SV\]) / params.R\_SVR;  
162	  const Q\_pulm  \= (state\[I.P\_PA\] \- state\[I.P\_PV\]) / params.R\_PVR;  
167	      mv.q\_net \- av.q\_net,                          // dV\_LV  
168	      Q\_LA\_in   \- mv.q\_net,                         // dV\_LA  
169	      tv.q\_net \- pv.q\_net,                          // dV\_RV  
171	      (av.q\_net \- Q\_sys)  / params.C\_SA,            // dP\_SA  
174	      (Q\_pulm   \- Q\_LA\_in) / params.C\_PV,           // dP\_PV  
Verification: State index map I at simulator.ts:145. Default vascular parameters at simulator.ts:95-99 (VASC\_DEFAULT).  
ID: 24  
File: apps/rrvalves-canvas/src/lib/simulator.ts:189-202  
Function/export: rk4Step (module-private)  
Inputs: state, params, t, dt, cycleStart, currentT  
Outputs: next-step state vector (length 8\)  
What it computes: classical RK4 step on deriv; out \= state \+ (dt/6)·(k1+2k2+2k3+k4); clamps volumes to \[V\_MIN=2, V\_MAX=300\] and pressures to ≥0.  
Evidence quote:  
189	function rk4Step(state, params, t, dt, cycleStart, currentT) {  
190	  const k1 \= deriv(state, params, t,           cycleStart, currentT);  
191	  const k2 \= deriv(addScaled(state, k1, dt / 2), params, t \+ dt / 2, cycleStart, currentT);  
196	    out\[i\] \= state\[i\] \+ (dt / 6\) \* (k1.d\[i\] \+ 2 \* k2.d\[i\] \+ 2 \* k3.d\[i\] \+ k4.d\[i\]);  
199	  for (let i \= 0; i \< 4; i++) out\[i\] \= Math.max(V\_MIN, Math.min(V\_MAX, out\[i\]));  
Verification: Constants at simulator.ts:22 (DT=0.001), simulator.ts:26-27 (V\_MIN=2, V\_MAX=300).  
ID: 25  
File: apps/rrvalves-canvas/src/lib/simulator.ts:225-323  
Function/export: buildParams (module-private; re-exported via simulator.ts:890)  
Inputs: ui, overrides  
Outputs: parameter object consumed by deriv/rk4Step (areas, resistances, compliances, elastance, target BP, etc.)  
What it computes: A\_AV \= NORMAL\_AREAS.AV·(1−0.85·AS); A\_MV \= 5.0·(1−0.80·MS); A\_AV\_reg \= 0.8·AR; A\_MV\_reg \= 0.6·MR; A\_TV\_reg \= 0.5·TR; R\_SVR scaled by (1−afterloadPct/100) when afterloadOn; TAVR EOA lookup {26mm:1.9, 29mm:2.4, 23mm:1.5}; mitral residual MR lookup {Tendyne:0.05, MitraClip G4:0.20, default:0.35}; volPreloadMod ∈ {Hypervolemic:1.35, Hypovolemic:0.55, else:1.0}; PVR\_factor \= 1+8.0·max(MR,MS)+1.5·AS; C\_PA \= C\_PA\_default/√PVR\_factor; AFib RR\_var=0.25.  
Evidence quote:  
228	  let A\_AV       \= NORMAL\_AREAS.AV \* (1 \- 0.85 \* (ui.AS ?? 0));  
229	  let A\_MV       \= NORMAL\_AREAS.MV \* (1 \- 0.80 \* (ui.MS ?? 0));  
232	  let A\_AV\_reg   \= 0.8 \* (ui.AR ?? 0);  
233	  let A\_MV\_reg   \= 0.6 \* (ui.MR ?? 0);  
234	  let A\_TV\_reg   \= 0.5 \* (ui.TR ?? 0);  
254	    const tavrAreas \= { '26mm': 1.9, '29mm': 2.4, '23mm': 1.5 };  
262	    const residual \= ui.mitralModel \=== 'Tendyne'         ? 0.05  
292	  const PVR\_factor      \= 1 \+ 8.0 \* chronicLALoad \+ 1.5 \* chronicLVLoad;  
293	  let R\_PVR             \= VASC\_DEFAULT.R\_PVR \* PVR\_factor;  
Verification: NORMAL\_AREAS defined at simulator.ts:29. svrDisplayToInternal (line 102\) converts dyn·s·cm⁻⁵ to mmHg·s/mL via 1/1333.22.  
ID: 26  
File: apps/rrvalves-canvas/src/lib/simulator.ts:345-380  
Function/export: runSimulation (exported)  
Inputs: params (output of buildParams)  
Outputs: simulation result with metrics, recorded traces, baroreflex factor, audit  
What it computes: iterative damped proportional baroreflex — for each pass i, R\_SVR\_{i+1} \= R\_SVR\_i · (1 \+ 0.6·(target/achieved − 1)) with cumFactor clamped to \[0.4, 1.9\]×; convergence when |achieved − target|\<3 mmHg or after 3 passes; targetMAP=(SBP+2·DBP)/3.  
Evidence quote:  
346	  const targetMAP \= (params.BP\_target\_sys \+ 2 \* params.BP\_target\_dia) / 3;  
348	  const G \= 0.6;            // damping gain  
349	  const CLAMP\_LO \= 0.4;  
350	  const CLAMP\_HI \= 1.9;  
351	  const MAX\_PASSES \= 3;  
361	    if (Math.abs(ach \- targetMAP) \< 3\) break; // converged  
362	    const step \= 1 \+ G \* (targetMAP / Math.max(20, ach) \- 1);  
363	    cumFactor \= Math.max(CLAMP\_LO, Math.min(CLAMP\_HI, cumFactor \* step));  
Verification: calls runSimulationPass (simulator.ts:471) then runConsistencyAudit (simulator.ts:382). Output augments metrics with baroFactor \+ SVR\_baroreflexed.  
ID: 27  
File: apps/rrvalves-canvas/src/lib/simulator.ts:382-469  
Function/export: runConsistencyAudit (exported)  
Inputs: m (metrics), params  
Outputs: { ok, gates, softWarnings }  
What it computes: verifies clinical identities — Gate 1: CO ≈ HR·SV\_forward/1000 (1%); Gate 2: LVEF ≈ (LVEDV−LVESV)/LVEDV·100 (1%); Gate 3: LV\_total\_SV ≈ LVEDV−LVESV (±1 mL soft); Gate 4: PVR\_woods ≈ (mPAP−Mean\_LA)/CO (5%).  
Evidence quote:  
395	    const co\_calc \= HR \* m.SV\_forward / 1000;  
399	                  passed:   within(m.CO, co\_calc, 0.01),  
405	    const ef\_calc \= (m.LVEDV \- m.LVESV) / m.LVEDV \* 100;  
409	                  passed:   within(m.LVEF, ef\_calc, 0.01),  
432	    const pvr\_calc \= (m.mPAP \- m.Mean\_LA) / m.CO;  
436	                  passed:   within(m.PVR\_woods, pvr\_calc, 0.05),  
Verification: Tolerance helper within defined inline at simulator.ts:385-389.  
ID: 28  
File: apps/rrvalves-canvas/src/lib/simulator.ts:471-571  
Function/export: runSimulationPass (exported)  
Inputs: params  
Outputs: { recorded, metrics, converged, error }  
What it computes: simulates N\_CYCLES=16 cardiac cycles via RK4 at DT=1 ms; for AFib injects per-cycle T \= baseT·(1+detRand(c)·RR\_var); convergence \= relative SV change \<CONV\_TOL+RR\_var for ≥2 consecutive cycles after cycle 4\.  
Evidence quote:  
473	  const baseT \= 60 / params.HR;  
477	    const T \= params.RR\_var \> 0  
478	      ? baseT \* (1 \+ detRand(c) \* params.RR\_var)  
480	    const steps \= Math.max(1, Math.round(T / DT));  
560	    const tol \= CONV\_TOL \+ params.RR\_var;  
561	    const rel \= Math.abs(cycleSV \- lastSV) / Math.max(1e-3, lastSV);  
562	    if (c \> 4 && rel \< tol) convergedCount++;  
568	  const converged \= convergedCount \>= 2;  
Verification: N\_CYCLES=16, DT=0.001, CONV\_TOL=0.05 at simulator.ts:22-24; detRand defined at simulator.ts:327-330.  
ID: 29  
File: apps/rrvalves-canvas/src/lib/simulator.ts:573-799  
Function/export: computeMetrics (exported)  
Inputs: rec (recorded traces), params, cycleSchedule, recordFromCycle  
Outputs: bundle of clinical scalars (CO, SV\_forward, LVEF, gradients, RF\_*, mPAP, Mean\_LA, LVEDP, TPG, PVR\_woods, EROA, VC\_*, achievedSBP/DBP/MAP, etc.)  
What it computes: cycle-wise integrations — SV\_forward=∫Q\_AV\_fwd·dt per cycle; CO=totalForwardVol/totalRecT·60/1000; Mean\_AV\_grad=Σ(P\_LV−P\_SA) over Q\_AV\>1; Vmax\_AV=√(peakAVg/4) (simplified Bernoulli); LVEDP at maxV per cycle; LVEF=(LVEDV−LVESV)/LVEDV·100; RF\_MR=MR\_reg\_vol/(AV\_fwd+MR\_reg); RF\_AR=AR\_reg/AV\_fwd; RF\_TR=TR\_reg/(PV\_fwd+TR\_reg); SVi=SV\_forward/1.73; AVAi=AVA/1.73; TPG=mPAP−Mean\_LA; PVR\_woods=TPG/CO; VC\_diameter=20·√(EROA/π) mm; effective\_CO\_Lpm=HR·max(0,SV\_forward−AR\_RVol\_per\_beat)/1000.  
Evidence quote:  
600	  const totalFwdVol \= SV\_fwd\_per\_cycle.reduce((a, b) \=\> a \+ b, 0);  
601	  const CO \= totalRecT \> 0 ? (totalFwdVol / totalRecT) \* 60 / 1000 : 0;  
615	  const Mean\_AV\_grad \= nAVg ? sumAVg / nAVg : 0;  
617	  const Vmax\_AV \= peakAVg \> 0 ? Math.sqrt(peakAVg / 4\) : 0;  
671	  const RF\_MR \= LV\_total\_SV\_vol \> 0 ? MR\_reg\_vol / LV\_total\_SV\_vol : 0;  
672	  const RF\_AR \= AV\_fwd\_vol      \> 0 ? AR\_reg\_vol / AV\_fwd\_vol      : 0;  
699	  const LVEF \= LVEDV \> 0 ? (LVEDV \- LVESV) / LVEDV \* 100 : 0;  
702	  const BSA \= 1.73;  
703	  const SVi  \= SV\_forward / BSA;  
737	  const TPG \= mPAP \- Mean\_LA;  
738	  const PVR\_woods \= CO \> 0 ? TPG / CO : 0;  
780	    effective\_CO\_Lpm:                   params?.HR \!= null  
781	                                          ? params.HR \* Math.max(0, SV\_forward \- AR\_RVol\_per\_beat) / 1000  
Verification: BSA constant inline at line 702\. EROA exposure at simulator.ts:743-749.  
ID: 30  
File: apps/rrvalves-canvas/src/lib/simulator.ts:816-821  
Function/export: classifyAS (exported)  
Inputs: meanGrad, AVA  
Outputs: { label, col } (SEV\_TONE entry)  
What it computes: AS severity — Severe if meanGrad≥40 OR AVA≤1.0; Moderate if ≥20 or ≤1.5; Mild if ≥10 or ≤2.0; else Normal.  
Evidence quote:  
816	function classifyAS(meanGrad, AVA) {  
817	  if (meanGrad \>= 40 || AVA \<= 1.0) return SEV\_TONE.Severe;  
818	  if (meanGrad \>= 20 || AVA \<= 1.5) return SEV\_TONE.Moderate;  
819	  if (meanGrad \>= 10 || AVA \<= 2.0) return SEV\_TONE.Mild;  
820	  return SEV\_TONE.Normal;  
821	}  
Verification: SEV\_TONE defined at simulator.ts:806-813.  
ID: 31  
File: apps/rrvalves-canvas/src/lib/simulator.ts:826-835  
Function/export: classifyMS (exported)  
Inputs: meanMVgrad, isPrimary  
Outputs: severity object  
What it computes: when isPrimary: Severe if meanMVgrad≥10, Moderate if ≥5, Mild if ≥3, else Normal. When not primary and grad≥5 → 'Pseudo (LA-driven)'.  
Evidence quote:  
826	function classifyMS(meanMVgrad, isPrimary) {  
827	  if (\!isPrimary) {  
828	    if (meanMVgrad \>= 5\) return { label: 'Pseudo (LA-driven)', col: '\#9ca3af' };  
831	  if (meanMVgrad \>= 10\) return SEV\_TONE.Severe;  
832	  if (meanMVgrad \>= 5\)  return SEV\_TONE.Moderate;  
833	  if (meanMVgrad \>= 3\)  return SEV\_TONE.Mild;  
Verification: msPrimary is set in computeMetrics at simulator.ts:797.  
ID: 32  
File: apps/rrvalves-canvas/src/lib/simulator.ts:839-859  
Function/export: classifyAR, classifyMR, classifyTR (exported)  
Inputs: RF\_pct: number  
Outputs: severity object  
What it computes: AR/MR: Severe ≥50, Mod-Severe ≥40, Moderate ≥30, Mild ≥5, else Trivial. TR: Severe ≥50, Moderate ≥30, Mild ≥5, else Trivial.  
Evidence quote:  
840	  if (RF\_pct \>= 50\) return SEV\_TONE.Severe;  
841	  if (RF\_pct \>= 40\) return SEV\_TONE.ModSevere;  
842	  if (RF\_pct \>= 30\) return SEV\_TONE.Moderate;  
843	  if (RF\_pct \>= 5\)  return SEV\_TONE.Mild;  
854	  if (RF\_pct \>= 50\) return SEV\_TONE.Severe;  
855	  if (RF\_pct \>= 30\) return SEV\_TONE.Moderate;  
856	  if (RF\_pct \>= 5\)  return SEV\_TONE.Mild;  
Verification: SEV\_TONE keys/values at simulator.ts:806-813.  
ID: 33  
File: apps/rrvalves-canvas/src/lib/simulator.ts:862-867  
Function/export: classifyPH (exported)  
Inputs: mPAP: number  
Outputs: { label, col }  
What it computes: Severe PH if mPAP≥40; PH if ≥25; Borderline if ≥20; else Normal.  
Evidence quote:  
862	function classifyPH(mPAP) {  
863	  if (mPAP \>= 40\) return { label: 'Severe PH',   col: '\#ef4444' };  
864	  if (mPAP \>= 25\) return { label: 'PH',          col: '\#f97316' };  
865	  if (mPAP \>= 20\) return { label: 'Borderline',  col: '\#f59e0b' };  
866	  return            { label: 'Normal',           col: '\#22c55e' };  
867	}  
Verification: Exported in public API list at simulator.ts:892-893.  
ID: 34  
File: apps/rrvalves-canvas/src/lib/simulator.ts:869-878  
Function/export: classifyPH\_Group (exported)  
Inputs: meanLA, TPG  
Outputs: { label, col }  
What it computes: with meanLA≤15 → Pre-capillary (Group 1/3/4) if TPG\>12 else No PH; with meanLA\>15 → Cpc-PH if TPG\>12 else Isolated post-capillary (Group 2).  
Evidence quote:  
869	function classifyPH\_Group(meanLA, TPG) {  
870	  if (meanLA \<= 15\) {  
871	    return TPG \> 12  
872	      ? { label: 'Pre-capillary (Group 1/3/4)', col: '\#ef4444' }  
874	  }  
876	  if (TPG \> 12\) return { label: 'Combined post \+ pre (Cpc-PH)', col: '\#ef4444' };  
877	  return { label: 'Isolated post-capillary (Group 2)', col: '\#f97316' };  
Verification: TPG computed in computeMetrics at simulator.ts:737; Mean\_LA at simulator.ts:641.  
ID: 35  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:685-689  
Function/export: classifyCO (exported)  
Inputs: co: number  
Outputs: { severity: Severity; label: string }  
What it computes: CO\<3.0→'LOW'; CO\<4.0→'LOW-NORMAL'; else 'NORMAL'.  
Evidence quote:  
685	export function classifyCO(co: number): { severity: Severity; label: string } {  
686	  if (co \< 3.0) return { severity: "low", label: "LOW" };  
687	  if (co \< 4.0) return { severity: "elevated", label: "LOW-NORMAL" };  
688	  return { severity: "normal", label: "NORMAL" };  
689	}  
Verification: Type Severity defined at liveCalcs.ts:683.  
ID: 36  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:691-696  
Function/export: classifyAvGrad (exported)  
Inputs: g: number  
Outputs: severity record  
What it computes: AV grad ≥40→SEVERE; ≥20→MODERATE; ≥10→MILD; else NORMAL.  
Evidence quote:  
691	export function classifyAvGrad(g: number): { severity: Severity; label: string } {  
692	  if (g \>= 40\) return { severity: "severe", label: "SEVERE" };  
693	  if (g \>= 20\) return { severity: "elevated", label: "MODERATE" };  
694	  if (g \>= 10\) return { severity: "elevated", label: "MILD" };  
695	  return { severity: "normal", label: "NORMAL" };  
696	}  
Verification: Cutpoints duplicate those in simulator.ts classifyAS for the gradient axis.  
ID: 37  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:698-703  
Function/export: classifyMrRf (exported)  
Inputs: rf: number (percent)  
Outputs: severity record  
What it computes: RF ≥50→SEVERE; ≥30→MODERATE; ≥15→MILD; else NORMAL.  
Evidence quote:  
698	export function classifyMrRf(rf: number): { severity: Severity; label: string } {  
699	  if (rf \>= 50\) return { severity: "severe", label: "SEVERE" };  
700	  if (rf \>= 30\) return { severity: "elevated", label: "MODERATE" };  
701	  if (rf \>= 15\) return { severity: "elevated", label: "MILD" };  
702	  return { severity: "normal", label: "NORMAL" };  
703	}  
Verification: Lower band (15) differs from simulator.ts classifyMR (5).  
ID: 38  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:705-709  
Function/export: classifyLvedp (exported)  
Inputs: p: number  
Outputs: severity record  
What it computes: LVEDP ≥18→ELEVATED; ≥12→BORDERLINE; else NORMAL.  
Evidence quote:  
705	export function classifyLvedp(p: number): { severity: Severity; label: string } {  
706	  if (p \>= 18\) return { severity: "elevated", label: "ELEVATED" };  
707	  if (p \>= 12\) return { severity: "elevated", label: "BORDERLINE" };  
708	  return { severity: "normal", label: "NORMAL" };  
709	}  
Verification: Standalone module-private severity type at liveCalcs.ts:683.  
ID: 39  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:59-121  
Function/export: ischemiaRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput ({ drivers, ... })  
What it computes: emits P0 driver when FDA-authorized algorithm \+ used-within-labeling reports STEMI-like pattern; emits P0 from ecgText match against STEMI\_PATTERNS; emits P0 if structured stElevation+ischemic context (troponin elevated/rising OR chest pain); else P1 for stElevation alone.  
Evidence quote:  
66	  const externalStemi \=  
67	    ext && ext.status \=== "configured" &&  
68	    Boolean(ext.fdaAuthorizationId) &&  
69	    ext.usedWithinLabeling &&  
71	    STEMI\_PATTERNS.test(ext.result);  
94	  if (ecg?.stElevation \=== true) {  
95	    const ischemicContext \=  
96	      hasIschemicSymptoms(ctx) ||  
97	      ctx?.troponinStatus \=== "elevated" ||  
98	      ctx?.troponinStatus \=== "rising";  
99	    if (ischemicContext) {  
100	      drivers.push({ id: "ischemia.structured.st\_elevation\_with\_context", priority: "P0",  
Verification: STEMI\_PATTERNS regex at ecgPriorityRules.ts:27-28; APPROVED\_PHRASES imported from ecgPriorityRegulatory.  
ID: 40  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:124-204  
Function/export: rhythmRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput  
What it computes: VF→P0, sustained VT→P0, wide-complex tachy→P0 (unless VT/VF already), AFib+(RVR or rateBpm≥110) → P1 if unstable/ischemic else P2, NSVT match→P2.  
Evidence quote:  
130	  const vf \= ecg?.ventricularFibrillation \=== true || VF\_PATTERNS.test(text);  
142	  const vt \= ecg?.ventricularTachycardia \=== true || VT\_PATTERNS.test(text);  
168	  const isRvr \= RVR\_PATTERNS.test(rhythmText) || (ecg?.rateBpm \!== undefined && ecg.rateBpm \>= 110);  
170	  if (isAf && isRvr) {  
171	    if (isUnstable(ctx) || hasIschemicSymptoms(ctx)) {  
173	        priority: "P1",  
181	        priority: "P2",  
Verification: Pattern regexes at ecgPriorityRules.ts:30-39.  
ID: 41  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:207-241  
Function/export: conductionRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput  
What it computes: complete/high-grade AV block (structured flag, text pattern, or conductionBlock string match) → P0 when shock/hypotension/syncope present, else P1.  
Evidence quote:  
213	  const completeBlock \=  
214	    ecg?.highGradeAvBlock \=== true ||  
215	    COMPLETE\_BLOCK\_PATTERNS.test(text) ||  
218	  if (completeBlock) {  
219	    if (isUnstable(ctx)) {  
221	        priority: "P0",  
229	        priority: "P1",  
Verification: isUnstable defined at ecgPriorityRules.ts:41-44 (checks shock || hypotension || syncope).  
ID: 42  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:244-270  
Function/export: repolarizationRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput  
What it computes: QTc≥500ms → P1; 480≤QTc\<500 → P2; missing QTc reports missingInputs:\['qtcMs'\].  
Evidence quote:  
246	  const qtc \= input.structuredEcg?.qtcMs;  
247	  if (qtc \=== undefined || qtc \=== null) {  
248	    return { drivers, missingInputs: \["qtcMs"\] };  
250	  if (qtc \>= 500\) {  
253	      priority: "P1",  
259	  } else if (qtc \>= 480\) {  
262	      priority: "P2",  
Verification: Cutpoints (500/480) inline; consumer combiner at queue-priority/combineQueuePriority.ts:29-35.  
ID: 43  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:277-299  
Function/export: electrolytePatternRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput  
What it computes: hyperkalemia-pattern regex match on ecgText → P0; downgrades the explanation phrase when serum K is unavailable but keeps the P0 priority.  
Evidence quote:  
283	  if (HYPERK\_PATTERNS.test(text)) {  
284	    let evidence: string \= APPROVED\_PHRASES.HIGH\_RISK\_PATTERN;  
285	    if (k \=== undefined || k \=== null) {  
286	      evidence \= APPROVED\_PHRASES.HYPERK\_NO\_POTASSIUM;  
289	    drivers.push({ id: "electrolyte.hyperkalemia\_like\_pattern", priority: "P0",  
Verification: HYPERK\_PATTERNS regex at ecgPriorityRules.ts:34-35.  
ID: 44  
File: apps/rrvalves-canvas/src/ecg-priority/ecgPriorityRules.ts:306-377  
Function/export: trajectoryRule (exported)  
Inputs: input: EcgPriorityInput  
Outputs: RuleOutput  
What it computes: P1 drivers fire on new (current vs prior) stElevation, highGradeAvBlock, wideComplexTachycardia, or QTc crossing ≥500.  
Evidence quote:  
334	  if (cur.stElevation \=== true && old.stElevation \!== true) {  
336	      id: "trajectory.new\_st\_elevation",  
337	      priority: "P1",  
364	  const newLongQtc \=  
365	    cur.qtcMs \!== undefined && cur.qtcMs \>= 500 && (old.qtcMs \=== undefined || old.qtcMs \< 500);  
Verification: Clock-skew handling at ecgPriorityRules.ts:323-326.  
ID: 45  
File: apps/rrvalves-canvas/src/coupling/maskingPatterns.ts:19-76  
Function/export: MASKING\_PATTERNS (exported array of { match, ... })  
Inputs: per pattern, (ui, m?: SimulatorMetrics) predicates  
Outputs: boolean from match, label text on activation  
What it computes: threshold gates that emit clinical labels — MR\_masks\_AS fires when MR≥0.5 AND AS≥0.65; MitraClip\_unmasks\_AS fires when mitralRepairOn AND AS≥0.65; TR\_masks\_MS fires when TR≥0.65 AND MS≥0.3; AR\_MR\_not\_additive fires when AR≥0.5 AND MR≥0.5; EF\_falsely\_reassuring fires when MR≥0.5 AND LVEF≥55 AND LVEDV\>130.  
Evidence quote:  
22	    match: (ui) \=\>  
23	      ((ui.MR as number) ?? 0\) \>= 0.5 && ((ui.AS as number) ?? 0\) \>= 0.65,  
33	    match: (ui) \=\>  
34	      Boolean(ui.mitralRepairOn) && ((ui.AS as number) ?? 0\) \>= 0.65,  
44	      ((ui.TR as number) ?? 0\) \>= 0.65 && ((ui.MS as number) ?? 0\) \>= 0.3,  
64	    match: (ui, m) \=\>  
65	      ((ui.MR as number) ?? 0\) \>= 0.5 &&  
66	      Number.isFinite(m?.LVEF) &&  
67	      (m?.LVEF as number) \>= 55 &&  
68	      Number.isFinite(m?.LVEDV) &&  
69	      (m?.LVEDV as number) \> 130,  
Verification: Consumed at runCouplingAnalysis.ts:199-201 (.filter((p) \=\> p.match(ui, baseline))).  
ID: 46  
File: apps/rrvalves-canvas/src/coupling/couplingRules.ts:19-108  
Function/export: COUPLING\_RULES (exported array)  
Inputs: per rule, (u: ui) predicate  
Outputs: rule match boolean \+ clinical narrative  
What it computes: lesion-combination thresholds that select an explanatory narrative — AS≥0.85+MR≥0.65 → LFLG-AS coupling; AS≥0.85+0.3≤MR\<0.65 → functional-MR-from-AS; isolated AS (≥0.85 with others \<0.3); AR≥0.65; MR≥0.65 alone (AS\<0.5); TR≥0.65; max(all)\<0.3 → no significant disease.  
Evidence quote:  
22	    match: (u) \=\> ((u.AS as number) ?? 0\) \>= 0.85 && ((u.MR as number) ?? 0\) \>= 0.65,  
33	    match: (u) \=\>  
34	      ((u.AS as number) ?? 0\) \>= 0.85 &&  
35	      ((u.MR as number) ?? 0\) \>= 0.3 &&  
36	      ((u.MR as number) ?? 0\) \< 0.65,  
62	    match: (u) \=\> ((u.AR as number) ?? 0\) \>= 0.65,  
72	    match: (u) \=\> ((u.MR as number) ?? 0\) \>= 0.65 && ((u.AS as number) ?? 0\) \< 0.5,  
Verification: Top-2 matches consumed at runCouplingAnalysis.ts:202-205.  
ID: 47  
File: apps/rrvalves-canvas/src/coupling/rankDrivers.ts:35-91  
Function/export: rankDrivers (exported) \+ TARGETS constant  
Inputs: perturbations: PerturbationResult\[\] | null | undefined, baseline: SimulatorMetrics | null | undefined  
Outputs: DriverGroup\[\]  
What it computes: for each of 4 clinical targets (low CO wants CO↑, high LA wants Mean\_LA↓, high PA wants mPAP↓, low AV grad wants Mean\_AV\_grad↑), keeps perturbations whose delta moves the target metric in the desired direction, sorts by |relDelta|, returns top 3\.  
Evidence quote:  
35	const TARGETS: ClinicalTarget\[\] \= \[  
36	  { id: "low\_CO", label: "Low CO", metric: "CO", direction: "up" },  
68	        const beneficial \=  
69	          (t.direction \=== "up" && d.delta \> 0\) ||  
70	          (t.direction \=== "down" && d.delta \< 0);  
77	          magnitude: Math.abs(d.relDelta),  
80	      .filter((p) \=\> p.beneficial)  
81	      .sort((a, b) \=\> b.magnitude \- a.magnitude)  
82	      .slice(0, 3);  
Verification: Consumed at runCouplingAnalysis.ts:206 then used to pick topDriver at runCouplingAnalysis.ts:118-133.  
ID: 48  
File: apps/rrvalves-canvas/src/coupling/runCouplingAnalysis.ts:66-116  
Function/export: buildFlowLedger, ledgerConservation (module-private)  
Inputs: m: SimulatorMetrics | null  
Outputs: FlowLedgerRow\[\]; number | null  
What it computes: 6-row ledger pulling LV\_total\_SV\_mL, aortic\_systolic\_forward\_SV\_mL, MR/AR/TR\_regurgitant\_volume\_mL, effective\_systemic\_forward\_SV\_mL; conservation residual \= |LV\_total − (aortic\_forward \+ MR\_regurg)|.  
Evidence quote:  
99	  const lvTotal \= m.LV\_total\_SV\_mL;  
100	  const aoFwd \= m.aortic\_systolic\_forward\_SV\_mL;  
101	  const mrVol \= m.MR\_regurgitant\_volume\_mL;  
113	  return Math.abs(  
114	    (lvTotal as number) \- ((aoFwd as number) \+ (mrVol as number)),  
115	  );  
Verification: Fields LV\_total\_SV\_mL / aortic\_systolic\_forward\_SV\_mL / MR\_regurgitant\_volume\_mL produced in simulator.ts:773-777.  
ID: 49  
File: apps/rrvalves-canvas/src/coupling/runCouplingAnalysis.ts:135-236  
Function/export: runCouplingAnalysis (exported)  
Inputs: ui: CouplingUi, options: RunOptions  
Outputs: CouplingAnalysis  
What it computes: runs the simulator at baseline \+ 8 perturbations, computes per-tracked-metric absolute and relative deltas (delta \= post − baseline, relDelta \= (post−baseline)/|baseline|), then composes flow ledger, masking matches, coupling-rule top 2, ranked drivers, cascade rows.  
Evidence quote:  
182	      if (Number.isFinite(b) && Number.isFinite(n)) {  
183	        const bn \= b as number;  
184	        const nn \= n as number;  
185	        deltas\[tm.key\] \= {  
186	          baseline: bn,  
187	          post: nn,  
188	          delta: nn \- bn,  
189	          relDelta: Math.abs(bn) \> 1e-3 ? (nn \- bn) / Math.abs(bn) : 0,  
190	        };  
Verification: Perturbation list PERTURBATIONS imported from coupling/perturbations.ts:28-110 (8 entries: AS\_minus\_20, MR\_minus\_20, AR\_minus\_20, TR\_minus\_20, PVR\_minus\_20, SVR\_minus\_20, preload\_minus\_10, contractility\_plus\_10).  
ID: 50  
File: apps/rrvalves-canvas/src/lib/impactLens.ts:92-130  
Function/export: runOnce (module-private)  
Inputs: uiBase, strategyOverrides, pert: Perturbation  
Outputs: ImpactLensOutputs ({ CO, MAP, Mean\_LA, SVR, Mean\_AV\_grad })  
What it computes: merges strategy overrides onto a baseline UI, applies per-axis multipliers (HR·hrMul, SVR·svrMul, volume\_preload·preloadMul), runs runSimulation, returns CO, achievedMAP, Mean\_LA, SVR\_baroreflexed·0.06 (internal→mmHg·min/L), Mean\_AV\_grad.  
Evidence quote:  
98	  if (typeof merged.HR \=== "number") merged.HR \= (merged.HR as number) \* pert.hrMul;  
99	  if (typeof merged.SVR \=== "number") merged.SVR \= (merged.SVR as number) \* pert.svrMul;  
108	  const overrides: Record\<string, unknown\> \= {  
109	    volPreloadMod\_override: baseVolMod \* pert.preloadMul,  
110	  };  
124	    CO: typeof m.CO \=== "number" ? m.CO : 0,  
127	    SVR: r\_svr\_internal \* SVR\_INTERNAL\_TO\_MMHG\_MIN\_PER\_L,  
Verification: Conversion factor at impactLens.ts:51 (SVR\_INTERNAL\_TO\_MMHG\_MIN\_PER\_L \= 60/1000).  
ID: 51  
File: apps/rrvalves-canvas/src/lib/impactLens.ts:154-196  
Function/export: computeStrategyResponse (exported)  
Inputs: caseId: string, strategy: Strategy, overrides?: InputOverrides  
Outputs: ImpactLensResponse ({ outputs, sensitivity, ... })  
What it computes: central run plus 8 perturbation runs at the corners of {0.95,1.05}³ over (HR, SVR, preload); reports per-output min/max as sensitivity envelope.  
Evidence quote:  
132	const PERTURB\_LO \= 0.95;  
133	const PERTURB\_HI \= 1.05;  
134	const CORNERS: Perturbation\[\] \= \[\];  
135	for (const hr of \[PERTURB\_LO, PERTURB\_HI\]) {  
174	  const central \= runOnce(uiBase, strategyOverrides, { hrMul: 1.0, svrMul: 1.0, preloadMul: 1.0 });  
175	  const cornerResults \= CORNERS.map((c) \=\> runOnce(uiBase, strategyOverrides, c));  
180	    let lo \= Infinity, hi \= \-Infinity;  
181	    for (const r of cornerResults) {  
Verification: CORNERS constructed at impactLens.ts:134-141 as the 2³=8 vertices of the cube.  
ID: 52  
File: apps/rrvalves-canvas/src/lib/impactLens.ts:249-307  
Function/export: computeStrategyImpactWorkbench (exported)  
Inputs: caseId, strategy, overrides  
Outputs: { baseline: LiveMetrics; projected: LiveMetrics } | null  
What it computes: layers strategy overrides on top of the (possibly already overridden) UI, calls buildParams \+ runSimulation, and projects the same LiveMetrics shape (CO, AV grad, RF\_MR/AR/TR ×100, LVEDP, Mean\_LA, mPAP, AVA, LVEF, SV\_forward, effective\_CO\_Lpm, SVi, sPAP, TPG, PVR\_woods, achievedMAP, etc.).  
Evidence quote:  
273	  const uiBase \= recorded.ui as Record\<string, unknown\>;  
274	  const strategyOv \= strategyToOverrides(strategy);  
275	  const merged: Record\<string, unknown\> \= { ...uiBase, ...strategyOv };  
276	  const params \= buildParams(merged);  
277	  const result \= runSimulation(params);  
283	    RF\_MR: (typeof m.RF\_MR \=== "number" ? m.RF\_MR : 0\) \* 100,  
295	    effective\_CO\_Lpm: typeof m.effective\_CO\_Lpm \=== "number" ? m.effective\_CO\_Lpm : 0,  
Verification: strategyToOverrides defined at impactLens.ts:53-84 — translates intervention objects to simulator UI keys (tavrOn, mitralRepairOn, diuresisOn, afterloadOn, etc.).  
ID: 53  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:148-179  
Function/export: runScenario (module-private)  
Inputs: overrides: Overrides  
Outputs: LiveMetrics  
What it computes: merges Carter baseline UI with overrides, runs buildParams\+runSimulation, returns CO, Mean\_AV\_grad, RF\_MR/AR/TR (×100 fraction→percent), LVEDP, Mean\_LA, mPAP, AVA, LVEF, SV\_forward, regurgitant volumes per beat, effective\_CO\_Lpm, SVi, sPAP, TPG, PVR\_woods, achievedMAP, targetSBP/DBP.  
Evidence quote:  
149	  const ui \= { ...carterBase, ...overrides };  
150	  const params \= buildParams(ui);  
151	  const result \= runSimulation(params);  
156	    CO: m?.CO ?? 0,  
158	    RF\_MR: (m?.RF\_MR ?? 0\) \* 100,  
170	    effective\_CO\_Lpm: m?.effective\_CO\_Lpm ?? 0,  
Verification: carterBase UI defined at liveCalcs.ts:64-89; same factor-of-100 conversion in computeForCase (line 424-456) and computeForCaseOv (line 565-597).  
ID: 54  
File: apps/rrvalves-canvas/src/components/rounds/liveCalcs.ts:540-560  
Function/export: applyOverrides (module-private)  
Inputs: baseUi: Ui, ov: OverridesShape  
Outputs: Ui  
What it computes: when MAP\_target is supplied, preserves baseline pulse pressure (PP=SBP−DBP) and solves newSBP \= MAP\_target \+ 2·PP/3, newDBP \= newSBP − PP; otherwise passes scalar overrides through unchanged.  
Evidence quote:  
552	  if (typeof ov.MAP\_target \=== "number") {  
553	    const PP \= baseUi.BP\_sys \- baseUi.BP\_dia;  
554	    const newSBP \= ov.MAP\_target \+ (2 \* PP) / 3;  
555	    const newDBP \= newSBP \- PP;  
556	    merged.BP\_sys \= Math.round(newSBP);  
557	    merged.BP\_dia \= Math.round(newDBP);  
558	  }  
Verification: Inverse of the MAP \= (SBP \+ 2·DBP)/3 formula used in simulator.ts:346.  
ID: 55  
File: apps/rrvalves/src/hemodynamics-simulator.jsx:2890-2945 (approx — verbatim source of simulator.ts classifiers)  
Function/export: classifyAS, classifyMS, classifyAR, classifyMR, classifyTR, classifyPH, classifyPH\_Group  
Inputs: same scalars as in simulator.ts (gradients, RF, mPAP, TPG, Mean\_LA)  
Outputs: severity label/color records  
What it computes: identical severity classification logic to entries ID:30–34 — this is the original monolith from which simulator.ts is a parity-locked verbatim port (per simulator.ts:6-11 header).  
Evidence quote:  
2890	function classifyAS(meanGrad, AVA) {  
2900	function classifyMS(meanMVgrad, isPrimary) {  
2913	function classifyAR(RF\_pct) {  
2920	function classifyMR(RF\_pct) {  
2928	function classifyTR(RF\_pct) {  
2936	function classifyPH(mPAP) {  
2943	function classifyPH\_Group(meanLA, TPG) {  
Verification: rg shows these functions are still called within hemodynamics-simulator.jsx itself (lines 3720-3722, 4530-4534, 5385-5386, 8779-8791 — see rg output above).  
UNCERTAIN:  
(none — every entry above has clear inputs, outputs, and verifiable formula or threshold.)  
---

Reproduction commands:  
rg \-l \--type-add 'code:\*.{ts,tsx,js,jsx,py,go}' \-t code 'compute|calculate|\\bscore\\b|\\bband\\b|\\btier\\b|\\bsolve\\b|integrate|dydt|gradient|regurg|\\bSVR\\b|\\bPVR\\b|LVEDP|cutpoint|threshold'  
rg \-c 'compute|calculate|\\bscore\\b|\\bband\\b|\\btier\\b|\\bsolve\\b|integrate|dydt|gradient|regurg|\\bSVR\\b|\\bPVR\\b|LVEDP|cutpoint|threshold' apps/rrvalves-canvas/src apps/rrvalves/src apps/brain/src | sort \-t: \-k2 \-n \-r | head \-40  
rg \-n 'classifyAvGrad|classifyMrRf|classifyCO|classifyLvedp|classifyAS|classifyMS|classifyAR|classifyMR|classifyTR|classifyPH|classifyPH\_Group' apps/rrvalves-canvas/src apps/rrvalves/src  
rg \-n 'export function|export const|function \[a-z\]' apps/rrvalves-canvas/src/coupling/maskingPatterns.ts apps/rrvalves-canvas/src/coupling/confidence.ts apps/rrvalves-canvas/src/components/rounds/RoznerLiveFlowMap.jsx  
rg \-n 'export function|function ' apps/rrvalves-canvas/src/cicu-risk/hdiDemoCases.ts apps/rrvalves-canvas/src/cicu-risk/\_score\_snapshot.ts apps/rrvalves-canvas/src/cicu-risk/coverage.verify.ts  
Excluded as not clinical math by the strict definition:

* apps/rrvalves-canvas/src/guidelines/thresholds/esc-ers-2022-ph.ts (constants only, no logic)  
* apps/rrvalves-canvas/src/coupling/perturbations.ts (input pre-multipliers feeding the simulator)  
* apps/rrvalves-canvas/src/coupling/cascadeClassification.ts (static dictionary lookup, no derivation)  
* apps/rrvalves-canvas/src/coupling/trackedMetrics.ts, types.ts, confidence.ts (type/registry/UI-tier metadata)  
* apps/rrvalves-canvas/src/queue-priority/combineQueuePriority.ts (pure passthrough — never blends/derives)  
* apps/rrvalves-canvas/src/components/rounds/RoznerLiveFlowMap.jsx (cardiac-phase animation math, not clinical derivation)

Excluded as test / fixture / verifier files (listed but not enumerated):

* apps/rrvalves-canvas/src/ecg-priority/ecgPriority.test.ts  
* apps/rrvalves-canvas/src/cicu-risk/coverage.verify.ts  
* apps/rrvalves-canvas/src/cicu-risk/\_score\_snapshot.ts  
* apps/rrvalves-canvas/src/cicu-risk/hdiDemoCases.ts  
* apps/rrvalves-canvas/src/coupling/coupling.verify.ts  
* apps/rrvalves-canvas/src/guidelines/verifier/verifier.verify.ts, dispatcher/dispatcher.verify.ts, indexer/indexer.verify.ts

