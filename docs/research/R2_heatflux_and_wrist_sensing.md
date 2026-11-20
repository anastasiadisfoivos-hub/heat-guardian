# R2 — Heat-flux core-temperature estimation and wrist sensing for the Heat Guardian band

Research agent: SENSING. Feeds "Core Sense" (two TMP117 + insulation → core estimate) and the sensor model inside "Virtual Elders". Date: 12 Nov 2026.

Prior notes this extends (not repeated here): `/home/claude/research_notes/Heat Guardian band hardware/sensors.md` (TMP117, SHT4x, PPG parts, Coolbit wrist-air contamination, I2C map) and `algorithms.md` (ECTemp equations, Welles 2018, Eggenberger 2018, Kenzen, Coolbit, Meade 2024 older-adult signal sizes, Carrillo 2024, PPG RMSSD limits). Where a number is already sourced there I cite the note. Every new number below has a DOI/URL. "INFERENCE" marks my own calculation.

**One-paragraph verdict.** Dual-heat-flux (DHF) and zero-heat-flux (ZHF) methods cancel the *perpendicular* tissue resistance under the sensor, which is why they work on the forehead and chest (bias ≈0.0–0.2 °C, SD 0.2–0.35 °C vs oesophageal). They do not cancel the *longitudinal* gradient along the arm, which is set by skin blood flow and reaches several °C when the wrist is vasoconstricted. A wrist heat-flux "core" is therefore credible only as (a) an ambient-decoupled *insulated wrist temperature* plus (b) a perfusion-dependent offset that must be learned per person (published wrist results: MAE 0.30 °C with daily personal calibration, 0.34 °C free-living with ML; 0.40 °C RMSE vs 0.29 °C forehead for the same device). Worse for us: in hot rooms (31–36 °C) the skin-to-air flux goes to zero, so the ΔT across our insulation disc shrinks to 0.2–0.5 °C and carries almost no core information; what remains is insulated skin temperature + HR + air. Core Sense should therefore be framed as "insulated-skin + flux + HR + air fusion with a learned personal offset", never as a core thermometer. The simulator must generate the flux-collapse in heat, the vasoconstriction offset in cool rooms, the 20–30 min donning transient, sweat/loosening events, and PPG dropout.

---

## 1. Physics of zero-heat-flux and dual-heat-flux core estimation

### 1.1 Zero-heat-flux (Fox & Solman)

Fox & Solman (J Physiol 1971, 212:8–10; Clin Sci 1973, 44:81–86, doi 10.1042/cs0440081) put an insulating pad on the skin with a thermocouple pair across the pad and a heater on top, servo-controlled so the temperature difference across the pad is zero. With no heat flowing, the skin under the pad warms until it equals the deep tissue temperature below (an isotherm ~1–2 cm deep), and the top thermistor reads "core". It is the basis of the 3M/Solventum Bair Hugger (SpotOn) forehead sensor. Costs: an active heater (hundreds of mW, needs mains or a big battery), a thick probe, and a 15–20 min equilibration (Saurabh 2014, BIODEVICES, [PDF](https://www.scitepress.org/Papers/2014/48899/48899.pdf)). Not usable on a 250 mAh band; cited here as the accuracy ceiling.

Accuracy of ZHF vs invasive core (all adult, mostly perioperative):
- Meta-analysis, 16 studies, 952 patients, 314,137 pairs: pooled bias 0.03 °C, population LoA −0.93 to +0.98 °C (Conway et al. 2021, J Clin Monit Comput 35:39–49, doi 10.1007/s10877-020-00543-6).
- Rest at 35 °C/50 % RH vs oesophageal: bias 0.17 ± 0.19 °C; exercise −0.05 ± 0.18; recovery −0.01 ± 0.20 (Teunissen 2011, as tabulated in Hashimoto 2026 review, doi 10.3390/s26030972). ICU adults vs oesophageal: 0.19 ± 0.27 °C (Dahyot-Fizelier 2017, Crit Care Med, doi 10.1097/CCM.0000000000002317). Cardiac surgery vs pulmonary artery: −0.05 ± 0.26 °C (Mäkinen 2016, in the same review table).
- Accuracy degrades below 32 °C core and the method is sensitive to ambient and airflow (Hashimoto 2026 review, §2.2.4).

### 1.2 Single-heat-flux (Gunga "Double Sensor", greenTEG CORE/CALERA)

Replace the heater with a known insulator and two thermistors: T1 on the skin side, T2 on the outer side of a disc of thermal resistance R_ins (m²·K/W). Steady-state 1-D conduction gives the same flux through tissue and disc:

- q = (T1 − T2) / R_ins = (T_deep − T1) / R_tissue
- **T_deep = T1 + K·(T1 − T2), with K = R_tissue / R_ins**

Gunga's Double Sensor (forehead) uses exactly this with an empirically fitted constant K_s/K_g (Masè et al. 2022, Front Physiol 13:830059, doi 10.3389/fphys.2022.830059, methods description). R_tissue is unknown and varies with site, fat, and above all skin blood flow, so single-flux devices need per-person or per-site calibration against a reference (Hashimoto 2026 review).

Published accuracy (forehead unless stated), bias ± SD vs rectal/oesophageal/GI pill:
- Gunga 2008 (J Therm Biol 33:297–307, doi 10.1016/j.jtherbio.2008.03.004), 20 men, forehead: at 10 °C rest −0.08 ± 0.50, exercise 0.16 ± 0.45; at 25 °C rest 0.01 ± 0.37, exercise 0.08 ± 0.35; **at 40 °C rest −0.10 ± 0.34**, exercise 0.11 ± 0.42 (table in Hashimoto 2026).
- Double Sensor at −18.7 °C air: bias +2.16 °C, LoA −0.89 to +5.22 (vs +0.09, LoA −1.51..+1.69 at 23 °C) — vasoconstriction and the constant-K assumption break it in the cold (Masè 2022).
- greenTEG CORE (chest, under a strap) vs rectal, cycling: bias +0.23 ± 0.35 °C (LoA −0.38..+0.72) at 19 °C; −0.10 ± 0.38 (LoA −0.62..+0.59) at 30.7 °C; only 45–51 % of pairs within 0.3 °C; underestimates above 39.5 °C; manufacturer claim ±0.26 °C "not supported" (Verdel et al. 2021, Sensors 21:5932, doi 10.3390/s21175932).
- CORE during 8 h indoor heat at 40 °C/57 % RH, free-living-like, vs rectal: no fan −0.19 ± 0.27 °C (men), 0.06 ± 0.26 (women); **with a 3.2 m/s fan −0.34 ± 0.12 (men), −0.27 ± 0.10 (women)** — airflow alone shifts the estimate by ~0.15–0.3 °C (Xu, Xu, Wang, Lei, Wang 2025, Build Environ 282:113288, doi 10.1016/j.buildenv.2025.113288, as tabulated in Hashimoto 2026).
- CORE at rest, sleep lab 16–24 °C, young adults, vs GI pill: −0.06 ± 0.26 °C (Xu, Wu, Lian, Xu 2024, Energy Build 303:113827, doi 10.1016/j.enbuild.2023.113827).
- CORE in chronic heart-failure patients (54 y) at 28 °C: rest −0.14 ± 0.41, exercise 0.06 ± 0.20 (Kaltsatou 2024, in review table). ICU patients vs bladder: −0.38 ± 0.43 (Ehler 2025, in review table).
- CORE could not follow a −0.76 °C core drop induced by cold-water hyperhydration at rest (it showed −0.09 °C; ICC 0.12) (Goulet et al. 2026, Sensors, cited in the Verdel ResearchGate page).

### 1.3 Dual-heat-flux (Kitamura 2010, Huang, Tamura)

Two parallel heat paths through the probe with different insulation (resistances R1, R2), each with a top and bottom thermistor: T1 (skin, path 1), T2 (top, path 1), T3 (skin, path 2), T4 (top, path 2). Equating the flux in tissue and in each path and eliminating the unknown R_tissue:

- **T_deep = T1 + (T1 − T2)(T1 − T3) / [k·(T2 − T4) − (T1 − T3)]**, k = R1/R2 (Kitamura, Zhu, Chen, Nemoto 2010, Med Eng Phys 32:1–6, doi 10.1016/j.medengphy.2009.09.004; Saurabh 2014 notes a sign error in the original denominator).
- Huang's modified form with k = 2 for diffuse (non-vertical) heat entry: T_deep = T1 + (T1 − T2)(T1 − T3) / [k·(T2 − T4) − (T1 − T2)] (Tamura, Huang et al. 2022, Sensors 22:9985, doi 10.3390/s22249985). The same formula in Huang 2014 (BIODEVICES, [PDF](https://www.scitepress.org/Papers/2014/47900/47900.pdf)) with α = R1/R2.
- In heat-transfer-coefficient form (Żmigrodzki et al. 2024, Sensors 24:1887, doi 10.3390/s24061887): CBT = Tss + q/h_t; with two channels h_t = (q1 − q2)/(Tss1 − Tss2), so CBT = Tss1 + q1·(Tss1 − Tss2)/(q2 − q1).

What DHF buys: no per-person tissue calibration *for the perpendicular path*. What it costs: four matched thermistors, a probe ≥ 20–40 mm wide so the two paths see the same tissue, and a still-large transient.

Published DHF accuracy:
- Kitamura 2010, forehead, 17 subjects, vs ZHF reference: mean 37.08 vs 37.02 °C, r = 0.970 ([PubMed 19906554](https://www.pubmed.gov/19906554/)).
- Feng et al. 2017 (Physiol Meas 38:652–668, doi 10.1088/1361-6579/aa5f43): PDMS + CaCO₃ medium, LMS adaptive cancellation of ambient fluctuations; hot plate 37–41 °C error 0.08 ± 0.20 °C; 34 resting subjects vs sublingual 0.13 ± 0.22 °C; **initial settling time ~23.5 min**.
- Tokizawa 2021 chest patch (dual heat flux), walking at 30–40 °C vs oesophageal: RMSE 0.18–0.25 °C, bias 0.00 ± 0.19 to −0.10 ± 0.23 °C, 85 ± 18 % of pairs within 0.3 °C (Tokizawa, Shimuta, Tsuchimoto 2022, J Therm Biol 108:103294, doi 10.1016/j.jtherbio.2022.103294).
- Tamura 2022 forehead under a helmet at 39 °C vs ZHF: bias 0.07 °C, SD 0.33 °C; calibrated k changes with ambient (k_av 1.42 ± 0.01 standard probe, 0.98 ± 0.03 miniature) and "error increases as ambient temperature decreases".
- Huang 2014 FEM: lateral (transverse) heat loss from the probe periphery is the main geometric error; a probe of 22 mm radius and ≤ 8 mm height keeps error < 0.5 °C; a flatter, wider probe is better than a tall one.
- Żmigrodzki 2024 analytical model: all variants become unstable where ambient ≈ CBT (TT variants unstable from 33.8 to 42.3 °C ambient); temperature-sensor error is ~90 % of total uncertainty, so sensors better than 0.05 °C are required; raising convection h_sa from 6 to 104 W/m²K *lowers* uncertainty (bigger flux = more signal); optimal h_s2/h_s1 ratio ≈ 7 or more. Model parameters: skin k 0.37 W/mK, thickness 2.5 mm; PDMS 0.15 W/mK; natural convection 6.1 W/m²K.
- Settling: forehead stabilisation 20–30 min, step tracking < 5 min once settled (Saurabh 2014); ZHF 15–20 min.

### 1.4 What changes at the wrist

**The equation cancels the wrong resistance.** All the above assume 1-D conduction from a deep isotherm at core temperature directly beneath the probe. On the forehead/sternum that isotherm is the brain/thorax. On the wrist the "deep" tissue 5–10 mm down is tendon, bone and the radial/ulnar arteries, whose temperature is core minus an *axial* drop along the arm that depends on blood flow (Pennes perfusion term), not on conduction through the disc. DHF cannot see that drop.

Evidence for the size of the axial drop and its driver:
- Forearm-minus-fingertip skin gradient vs fingertip blood flow in 19 volunteers: gradient = 0.2 − 5.7·log(flow), r = 0.98 (regression as given on PubMed; coefficient signs from the abstract text); fingertip cooling half-time after arterial occlusion 6.6 ± 1.2 min (Rubinstein & Sessler 1990, Anesthesiology 73:541–545, [PubMed 2393139](https://www.ncbi.nlm.nih.gov/pubmed/2393139)). So the distal arm sits several °C below proximal skin when vasoconstricted, and changes with a ~7 min half-time.
- Wrist calorimetry at 21 °C room: skin thermal resistance under a 2×2 cm plate 24 ± 2 K/W volar, 33 ± 4 K/W dorsal (= 0.0096 and 0.013 m²K/W per unit area, INFERENCE), heat capacity 1.8–2.3 J/K; dorsal–volar difference attributed to local vasoconstriction (Rodríguez de Rivera et al. 2025, PLOS ONE 20:e0334062, doi 10.1371/journal.pone.0334062). Note this is ~1.4–2× the 0.0068 m²K/W (2.5 mm/0.37 W/mK) that the forehead models assume, and it is *state dependent*.
- Insulated (foam-covered) skin temperature at distal sites did worse than proximal (scapula) as a core predictor; the authors favour proximal, bony sites and state distal sites are "less representative of core" (Eggenberger et al. 2018, Front Physiol 9:1780, doi 10.3389/fphys.2018.01780). Their 2-input model: T_core = 0.0100·HR + 0.0837·T_ins,scapula + 33.17, SEE 0.29 °C, R² 0.68.
- Xu 2013 (Eur J Appl Physiol 113:2381–2389, doi 10.1007/s00421-013-2674-z): regressions of core on skin temperature + heat flux are **site-specific**, R² 0.30–0.88; sternum best; forehead fails under sweating; accuracy "depends largely on sensor placement" and on the clothing ensemble. No wrist data.
- Forearm skin at rest in 40 °C/15 % RH air: 36.0 °C surface, 35.3 intradermal; **with a fan the surface rises to 37.8 °C** (air hotter than skin, so convection heats the arm); water spray drops it to 30.6 °C (McKenna et al. 2025, Physiol Rep 13:e70643, doi 10.14814/phy2.70643). This is the flux-reversal regime our wearers live in.

Direct wrist heat-flux results (the only ones found):
- Tsadok-type wrist dual-sensor device: RMSE 0.40 °C at the wrist vs 0.29 °C at the forehead (Zhao et al. 2026 benchmark Table 3, cited in `algorithms.md`); the earlier Sensors review excluded the same group's single-distal-site result as an outlier at RMSE 1.97 °C (Dolson et al. 2022, Sensors 22:7639, doi 10.3390/s22197639).
- Shan, Hu, Zou, Zhang 2022 (IEEE JBHI 26:2158–2168, doi 10.1109/JBHI.2021.3124551): single-flux wrist and forehead models with a *dynamic tissue-perfusion term* and per-person parameters fitted from daily data: **wrist MAE 0.297 ± 0.078 °C, forehead 0.224 ± 0.071 °C**; the group (non-personal) wrist model was markedly worse. This is the strongest evidence that a wrist flux estimate can reach ~0.3 °C, and that it only does so with personal calibration and a perfusion term.
- greenTEG CALERA prototype wrist sensor (heat flux + skin T + HR, on-device ML, 1 estimate/min), 50 adults free-living 26 h after a COVID booster, vs GI pill: validation bias +0.11 °C, **LoA −0.67 to +0.93 °C, MAE 0.34 °C**, r = 0.72; fever > 38 °C FPR 14.9 %, FNR 23.6 %; "reliable measurement of CBT at the wrist remains challenging"; young participants only (Etienne et al. 2023, BioMed Eng OnLine 22:25, doi 10.1186/s12938-023-01081-3).
- Liang et al. 2025 (Physiol Meas 46(4), doi 10.1088/1361-6579/adbf64): wearable *dual temperature* (skin + environment) device, six ML models, 62 train / 10 test subjects: MAE 0.15 ± 0.04 °C, RMSE 0.17 ± 0.05 °C; site not stated in the abstract, extreme-environment (firefighter/military) framing. Treat as optimistic.
- Non-contact IR wrist vs forehead on 30 students: wrist 31–33 °C and "not a reliable reference for body temperature" (Mata-Romero et al. 2024, Sensors 24:1944, doi 10.3390/s24061944).

**Is a wrist heat-flux core estimate credible?** As an absolute thermometer: no (LoA ≈ ±0.8 °C free-living, dependence on perfusion state, no 65+ data). As a *feature*: yes, and better than bare skin temperature, for three reasons. (1) The insulated skin side T1 is decoupled from room air and drafts, which bare wrist skin is not (Janowicz & Wiczyński 2026 in `algorithms.md`). (2) In heat the wrist vasodilates, so the axial offset shrinks exactly when we care; Meade 2024 shows mean skin reaching 35–36 °C at 31–36 °C rooms with core 37.6–37.8 °C (`algorithms.md` §3), i.e. the core–wrist gap collapses to ~1.5–2.5 °C and T1 tracks it. (3) PPG perfusion index gives a live proxy for the perfusion state that sets K, so the NN can learn K(PI, T_air, T1 − T_air). Caveat: older adults raise skin blood flow 2–3× less than the young (`sensors.md` Q7), so the gap closes more slowly and less completely in exactly our users; no study has measured wrist flux in anyone over 62.

---

## 2. Practical design for the band (two TMP117 + insulation disc)

### 2.1 Geometry and materials

Stack (skin → out): 316L/aluminium skin disc 8–10 mm (`enclosure_safety_regulatory.md`) → TMP117-SKIN (chip down on a 0.5 mm thermal pad) → insulation disc → TMP117-REF (chip up against the pod lid via pad) → lid → air. Keep the disc at least as wide as the two boards and ring it with the same foam so heat leaves vertically (Huang 2014: lateral loss is the main geometric error; wide-and-flat beats tall).

Candidate insulators (k in W/m·K, measured values):
| Material | k | Source | 2 mm R (m²K/W) | 3 mm | 5 mm |
|---|---|---|---|---|---|
| EVA foam (the mouse-pad material Foivos already uses) | 0.0368 | Thermtest transient hot-wire, [page](https://thermtest.com/application/thermal-conductivity-of-eps-and-eva-foam) | 0.054 | 0.082 | 0.136 |
| Silicone foam, Rogers BISCO BF-1000 (192 kg/m³) | 0.048 (ASTM C518) | [Stockwell datasheet](https://www.stockwell.com/data-sheets/bf1000.pdf) | 0.042 | 0.063 | 0.104 |
| Solid PDMS (used in DHF probes) | 0.15 | Żmigrodzki 2024 | 0.013 | 0.020 | 0.033 |
| Rubber insulator in Huang's probe | 0.06 | Huang 2014 | — | — | — |

Recommendation: **3 mm EVA/closed-cell foam (R ≈ 0.08 m²K/W)**, or 3 mm silicone foam if compression set matters. Reasons: (a) k is 4× lower than PDMS, so ΔT across it is 4× larger for the same flux; (b) 3 mm keeps the pod thin (the Nov 12 one-pod note says the REF board "adds ~3 mm"); (c) 5 mm gives 60 % more ΔT but a longer transient and a thicker pod. Avoid open-cell foam (sweat wicking changes k). Keep the ratio R_ins/R_tissue ≈ 8 (0.08/0.01), which is in the ≥ 7 range Żmigrodzki finds optimal for sensitivity.

### 2.2 Expected signal size (INFERENCE, 1-D model; verify on the bench)

Series resistances per unit area: tissue 0.010 (wrist calorimetry), foam 0.082, PLA lid 1.5 mm/0.13 W/mK = 0.012, outer film 1/h with h ≈ 8–9 W/m²K (natural convection ≈ 4–6 + radiation ≈ 4.5) = 0.11–0.12. Total ≈ 0.22 m²K/W. Deep wrist tissue T_deep is core minus the axial offset.

| Scenario | T_air | T_deep (assumed) | q = ΔT/0.22 (W/m²) | T1 (skin side) | **ΔT across 3 mm EVA** | K·ΔT correction (K = 0.12) |
|---|---|---|---|---|---|---|
| Cool room, vasoconstricted | 20 | 34.0 | 64 | 33.4 | 5.2 °C | 0.6 |
| Comfortable, rest | 25 | 35.5 | 48 | 35.0 | 3.9 °C | 0.5 |
| Warm room (WHO day limit) | 31 | 36.2 | 24 | 36.0 | 1.9 °C | 0.2 |
| Hot room, core 37.8 | 36 | 37.0 | 4.5 | 37.0 | **0.37 °C** | 0.04 |
| Hot room + fan 3 m/s (h ≈ 20) | 36 | 37.0 | 7 | 36.9 | 0.6 °C | 0.07 |
| Fever/exertion at 25 °C | 25 | 37.2 | 55 | 36.7 | 4.5 °C | 0.5 |
| Sun on the pod lid (lid 50 °C) | — | 37.0 | −59 (reverse) | 37.6 | **−4.8 °C** | formula invalid |

Reading: ΔT is 2–5 °C indoors below 31 °C, comfortably above TMP117 noise (±1 LSB = 0.008 °C with 8× averaging, ±3 LSB = 0.023 °C without; [TI TMP117 datasheet](https://www.ti.com/lit/ds/symlink/tmp117.pdf)). It collapses to ~0.3–0.6 °C at 36 °C rooms, where a 0.05 °C offset mismatch between the two chips becomes a 10–15 % flux error. With K ≈ 0.12 the flux *correction* term is small at the wrist (0.04–0.6 °C), so T1 itself dominates — which is the point: the estimate is "insulated wrist temperature + a small flux term + a learned perfusion offset". The sun row shows why any T2 > T1 must gate the formula off.

### 2.3 Time constants (INFERENCE from R·C)

- Foam disc alone: C ≈ 192 kg/m³ × 1.2 kJ/kgK × 3 mm ≈ 0.7 kJ/m²K; τ ≈ R·C/2 ≈ 30 s.
- Each Adafruit board (~1 g FR4+Cu, ~1 J/K) through a 0.5 mm pad (~5 K/W): τ ≈ 5 s.
- Lid + REF side to ambient: ~3.6 J/K through ~120 K/W → **τ ≈ 7 min**. The REF sensor lags room changes by 5–10 min; the SHTC3 island (t63 < 5–30 s, [SHTC3 datasheet](https://sensirion.com/media/documents/643F9C8E/63A5A436/Datasheet_SHTC3.pdf)) leads it, so (T_air − T2) is a usable "room is changing" signal.
- Tissue under the pod warming to insulated steady state: 20–30 min on the forehead (Saurabh 2014, Feng 2017: 23.5 min); the distal arm perfusion response has a 6.6 min half-time (Rubinstein & Sessler). **Discard the first 20–30 min after donning; after a room change expect a 10–15 min transient; feed d(T1)/dt and d(T2)/dt to the model so it can tell a transient from a trend.**

### 2.4 Sensitivity to air movement and sun

- Airflow raises h_out, which *increases* flux and ΔT (good for signal, Żmigrodzki) but changes K's effective denominator if the model assumed still air; for the CORE sensor a 3.2 m/s fan at 40 °C shifted the estimate by −0.15 to −0.3 °C (Xu 2025). Pedestal fans are common in Greek homes without AC, so the simulator must include fan on/off as a step in h_out (≈ 8 → 20–25 W/m²K at 2–3 m/s, INFERENCE from forced-convection correlations). Hashimoto's group built probe covers specifically for airflow robustness (Hashimoto, Tada, Nishida 2024, Sens Actuators A 368:115136, doi 10.1016/j.sna.2024.115136; 2025 IEEE Access 13:69081, doi 10.1109/ACCESS.2025.3561285): a lightweight cover over the outer face reduces the h_out dependence — our pod lid already does part of this.
- Direct sun on the lid flips the sign of ΔT (table above). Garmin's own manual tells users to remove the watch for 20–30 min before trusting its temperature (`sensors.md` Q3). Gate: if T2 ≥ T1 − 0.1 °C or T_air,SHTC3 > T1, mark `flux_invalid`, fall back to T1-only, and treat it as an "outdoors/sun" context feature.

### 2.5 Sensor matching and one-time calibration (he has a multimeter and a kitchen thermometer, no calipers)

Three different constants are at stake; do not confuse them.

1. **Offset between the two TMP117s** (what actually limits the hot-room case). Each chip is ±0.1 °C absolute, so the pair can disagree by up to 0.2 °C. Put both boards together inside a closed insulated box (a mug with a lid, or wrapped in a sock inside a drawer, no water needed — the boards are not waterproof) for 15 min; log both; the mean difference is the offset, store it in flash; expect 0.02–0.08 °C; repeatability after that is ±1 LSB. Repeat at a second temperature (warm room vs fridge-door) to catch gain mismatch; TMP117 has no user trim register beyond its offset register, so apply in firmware.
2. **R_ins of the disc** (needed only if we want flux in W/m²; the NN can absorb it). Bench "hot plate": mug of 40–45 °C water with a thin metal lid (tin-can lid or aluminium foil on cardboard is *not* enough — use metal), kitchen probe in the water; put a 2–3 mm layer of a material with known k (a cut of the same EVA sheet is fine, or a silicone baking sheet, k ≈ 0.2 W/mK typical) on the lid as the "skin", pod skin-disc down on it, towel over everything, wait 20 min, then R_ins = R_skinlayer × (T1 − T2)/(T_water − T1). Thickness without calipers: stack 10 sheets against a ruler and divide. Expect ±20–30 % uncertainty; that is acceptable because K is re-learned on the person. Better: a known heat source — a 470 Ω resistor on 5 V (53 mW; measure V and R with the multimeter) glued to a 2 × 2 cm aluminium plate on foam, pod on top: q = P/A ≈ 130 W/m² if the back is well insulated, R_ins = (T1 − T2)/q.
3. **K for the person** (tissue + perfusion). After ≥ 30 min seated in a 22–26 °C room, read an oral digital thermometer (a kitchen thermometer is not accurate enough; a €5 clinical one is ±0.1 °C) and set K = (T_oral − T1)/(T1 − T2). This is a Body Twin parameter, re-estimated nightly; the simulator should draw K per virtual elder from a distribution (see §6).

### 2.6 Sampling and filtering

- TMP117 one-shot, 8× averaging (124 ms, 16 µC per read, `power.md`) **every 5 s**, both chips read back-to-back so they see the same instant. Median of the last 3, then a 60 s EMA; emit 1-min means and 1-min slopes. Kenzen samples temperature every 5 s and aggregates to 1 min (`algorithms.md` §7); nothing in the heat-strain time course is faster than minutes.
- Keep the raw 5 s series in a 10-min ring buffer so Guardian Loop can do contact checks on fast drops (§5).
- Never use continuous mode: 410 µW self-heating gives +0.04 °C (TMP117 datasheet) and it wastes 16 µA.

---

## 3. Models that fuse heat flux, HR and ambient — what exists and how well it does

(All results young/middle-aged adults unless stated; errors vs rectal/oesophageal/GI pill.)

| Model | Inputs | Site | Reported error | Source |
|---|---|---|---|---|
| ECTemp (1-state EKF) | HR | — | bias −0.03 ± 0.32 °C, LoA ±0.63, RMSE 0.30; independent re-implementations 0.41–0.66 RMSE | Buller 2013; Zhao 2026 (`algorithms.md` §1) |
| Looney 2018 resting sigmoid EKF | HR | — | bias 0.00 ± 0.28 °C (sleep, 18–22 °C) | `algorithms.md`; Hashimoto 2026 table |
| Welles 2018 linear KF | T_skin + heat flux + HR | chest/rib | RMSE 0.18 ± 0.04 °C; any two of the three inputs similar; wrist not tested | `algorithms.md` |
| Niedermann 2014 PCA + regression | 3 skin T + 2 heat fluxes + HR, at 10 and 30 °C | trunk | RMSD 0.28–0.34 °C | Int J Biometeorol 58:7–15, doi 10.1007/s00484-013-0687-2 ([abstract](https://doc.rero.ch/record/324882?ln=en)) |
| Eggenberger 2018 regression | HR + insulated scapula T (heat flux dropped: β ≈ 0.00–0.03, "many measurement artifacts") | scapula | SEE 0.29 °C, R² 0.68 | doi 10.3389/fphys.2018.01780 |
| Laxminarayan 2018 individualised KF | HR + activity (+ chest T_skin, which did not help) ; 6 personal parameters converge in 30–45 min | chest | RMSE 0.33 ± 0.18 °C (166 subjects, 247 profiles); 0.25 above 38.5 °C; noisy HR +16 % | J Appl Physiol 124:1387, doi 10.1152/japplphysiol.00837.2017 |
| Kenzen ML | HR + skin-side and ambient-side T/RH + anthropometrics, in firmware | upper arm | MAE 0.25, RMSE 0.30 °C | `algorithms.md` |
| Coolbit multimodal KF | wrist air T, wrist skin T, RH, HR | **wrist** | RMSE 0.13, MAE 0.10 °C (15 subjects, chamber) | `algorithms.md`; Dolson 2022 review |
| Shan 2022 personal perfusion model | single-flux T1/T2 + daily personal fit | **wrist** / forehead | MAE 0.30 / 0.22 °C | doi 10.1109/JBHI.2021.3124551 |
| CALERA wrist ML | heat flux + skin T + HR | **wrist**, free-living | MAE 0.34, LoA −0.67..+0.93 °C | doi 10.1186/s12938-023-01081-3 |
| Liang 2025 ML | skin T + environment T (dual sensor) | unstated | MAE 0.15, RMSE 0.17 °C (10 test subjects) | doi 10.1088/1361-6579/adbf64 |
| Strickland 2025 BiLSTM + conformal | HR, chest T_skin, ambient, work, clothing, demographics; 30-min windows | chest | RMSE 0.29 vs 0.34 ECTemp on 251 subjects / 140 k minutes; **conformal intervals hit 94.75 % coverage at the 90 % level vs 14.8 % for ECTemp's own variance** | Commun Eng 4:219, doi 10.1038/s44172-025-00548-6 |
| Zhao 2026 benchmark | 14 re-implemented models | various | HR-only EKF 0.41–0.66 RMSE out of sample; skin gains "highly dependent on site" | `algorithms.md` |

What to take from this for Core Sense:
- The honest floor for any sensor-fusion core estimate on strangers is ≈ 0.25–0.35 °C RMSE; the 0.13–0.17 °C results come from single small chamber studies. Our sealed-exam target of ~0.25 °C on HTT (young, walking) is consistent with the field; quote it as such.
- Heat flux as a *raw* input is fragile (Eggenberger dropped it for artefacts; Verdel/Xu show device-level drift with airflow). Use it through the derived quantities T1 (insulated skin), ΔT, and d/dt, with a validity flag, not as "W/m²".
- Personalisation is where the wrist gains the most (Shan: group model poor → personal 0.30 °C; Laxminarayan: 6 parameters converge in 30–45 min). This argues for Body Twin learning K, resting HR and the HR–core slope, and for the ensemble to be seeded from a population prior.
- Uncertainty: conformal/ensemble intervals are the published way to say "we don't know"; Strickland shows Kalman variances are badly under-dispersed. The "when the models disagree, warn earlier" plan in the brief is in line with this.
- No published fusion model has any 65+ validation; Carrillo 2024 (39 adults 61–78, 9 h at 40 °C) found HR and HRV discriminate a > 1 °C core rise with AUC ≤ 0.65 (doi 10.1139/apnm-2024-0191). Core Sense must lean on the thermal channels for this group.

---

## 4. Wrist PPG heart rate in older adults at rest

### 4.1 MAX30102 at the wrist

Red (660 nm) + IR (880 nm) only, no green; 15–18-bit ADC, 50–3200 sps, LED 0–51 mA in 0.2 mA steps, 32-sample FIFO, ambient cancellation up to 200 µA, no proximity interrupt in revision 1, die temperature ±1 °C ([MAX30102 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX30102.pdf)). The datasheet's own ambient-light test is "with a finger on the sensor". Green has a ~10 dB better signal-to-motion ratio than IR at the wrist and IR is the motion-sensitive channel (Zhang 2019, `sensors.md` Q1). Expect usable red/IR wrist HR only when still and snug; treat IR as a motion/contact reference.

### 4.2 Signal quality indices (what commercial bands compute before trusting a beat)

From the largest wrist dataset (Aurora-BP, 1,142 adults of "varying ages and health statuses"; Charlton et al. 2025, PLOS Digit Health 4:e0000585, doi 10.1371/journal.pdig.0000585):
- **SNR**: spectral power at the cardiac frequency and its harmonics over the rest, after high-pass filtering below the minimum plausible HR. Wrist SNR 18.6 dB supine, 13.7 dB sitting with the arm in the lap, 9.0 dB standing with the arm hanging; sitting with the sensor at heart height 15.5 dB vs 10.5 dB alongside the body.
- **Perfusion index PI = 100 × AC/DC** (median pulse amplitude over median baseline). Rises with contact pressure at the wrist; is the gold-standard quality number in clinical oximeters (Elgendi 2016).
- **Template-matching correlation TMCC**: correlation of each pulse with the mean pulse template; ≥ ~0.8–0.9 is a usual "good beat" threshold in the literature.
- SNR and TMCC *increase* with age (less HRV, simpler waveform), PI does not; darker skin lowers SNR unless LED drive is raised. So older wrists give *more regular* pulses but not stronger ones; adaptive LED current is mandatory.
- Elgendi 2016 (Bioengineering 3:21, doi 10.3390/bioengineering3040021) compared eight SQIs; **skewness** of the PPG segment best separated excellent/acceptable/unfit 60 s windows (F1 86–87 %), with perfusion, kurtosis, entropy and zero-crossing as runners-up. Cheap enough for the nRF52840.

Practical confidence rule for the band (INFERENCE combining the above): `hr_conf = f(PI ≥ 0.3 %, SNR ≥ 10 dB, TMCC ≥ 0.8, skewness in band, IMU RMS < 0.05 g over the window)`; report HR only with conf ≥ 2 of 3 quality flags, and keep a "no reading" state rather than a bad number.

### 4.3 Accuracy to expect

- Consumer wrist optical HR across devices: MAE 9.5 bpm at rest pooled over 6 devices, +30 % during activity (Bent 2020, `algorithms.md` §7). Apple Watch living meta-analysis (82 studies): bias −0.27 bpm, LoA −7.2 to +6.6 bpm (living systematic review, npj Digit Med 2026, doi 10.1038/s41746-025-02238-1; pooled mean age 41 y) — i.e. σ ≈ 3.5 bpm per reading when the sensor is a good green-LED design.
- **Older adults (18, aged 69 ± 3)**, six trackers vs ECG strap during walking, household tasks and sitting: mean error −3.6 to +4.2 bpm, but **single readings underestimated by up to 30 bpm**, no dominant-arm effect (Tedesco et al. 2019, PLOS ONE 14:e0216891, doi 10.1371/journal.pone.0216891).
- Withings Pulse HR (wrist) vs chest ECG: r ≥ 0.82 at rest falling to ≤ 0.33 on a treadmill, bias up to 11.7 bpm, MAPE 3–4 % at rest (Mendt et al. 2025, Front Physiol 16:1491401, doi 10.3389/fphys.2025.1491401; young subjects).
- Fitbit in the Coolbit chamber: 83 % of readings within ±5 bpm (`sensors.md`).

Working numbers: at rest with good contact, σ ≈ 3 bpm on 1-min means with a 5–15 % rate of outlier minutes; red/IR-only hobby module: assume double the dropout. The physiological signal we need is +9–14 bpm over hours (Meade 2024), so 5-min medians are required and sufficient.

### 4.4 Resting HR and HRV norms by age

- Real-world PPG HR (66,788 people, 3.1 M readings): mean 79.1 ± 14.5 bpm overall; 95th percentile ≤ 95 bpm above age 60; HR falls with age and rises with number of conditions and BMI (Avram et al. 2019, npj Digit Med 2:58, doi 10.1038/s41746-019-0134-9).
- Healthy older adults at 22 °C seated: 60 ± 7 bpm, RMSSD 14.4 ± 4.1 ms, rising to 74 bpm / 9.3 ms at 36 °C (Meade 2024, `algorithms.md` §3).
- 10-s ECG RMSSD reference values, Lifelines (healthy, no beta-blockers): 65–69 y median 17.8 ms women / 17.7 men (2nd–98th pct 5.0–83 / 4.9–110); 70–74 y 18.3 / 16.0; 75+ 16.1 / 14.9 ms; mean IBI 889 ms (women) and 946 ms (men) at 65–69 (Tegegne et al. 2020, Eur J Prev Cardiol 27:2191, doi 10.1177/2047487319872567). The lower normal limit (~5 ms) is "remarkably stable", the upper tail widens after 60 (ectopy, arrhythmia).

### 4.5 HRV (RMSSD) as a strain/dehydration marker — evidence quality

- Mild dehydration (0.55–0.59 % body-mass loss over 4 h at 30 °C without water) lowered RMSSD and SDNN and raised HR by ~5.8 bpm in young adults; within-subject effect size for RMSSD ηp² = 0.36, between-subject 0.08 (Young & Benton 2019, Sci Rep 9:16412, doi 10.1038/s41598-019-52775-5). Small, young, and confounded by heat itself.
- In older adults during 9 h at 40 °C, RMSSD correlated with core rise but ROC AUC ≤ 0.65 for > 1 °C rise; "marked heterogeneity" (Carrillo 2024).
- Wrist PPG RMSSD vs ECG: LoA −43 % to +118 % even at rest (Casanova-Lizón 2026, `algorithms.md` §7).
- Verdict: RMSSD is a **weak, low-grade feature** (evidence: small young samples, poor discrimination in 65+, PPG measurement error of the same order as the effect). Compute it only in still windows (IMU-gated, ≥ 2 min, TMCC-filtered), use the personal night-time baseline, and give it low weight in Core Sense/Guardian Loop; never alarm on HRV alone.

---

## 5. Contact / loose-band / not-worn detection

Published and patented approaches:
- **PPG DC level and variance (Apple, US 2016/0341600 → US9766370B2)**: LED-on minus LED-off samples; features are VAR(on−off), VAR(on) − VAR(off), the DC level and the DC/LED-intensity ratio checked against a "human skin" range, saturation, and a proximity rule (a > 25 % drop in signal sustained ~5 s = removal); a counter of low-variance samples declares off-wrist; binary on/off flag with hysteresis ([patent](https://patents.google.com/patent/US20160341600A1/en)).
- **Skin temperature threshold and rate**: on-body if T_skin ≥ 32 °C (refined Böttcher pipeline) vs Böttcher's 25–40 °C valid range; Pagnamenta 2022 flags non-wear when temperature changes > 3 °C within 5-min windows; Vert 2022 uses the rate of change of near-body temperature to find non-wear bouts as short as 5 min; Böttcher 2022 combines accelerometer SD (≥ 0.2 g over 10 s), skin temperature and EDA (≥ 0.05 µS) into a 1-min on-body score, OR-combined (all summarised in Van Der Donckt et al. 2024, arXiv 2401.13518).
- **Accelerometer only**: SD-based algorithms detect non-wear bouts ≥ 30 min (Ahmadi 2020, same review).
- Loss-of-pulse on a consumer watch (Google Pixel, Nature 2025, doi 10.1038/s41586-025-08810-9) combines multi-wavelength PPG pulselessness with accelerometer and an off-wrist check before escalating; the page was not retrievable here, cite for the architecture only.

What our band has that these lack: a **second temperature sensor across a known resistance**. The loose-band physics (INFERENCE, same 1-D model as §2.2): a 0.5–1 mm air gap between skin and the disc adds R_gap = t/0.026 ≈ 0.02–0.04 m²K/W, comparable to the foam; at 25 °C room this drops T1 by ~1–2 °C within a minute and shrinks ΔT proportionally, while T_air and T2 barely move; a removed band drives T1 toward T2 within ~2–5 min (board τ 5 s, but the skin disc and pod cool slowly) and ΔT toward 0. Recommended three-state logic (`worn` / `loose` / `off`), evaluated every minute on the 5 s buffer:

| Signal | worn | loose | off |
|---|---|---|---|
| T1 (skin side) | ≥ 31 °C indoors, slope within ±0.1 °C/min | sudden −0.5 to −2 °C step (< 2 min) not matched by T_air, or T1 persistently < T_air + 3 °C with ΔT small | T1 → T2 → T_air within ±1 °C; ΔT < 0.1 °C with T_air < 30 °C |
| ΔT = T1 − T2 | consistent with T1 − T_air (ratio ~0.3–0.45 at rest indoors) | ratio drops by > 30 % | ≈ 0 |
| PPG | PI ≥ 0.3 %, TMCC ≥ 0.8, DC in skin band | PI falls, DC rises (ambient leak) or saturates, TMCC < 0.6 | DC at off-skin level or saturated, no pulse |
| IMU | normal | slip events (short rotation about the forearm axis) | flat orientation, no motion ≥ 30 min, or charging |
| SHTC3 RH | — | — | RH drops to room level if the island had been sweat-loaded |

Two caveats. In a 36 °C room T1 ≈ T2 ≈ T_air even when worn (§2.2), so thermal off-detection fails exactly in heat; rely on PPG + IMU there and say so in the self-check. And "off and charging" is trivially detected from the charger pin — use it.

---

## 6. Sensor noise model for Virtual Elders (what the band would see)

Notation: y = truth + bias_unit + bias_wear(t) + drift(t) + noise. Per-unit biases are drawn once per virtual band; wearing effects are drawn per episode. All values are to be labelled SIMULATION in the simulator docs.

### 6.1 TMP117 skin (T1) and reference (T2)
- Per-unit absolute offset: U(−0.1, +0.1) °C each (datasheet max; typical |offset| ≈ 0.03–0.05). After the §2.5 box-matching, residual *difference* offset N(0, 0.02) °C.
- Quantisation 0.0078 °C; white noise per 8-avg read σ ≈ 0.008 °C (±1 LSB); without averaging ±3 LSB (0.023 °C).
- Self-heating: +0.04 °C if left in continuous mode, 0 in one-shot. Long-term drift ±0.03 °C over the device life (1000 h at 150 °C accelerated). Sample every 5 s.
- Installed coupling error (board between skin and chip, `sensors.md` Q2): skin-side reading sits below true insulated-skin temperature by U(0.1, 0.5) °C at 25 °C, scaling with flux (≈ 0.004–0.01 °C per W/m²); model it as an extra resistance R_mount ~ U(0.002, 0.008) m²K/W in series with the tissue.
- Physical model to generate T1, T2 (steady state + first-order lags): q = (T_deep − T_air_local)/(R_tissue + R_mount + R_ins + R_lid + 1/h_out); T1 = T_deep − q(R_tissue + R_mount); T2 = T1 − q·R_ins; lag T1 with τ = 3–5 min toward steady state (tissue), T2 with τ = 5–10 min (lid). T_deep = T_core − Δ_axial, with **Δ_axial = a + b·(T_core − T_air)·(1 − s)** where s ∈ [0,1] is the skin-blood-flow state from the two-node model (0 = vasoconstricted, 1 = fully dilated); a ~ U(0.3, 0.8) °C, b ~ U(0.08, 0.2) per °C (INFERENCE calibrated so that Δ_axial ≈ 2–3 °C at 20 °C vasoconstricted and 0.5–1 °C at 36 °C dilated, consistent with Rubinstein & Sessler gradients and Meade's 35–36 °C mean skin at 36 °C). R_tissue ~ U(0.008, 0.014) m²K/W (volar/dorsal wrist calorimetry), reduced ×0.7 when s > 0.7. h_out = 8 W/m²K still air; 20–25 with a fan; 12 while walking; the simulator should switch fans on in 30–50 % of hot-afternoon hours.
- Sun episode (outdoors, errands): T_lid up to 45–60 °C for the exposed minutes → T2 > T1, ΔT negative; flag probability of occurrence from the routine model.
- Sweat under the pod: occluded skin sweats without evaporating → R_mount falls by half (better contact) but after loosening/removal a flash evaporative drop of 1–3 °C in T1 for 2–5 min (surface vs intradermal with water: −1.3 °C, McKenna 2025; spray: 30.6 vs 36.0 °C).
- Loose band: with probability ~0.1 per hour in older wearers with swollen wrists (wrists swell in heat, PRODUCT_BRIEF), add R_gap ~ U(0.01, 0.04) m²K/W for 10–120 min; band slip also produces a short IMU rotation.
- Donning transient: 20–30 min exponential approach from room temperature.

### 6.2 SHTC3 air T / RH on the strap island
- Datasheet: T typ ±0.2 °C, RH typ ±2 %RH (20–80 %), repeatability 0.1 °C / 0.1 %RH, hysteresis 1 %RH, drift < 0.02 °C/yr and < 0.25 %RH/yr, RH t63 8 s at 1 m/s, T t63 5–30 s depending on mounting; 0.3 µA sleep, 270–430 µA for 0.7–10.8 ms per read ([SHTC3 datasheet](https://sensirion.com/media/documents/643F9C8E/63A5A436/Datasheet_SHTC3.pdf)).
- Per-unit offset U(−0.3, +0.3) °C, U(−2, +2) %RH; per-read noise σ 0.05 °C, 0.2 %RH; sample every 10 s.
- Body-heat contamination: Coolbit saw 26–34 °C "wrist air" in a 27–29 °C chamber (`sensors.md` Q3). Our island on the strap is better placed than a logger on the watch face, so model T_air,meas = T_air + c·(T1 − T_air) with c ~ U(0.05, 0.3) per band (fit c per band on the bench), plus +0.5–2 °C when the arm is under a blanket or sleeve (night, probability from the routine), plus sun episodes (+3–10 °C).
- RH: under-strap sweat saturation events (Coolbit): RH → 90–100 % for 10–60 min with probability rising with sweat rate; after loosening it recovers in minutes. True indoor RH in Athens summer homes 30–60 %.
- Slow-air situations (still rooms) make the island read the strap's own temperature; add a lag τ = 1–2 min relative to true air.

### 6.3 MAX30102 heart rate (what the HR algorithm outputs per minute)
- Good-contact, still: HR_meas = HR_true + N(0, 3 bpm) on 1-min means (Apple LoA ±7 per reading → σ ≈ 3.5; older adults mean error within ±4 bpm, Tedesco 2019).
- Outlier minutes: with probability p_out = 0.08 at rest (green-LED-class device) or 0.2 (red/IR hobby module, INFERENCE from the forum evidence in `sensors.md`), replace with HR_true + U(−30, +15) bpm (Tedesco: up to −30 bpm) or with "no reading".
- Motion: when IMU RMS > 0.05 g over the minute, σ × 1.3 (Bent +30 %) and p_out × 3; walking: σ ≈ 8–12 bpm (Mendt: bias up to 11.7 bpm, r ≤ 0.33).
- Perfusion coupling (the useful part): PI ≈ PI0 × g(s) with PI0 ~ U(0.2, 1.5) % per person and g rising ×2–4 from vasoconstricted to dilated (qualitative, from the physiology in Charlton 2025 "external temperature affects blood volume"); dehydration and cold lower PI; PI below ~0.2 % raises p_out. Generate PI as a band signal so Core Sense can use it as the perfusion covariate.
- Signal-quality outputs per minute: SNR (dB) ~ N(14, 3) sitting, N(18, 3) lying, N(9, 3) arm hanging/standing (Charlton 2025); TMCC ~ Beta centred 0.9 still, 0.6 moving. HR confidence = rule in §4.2.
- HRV: RMSSD_meas = RMSSD_true × LogNormal(0, 0.35) in still windows only (LoA −43..+118 %), undefined otherwise. RMSSD_true baseline per elder from the Lifelines age bins (median ≈ 17 ms at 65–74, 15 ms at 75+, 2nd–98th pct 5–100 ms), falling ~0.8 ms per °C ambient (Meade 2024), and by a further 10–20 % with mild dehydration (Young 2019; low-confidence effect).
- Beta-blocker elders (56 % of Meade's cohort on prescriptions; `algorithms.md` §8): HR rise with heat ×0.4–0.6 and RMSSD higher-than-age-norm; keep as a medication flag in the elder profile.

### 6.4 ICM-20649 motion
- Accelerometer: ranges ±4–30 g, noise density 285 µg/√Hz → RMS ≈ 1.4 mg at 25 Hz bandwidth (INFERENCE: 285e-6·√25), initial zero-g offset ±65 mg per axis (per-unit, fixed), offset drift ±0.8 mg/°C (so ±8 mg over a 10 °C day, correlated with T2), cross-axis ±2 %, nonlinearity ±0.5 %; gyro ZRO ±5 dps initial, ±0.05 dps/°C, 0.0175 dps/√Hz; accel-only low-power 68.9 µA at 102 Hz, 6-axis 3.2 mA; WOM threshold in 32 mg steps ([ICM-20649 datasheet](https://cdn.sparkfun.com/assets/7/e/5/f/1/ICM-20649_datasheet.pdf)).
- Wearing effects: gravity vector set by forearm orientation (drawn from the routine: lying, sitting with arm in lap, walking swing); physiological tremor 8–12 Hz at 1–5 mg RMS, essential tremor in a subset (4–8 Hz, 10–50 mg); band slip = brief ±20–40° rotation about the forearm axis; "no motion ≥ 30 min while T1 says worn" = nap/stillness event for the anomaly detector; "no motion + T1 falling to room" = taken off.
- Use 25–50 Hz accel-only for the simulator stream; gyro only in event windows (drinking gestures, `algorithms.md` §4).

### 6.5 Cross-signal consistency the simulator must preserve (so the NN cannot cheat)
- T1 − T_air,meas, ΔT and PI must all come from the same skin-blood-flow state s and the same h_out; a fan episode lowers T1 slightly, raises ΔT, and (via the island) lowers the apparent body-heat contamination at once.
- A loose band changes T1, ΔT, PI and IMU together, never one alone.
- At T_air ≥ 34 °C, ΔT must be ≤ 0.6 °C for every elder; any model that "sees" core through ΔT in that regime is learning an artefact.

---

## 7. Open risks and gaps

1. **No wrist heat-flux data in anyone over 62.** Every number above is young/middle-aged. The 65+ vasodilation deficit (2–3× smaller skin-blood-flow rise) means the axial offset closes less in heat than our young-adult-calibrated prior assumes; Body Twin must learn it, and the sealed exam cannot test it.
2. **Hot-room flux collapse** is physics, not a tuning problem: ΔT ≈ 0.3–0.6 °C at 34–36 °C rooms. Core Sense must be designed and reported as "insulated skin + HR + air" in that regime, with the heat-flux term contributing only below ~31 °C.
3. **K and R_ins uncertainty**: the no-calipers bench method gives ±20–30 % on R_ins; acceptable only because K is learned. Add a 470 Ω-resistor known-flux test if a cleaner number is needed.
4. **PPG**: the MAX30102 (red/IR) at the wrist is a known weak point (`sensors.md`); the noise model above assumes a 20 % outlier rate at rest for it. Measure it on Foivos and two older relatives before trusting any HR-dependent alarm.
5. **Two unread sources**: Nature 2025 loss-of-pulse paper (fetch blocked) and Huang 2015 J Therm Biol structural analysis (no abstract available); neither changes the conclusions.
6. **Startup/ambient instability** in the DHF literature (Żmigrodzki: unstable around T_air ≈ CBT; Tamura: k depends on ambient) means a fixed-K formula will produce wild values in exactly our conditions. Always clamp: `core_est ∈ [T1, T1 + 2.5 °C]` and `flux_valid = (T1 − T2 > 0.15 °C) ∧ (T_air < T1 − 0.5 °C)`.

---

## References (new in this note; DOIs as given above)

Avram 2019 npj Digit Med 10.1038/s41746-019-0134-9 · Charlton 2025 PLOS Digit Health 10.1371/journal.pdig.0000585 · Conway 2021 J Clin Monit Comput 10.1007/s10877-020-00543-6 · Dolson 2022 Sensors 10.3390/s22197639 · Elgendi 2016 Bioengineering 10.3390/bioengineering3040021 · Eggenberger 2018 Front Physiol 10.3389/fphys.2018.01780 · Etienne 2023 BioMed Eng OnLine 10.1186/s12938-023-01081-3 · Feng 2017 Physiol Meas 10.1088/1361-6579/aa5f43 · Fox & Solman 1971 J Physiol 212:8–10; 1973 Clin Sci 10.1042/cs0440081 · Gunga 2008 J Therm Biol 10.1016/j.jtherbio.2008.03.004 · Hashimoto 2026 Sensors review 10.3390/s26030972 · Hashimoto 2024 Sens Actuators A 10.1016/j.sna.2024.115136 · Huang 2014 BIODEVICES (scitepress 47900) · Kitamura 2010 Med Eng Phys 10.1016/j.medengphy.2009.09.004 · Laxminarayan 2018 J Appl Physiol 10.1152/japplphysiol.00837.2017 · Liang 2025 Physiol Meas 10.1088/1361-6579/adbf64 · Masè 2022 Front Physiol 10.3389/fphys.2022.830059 · Mata-Romero 2024 Sensors 10.3390/s24061944 · McKenna 2025 Physiol Rep 10.14814/phy2.70643 · Mendt 2025 Front Physiol 10.3389/fphys.2025.1491401 · Niedermann 2014 Int J Biometeorol 10.1007/s00484-013-0687-2 · Rodríguez de Rivera 2025 PLOS ONE 10.1371/journal.pone.0334062 · Rubinstein & Sessler 1990 Anesthesiology 73:541 · Saurabh 2014 BIODEVICES (scitepress 48899) · Shan 2022 IEEE JBHI 10.1109/JBHI.2021.3124551 · Strickland 2025 Commun Eng 10.1038/s44172-025-00548-6 · Tamura 2022 Sensors 10.3390/s22249985 · Tedesco 2019 PLOS ONE 10.1371/journal.pone.0216891 · Tegegne 2020 Eur J Prev Cardiol 10.1177/2047487319872567 · Tokizawa 2022 J Therm Biol 10.1016/j.jtherbio.2022.103294 · Van Der Donckt 2024 arXiv 2401.13518 · Verdel 2021 Sensors 10.3390/s21175932 · Xu 2013 Eur J Appl Physiol 10.1007/s00421-013-2674-z · Xu 2024 Energy Build 10.1016/j.enbuild.2023.113827 · Xu 2025 Build Environ 10.1016/j.buildenv.2025.113288 · Young & Benton 2019 Sci Rep 10.1038/s41598-019-52775-5 · Żmigrodzki 2024 Sensors 10.3390/s24061887 · Apple US20160341600A1 · Apple Watch living meta-analysis 2026 npj Digit Med 10.1038/s41746-025-02238-1 · Datasheets: TI TMP117 SNOSD82D; Sensirion SHTC3; ADI MAX30102; TDK ICM-20649 DS-000192; Rogers BISCO BF-1000; Thermtest EVA/EPS.
