# R1 — Ageing thermophysiology: parameter handbook for the Virtual Elders simulator

**Scope.** Everything a builder needs to stand up a two-node (core + skin) thermoregulation model of people aged 65–85, with age-dependent sweating, skin blood flow, thermal mass, cardiovascular response and medication effects. Every number has a source. Simulation outputs produced here are labelled **SIM**.

**Status of this file.** It *extends*, and does not repeat, two existing documents:
- `/home/claude/hgmodel/MEDICAL_CALIBRATION.md` — the clinical/occupational thresholds and the PSU-HEAT-derived environmental priors already used by the band. Its evidence rows are cited below as **[MC E1]…[MC E22]**. Where a number is already sourced there, this file cites it rather than re-deriving it.
- `/home/claude/research_notes/Heat Guardian band hardware/algorithms.md` §3, §6 — the Ottawa HEAT-lab resting-heat numbers and the indoor threshold work. Cited below as **[ALG §3]**, **[ALG §6]**.
- Contradictions flagged in `/home/claude/hgmodel/REPORT.md` §7 (JOS-3 vs PSU in humid heat) are carried forward and quantified in §8.

**What is new here:** the full two-node parameter set with an *older-adult* variant from a peer-reviewed model (Ji 2022); explicit age multipliers; the PSU HEAT **Rest** condition for older adults recomputed from the raw trial data in the project's own database; measured maximum skin wettedness for 65+ (0.31–0.47, not 0.85); the heart-rate-drift-precedes-core-rise finding; a working metabolic-unit convention; and a calibration run that matches Meade 2024 to within 0.07 °C.

---

## 1. Baseline two-node model

### 1.1 Structure and equations (Gagge 1971 / ASHRAE 55 form)

Two concentric compartments; the skin node holds a mass fraction `α` of body mass, the core holds `1 − α`.

```
hf_cs = (T_core − T_skin) · (5.28 + 1.163 · m_bl)          [W/m², core→skin]
S_core = M − hf_cs − E_res − C_res − W
S_skin = hf_cs − Q_sensible − E_skin
dT_skin/dt = S_skin · A_D / (0.97 · α · mass · 60)          [°C/min]
dT_core/dt = S_core · A_D / (0.97 · (1−α) · mass · 60)
E_res = 0.0023 · M · (44 − P_a)      C_res = 0.0014 · M · (34 − T_db)
α = 0.0417737 + 0.7451833 / (m_bl + 0.585417)
```

Source: Gagge, Stolwijk & Nishi (1971) two-node model as implemented in ASHRAE 55 and in `pythermalcomfort.models.two_nodes_gagge` (v3, verified by reading the source at `/usr/local/lib/python3.13/site-packages/pythermalcomfort/models/two_nodes_gagge.py`). ISO 7933 PHS is **not** cited for any number here: the standard is paywalled and was not opened — the same rule as [MC E22].

### 1.2 Body heat capacities

| Quantity | Value | Note / source |
|---|---|---|
| Whole-body specific heat | 0.97 Wh/(kg·°C) = **3.49 kJ/(kg·°C)** | Gagge two-node constant (code constant `0.97`) |
| 60 kg body | 58.2 Wh/°C = **210 kJ/°C** | computed |
| 70 kg body | 67.9 Wh/°C = **244 kJ/°C** | computed |
| 80 kg body | 77.6 Wh/°C = **279 kJ/°C** | computed |
| Skin-node capacity at α = 0.10, 72 kg | 7.0 Wh/°C = 25 kJ/°C | computed |
| Core-node capacity at α = 0.10, 72 kg | 62.9 Wh/°C = 226 kJ/°C | computed |
| α range (vasoconstricted → neutral → vasodilated) | **0.73 → 0.15 → 0.05** | from the α(m_bl) equation at m_bl = 0.5 / 6.3 / 90 |

Implication for the simulator: the skin node's time constant is 3–10 min, the core's is 1–3 h. A 1-minute integration step is ample; a 10-s step is wasted.

### 1.3 Core–skin conductance

| m_bl [L/(h·m²)] | α | K_core-skin = 5.28 + 1.163·m_bl [W/(m²·°C)] |
|---|---|---|
| 0.50 (young minimum) | 0.728 | 5.9 |
| 0.75 (**older minimum**, Ji 2022) | 0.600 | 6.2 |
| 6.3 (neutral, both) | 0.150 | 12.6 |
| 20 | 0.078 | 28.5 |
| 40 | 0.060 | 51.8 |
| 63 (**older maximum**, Ji 2022) | 0.053 | 78.5 |
| 90 (young maximum, ASHRAE default) | 0.050 | 110.0 |

So the usable conductance range is **5.9 → 110 W/(m²·°C) in young adults and 6.2 → 78.5 W/(m²·°C) in 65+** — a 0.71× ceiling.

### 1.4 Control gains and thresholds — young vs older side by side

| Parameter | Young (Gagge/ASHRAE 55) | Older (Ji et al. 2022) | Older/young |
|---|---|---|---|
| Sweating gain `c_sw` | 170 | 170 | 1.00 |
| Sweat attenuation `c_swe` | — | 1.0 (applied via thresholds, not gain) | — |
| Vasodilation gain `c_dil` | 120 (ASHRAE text says 50) | 50, × attenuation `c_de` = 0.6 → **effective 30** | 0.25 vs 120 |
| Vasoconstriction gain `c_str` | 0.5 | 0.75 × `c_ce` = 0.5 → effective 0.375 | 0.75 |
| Neutral skin blood flow | 6.3 L/(h·m²) | 6.3 L/(h·m²) | 1.00 |
| Min skin blood flow | 0.5 | **0.75** | 1.50 |
| Max skin blood flow | 90 | **63** | **0.70** |
| Vasodilation threshold | T_skin > 33.7 °C or T_core > 36.8 °C (neutral set-points) | **T_core > 37.3 °C** | **+0.5 °C** |
| Vasoconstriction threshold | T_skin < 33.7 °C | **T_skin < 33.25 °C** | −0.45 °C |
| Core sweating threshold | T_core > 36.8 °C | **T_core > 37.0 °C** | **+0.2 °C** |
| Skin sweating threshold | T_skin > 33.7 °C | **T_skin > 34.3 °C** | **+0.6 °C** |
| Shivering threshold | T_core < 36.8 °C | T_core < 36.7 °C | −0.1 °C |
| Shivering gain | 19.4·colds·c_cold | 19.4·ΔT_sk·ΔT_cr + 50·ΔT_cr + 0.5·ΔT_sk | — |
| Max regulatory sweat E | 500 W/m² (ASHRAE) | 400 W/m², ×1.25 if acclimatised; ×0.9 efficiency | 0.80 |
| Max skin wettedness `w_max` | 0.85 unacclimatised / 1.0 acclimatised | 0.85 / 1.0 in the model — but **measured 0.31–0.47** (§3.2) | **0.36–0.55** |
| Sweat evaporation efficiency | — | `eff = 1 − 0.5·w²` (PHS form) | same |
| Latent heat of sweat | `E_rsw = 0.68 · m_rsw` (W per g/(h·m²)) | same | — |

Sources: Gagge column — `two_nodes_gagge.py` constants (ASHRAE 55). Older column — **Ji L, Laouadi A, Wang L, et al. "Development of a bioheat model for older people under hot and cold exposures." *Building Simulation* 2022;15(10):1815–1829. [doi:10.1007/s12273-022-0890-3](https://doi.org/10.1007/s12273-022-0890-3)**, as implemented in `pythermalcomfort.models.two_nodes_gagge_ji` (source read directly). Ji's own reported accuracy against published measurements: ≈0.30 °C for core temperature and ≈0.60 °C for mean skin temperature.

The older sweat equation differs in form, not just gain:
`m_rsw = c_swe · 170 · ((1−α)·ΔT_cr,sw + (α + 0.2)·ΔT_sk,sw) · exp(ΔT_sk,sw / 10.7)`
with `a_cof = 0.2`. The young form is `170 · ΔT_body · exp(ΔT_sk / 10.7)`. Because the older thresholds sit higher (37.0/34.3 vs 36.8/33.7 °C), sweating **starts later** even with the same gain — which is the right qualitative shape (Inoue 1999: no change in central drive, delayed onset).

### 1.5 Heat-transfer coefficients at rest indoors

| Coefficient | Value | Condition / source |
|---|---|---|
| Linearised radiative `h_r` | 4.7 W/(m²·°C) initial, then `4·0.97·σ·((T_cl+T_r)/2 + 273.15)³ · f_eff` | `f_eff` = **0.70 seated**, **0.77 standing** (Gagge/Ji code) |
| `h_r` at 30 °C surfaces, seated | ≈ 4.3 W/(m²·°C) | computed from the above |
| Free convection `h_c`, v < 0.2 m/s | `2.5 · |T_cl − T_db|^0.16` (upward) / `2.5 · |ΔT|^0.41` (downward) | Gao et al. 2019 form used by Ji; gives ≈ 2.5–3.4 W/(m²·°C) indoors |
| `h_c` floor (ASHRAE) | 3.0 W/(m²·°C) | `two_nodes_gagge.py` |
| Forced convection | `8.6 · v^0.53` | v in m/s; at 1.5 m/s (ceiling fan) = 10.8 W/(m²·°C) |
| `h_c` for met > 0.85 (ASHRAE standard env.) | `max(3.0, 5.66·(met − 0.85)^0.39)` | `two_nodes_gagge.py` |
| Lewis relation | 2.2 / (p/p₀) K/kPa | — |
| Clothing area factor `f_cl` | `1 + 0.2·clo` (clo < 0.5), `1.05 + 0.1·clo` (clo ≥ 0.5) | — |
| Vapour permeation efficiency `i_cl` | 1.0 naked, **0.45** clothed | — |

**Indoor still-air total `h` ≈ 7.5–8.0 W/(m²·°C)** for a seated person at 0.1 m/s — the dominant term in a no-AC Athens flat.

### 1.6 Metabolic rates — and the unit trap

**Two incompatible "MET" conventions exist and mixing them is a ~20 % error.**

| Convention | 1 unit equals | For a 73 kg / 1.84 m² older adult |
|---|---|---|
| ASHRAE / Gagge **met** | **58.2 W/m²** | 107 W total ≈ 4.2 mL O₂/(kg·min) |
| Exercise-science **MET** (Compendium, PSU HEAT) | 3.5 mL O₂/(kg·min) | 89 W total ≈ 48 W/m² |
| **MET60+** (Older Adult Compendium) | **2.7 mL O₂/(kg·min)** | 69 W total ≈ 37 W/m² |

Conversion: `met_ASHRAE ≈ 0.81 × MET_3.5 ≈ 0.63 × MET60+` for a standard 73 kg adult. **The two-node model takes `met` in ASHRAE units.**

The MET60+ base of 2.7 mL/(kg·min) *is* the quantitative statement of lower resting metabolic rate with age: **2.7/3.5 = 0.77, i.e. a 23 % lower resting VO₂ per kg** (Herrmann SD, et al. "Older Adult Compendium of Physical Activities: energy costs of human activities in adults aged 60 and older." *J Sport Health Sci* 2024; [pacompendium.com](https://pacompendium.com/older-adult-compendium/)).

**Measured metabolic rates, 65+ (PSU HEAT, 248 trials, recomputed here from `heat_guardian_train.sqlite` dataset 3):**

| Activity | Net M [W/m²] | VO₂ [L/min] | MET (3.5) | **met (ASHRAE)** |
|---|---|---|---|---|
| Older, seated **Rest** (n = 82) | **50.0** | 0.279 | 1.11 | **0.86** |
| Older, **Minimal Activity** / ADL (n = 79) | **80.0** | 0.443 | 1.73 | **1.37** |
| Young, Minimal Activity (n = 87) | 83.9 | 0.472 | 1.80 | 1.44 |

Use **met = 0.86 for a seated older adult at rest** — not 1.0. §7 shows this single change is what makes the model match Meade 2024.

**Activity table for the scenario generator** (MET60+ from the 2024 Older Adult Compendium; met_ASHRAE = 0.63 × MET60+; ASHRAE 55 column from `pythermalcomfort.utilities.met_typical_tasks`):

| Activity | MET60+ | met (ASHRAE, 65+) | W/m² | ASHRAE 55 table (all ages) |
|---|---|---|---|---|
| Sleeping | — | 0.7 | 41 | 0.7 |
| Lying quietly awake / watching TV in bed | 1.3 | 0.82 | 48 | 0.8 (reclining) |
| Sitting quietly, general | 1.3 | 0.82 | 48 | 1.0 (seated, quiet) |
| Sitting, watching TV | 1.3 | 0.82 | 48 | 1.0 |
| Standing quietly / in a queue | 1.5 | 0.95 | 55 | 1.2 |
| Laundry: fold, hang, load machine | 2.0 | 1.26 | 73 | — |
| Cooking, serving food, setting table | 2.8 | 1.76 | 103 | 1.8 (cooking) |
| Mopping, standing, light effort | 3.0 | 1.89 | 110 | 2.7 (house cleaning) |
| Walking 1.0–1.9 mph, slow, level | 4.0 | 2.52 | 147 | 2.0 (2 mph) |
| Walking, leisurely, self-selected pace | 4.0 | 2.52 | 147 | 1.7 (walking about) |
| Sweeping carpet/floors, general | 4.3 | 2.71 | 158 | — |

**Caution:** the Compendium's slow-walk MET60+ of 4.0 is far above the ASHRAE value for 2 mph (2.0 met) and above PSU's measured "light ambulation". For the simulator, prefer **1.4–1.8 met (ASHRAE) for slow indoor walking and household tasks in 65+**, which is what PSU HEAT actually measured (80 W/m²), and treat the Compendium's 4.0 as an upper bound for brisk outdoor walking. Measured household METs are typically *lower* than Compendium estimates (Li et al., *J Phys Act Health* 2022;19:404, [doi:10.1123/jpah.2022-0011](https://doi.org/10.1123/jpah.2022-0011) — measured vs estimated differed by ±0.3 to 2.2 MET, most measured values lower).

### 1.7 Clothing — light summer indoor

| Ensemble | I_cl [clo] | Source |
|---|---|---|
| Walking shorts + short-sleeve shirt | 0.36 | ASHRAE 55 table, via `clo_typical_ensembles` |
| **Typical summer indoor clothing** | **0.5** | ASHRAE 55 |
| Knee-length skirt, short-sleeve shirt, sandals, underwear | 0.54 | ASHRAE 55 |
| Trousers, short-sleeve shirt, socks, shoes, underwear | 0.57 | ASHRAE 55 |
| Trousers, long-sleeve shirt | 0.61 | ASHRAE 55 |
| Sleepwear + light bedding (bed rest) | ~0.4–0.8 effective | inferred; O'Connor 2026 bed-rest protocol used sleepwear + sheet |

**Recommended simulator defaults:** `clo = 0.4` for an older adult indoors at home in summer (ASHRAE 0.5 minus the sandals/shoes a person at home often omits), `clo = 0.5–0.6` going out, `clo = 0.6` in bed with a sheet. ISO 9920 itself is paywalled and was not opened; these values come from the ASHRAE 55 tables as reproduced in a peer-reviewed open-source library. Clothing ventilation from walking can cut effective `I_cl` substantially (Bouskill, Havenith et al., *AIHA J* 2002;63:262, [doi:10.1080/15428110208984712](https://doi.org/10.1080/15428110208984712)); a single static clo is a simplification worth stating.

---

## 2. Age effects, quantitatively

### 2.1 Sweating

| Finding | Value | Population | Source |
|---|---|---|---|
| **Whole-body sweat rate at the critical environmental limit, older vs young** | older 77–92 vs young 122–202 g/(m²·h) → **ratio 0.44–0.63, mean ≈ 0.55** | 49 older (71 ± 6) vs 51 young (23 ± 4), 248 trials | recomputed from PSU HEAT raw data (dataset 3, `heat_guardian_train.sqlite`); primary paper Wolf et al. 2023 [MC E12] |
| **Maximum skin wettedness `ω_max`, 65+** | ADL: **0.47** (0.37–0.57) at 34 °C, **0.40** (0.36–0.43) at 12 mmHg · Rest: **0.31** (0.21–0.35) and **0.34** (0.28–0.37) | 49 adults 65–92 y | Kenney WL, Cottle RM, Vecellio DJ, Fisher KG, Leach OK, Kong Q, Wolf ST. "Age and livability in a hotter climate." *EBioMedicine* 2025;122:106020, Table 2. [doi:10.1016/j.ebiom.2025.106020](https://doi.org/10.1016/j.ebiom.2025.106020) |
| Whole-body sweat rate at rest indoors, 72 y | 20 (SD 30) / 26 (15) / 31 (15) / **80 (24)** g/(h·m²) at 22/26/31/36 °C | 16 adults, median 72 y, 8 h seated | Meade et al. *EHP* 2024;132:27003, Table (recomputed from full text). [doi:10.1289/EHP13159](https://doi.org/10.1289/EHP13159) · [ALG §3] |
| Total heat loss declines with age | **≈ 4 % per decade** in moderate and vigorous exercise in dry heat | n = 80, 18–70 y | D'Souza et al. *MSSE* 2020, [doi:10.1249/mss.0000000000002373](https://doi.org/10.1249/mss.0000000000002373) · [ALG §3] |
| Evaporative heat loss blunted in first 30 min of passive heat | 134 vs 151 W (**0.89×**) | 30 older (55–73) vs 30 young, 3 h at 44 °C | Kenny et al. *Temperature* 2017;4:79 [MC E8] |
| Whole-body evaporative heat loss at fixed heat production | older 424 ± 38 vs young 472 ± 42 W at 400 W (**0.90×**); 485 ± 44 vs 558 ± 51 W at 500 W (**0.87×**); **no difference below 400 W** | 10 young (21 ± 1), 10 older (65 ± 3) | Stapleton et al. "Aging impairs heat loss, but when does it matter?" *J Appl Physiol* 2015;118:299. [doi:10.1152/japplphysiol.00722.2014](https://doi.org/10.1152/japplphysiol.00722.2014) |
| Age at which the decrement first appears | from **40–44 y** for heat storage; sweat rate reduced from 45–49 y (final bout) and in all bouts by 56–70 y | 85 males 20–70 y, 35 °C/20 % RH | Larose et al. *PLoS ONE* 2013;8:e83148 [MC E9]. [doi:10.1371/journal.pone.0083148](https://doi.org/10.1371/journal.pone.0083148) |
| Humid vs dry heat, by age | evaporative heat loss cut 17–25 % by humidity in **every** age band; 40–70 y stored **60–85 % more heat (dry)** and **13–38 % more (humid)** than 20–30 y | 60 men, 5 age bands, 35 °C 20 % vs 60 % RH | Larose et al. *J Appl Physiol* 2014;117:69. [doi:10.1152/japplphysiol.00123.2014](https://doi.org/10.1152/japplphysiol.00123.2014) |
| **Mechanism** | lower sweat output *per heat-activated gland*, not fewer glands; **no change in the core-temperature threshold for sweating** and **no change in central sudomotor drive** (slope of expulsion frequency vs T_body unchanged); onset time longer at every site | 7–10 older (60–76) vs 7–9 young (20–25) | Inoue et al. *J Appl Physiol* 1991;71:2453 ([doi:10.1152/jappl.1991.71.6.2453](https://doi.org/10.1152/jappl.1991.71.6.2453)); Inoue et al. *Eur J Appl Physiol* 1999;79:121 ([doi:10.1007/s004210050485](https://doi.org/10.1007/s004210050485)) |
| Regional sweat ratio older/young, last 30 min of passive heat | forehead **1.05**, chest **0.99**, forearm **1.06**, back **0.88**, thigh **0.63** | 10 older (64–76) vs 10 young | Inoue & Shibasaki, *Eur J Appl Physiol* 1996;74:78. [doi:10.1007/BF00376498](https://doi.org/10.1007/BF00376498) |
| Time to steady-state sweating | **≈ 35 min older vs ≈ 30 min young** | as above | Inoue 1999 |
| NO-dependent sweating lost with age | L-NAME cut forearm sweat 26 % in young, **0 % in older**; baseline local rate 0.69 ± 0.19 vs 0.90 ± 0.17 mg/(min·cm²) = **0.77×** | 10 young (23 ± 3) vs 10 older (64 ± 5) | Stapleton et al. *Exp Physiol* 2014;99:921. [doi:10.1113/expphysiol.2013.077644](https://doi.org/10.1113/expphysiol.2013.077644) |
| JOS-3 regional sweat multipliers for age ≥ 60 (model, not measurement) | head/neck **0.69**, chest 0.59, back 0.52, pelvis **0.40**, arms **0.75**, legs **0.40** | model | `jos3/thermoregulation.py` `sd_sweat`; cf. REPORT §7 |

**Simulator recommendation.** Implement the age effect on sweating as **(a) higher onset thresholds** (T_core 37.0, T_skin 34.3 °C, Ji 2022) plus **(b) a hard `ω_max` cap of 0.31–0.47** rather than as a gain reduction. The measured evidence says central drive and the core threshold are intact (Inoue) and the gain is unchanged (Ji keeps `c_sw` = 170); what fails is the periphery and the achievable wettedness. A single "sweat × 0.55" multiplier reproduces the whole-body rate but gets the *shape* wrong (it would suppress sweating at onset as much as at the ceiling).

### 2.2 Skin blood flow and vasodilation

| Finding | Value | Population | Source |
|---|---|---|---|
| Max skin blood flow ceiling | **63 vs 90 L/(h·m²) = 0.70×** | model for older adults | Ji 2022 (§1.4) |
| Effective vasodilation gain | **0.6 × 50 = 30 vs 120 = 0.25×** (vs ASHRAE's own 50 → 0.60×) | model | Ji 2022 |
| Vasodilation core threshold | **+0.5 °C** (37.3 vs 36.8 °C) | model | Ji 2022 |
| Regional skin blood flow ratio older/young (laser Doppler, last 30 min) | forehead **0.99**, chest **0.58**, thigh **0.50** | 10 older (64–76) vs 10 young | Inoue & Shibasaki 1996 |
| Mechanism | smaller release of vasoconstrictor tone **and** less active vasodilation once sweating begins; regional, progressing lower limb → upper body → head | 11 young, 10 older | Inoue et al. *Eur J Appl Physiol* 1998;79:17. [doi:10.1007/s004210050467](https://doi.org/10.1007/s004210050467) |
| Reflex vasodilation magnitude | older increase skin blood flow **2–3× less** than young in passive and active heating | review | Millyard et al. *Gerontol Geriatr Med* 2020;6. [doi:10.1177/2333721420932432](https://doi.org/10.1177/2333721420932432) · [ALG §3] |
| Impairment sites | diminished sympathetic outflow; altered presynaptic transmitter synthesis; reduced vascular responsiveness; impaired endothelial/smooth-muscle second messengers. **Both** vasoconstriction and vasodilation impaired | mechanistic review | Holowatz & Kenney, *J Appl Physiol* 2010;109:1538. [doi:10.1152/japplphysiol.00338.2010](https://doi.org/10.1152/japplphysiol.00338.2010) (abstract only — publisher full text blocked) |
| JOS-3 regional vasodilation multipliers for age ≥ 60 | head/neck **0.91**, chest/back 0.47, pelvis **0.31**, arms 0.47, legs **0.31**; vasoconstriction unchanged (1.00) | model | `jos3/thermoregulation.py` `sd_dilat`, `sd_stric` |

**The wrist matters here.** Inoue's gradient (forehead ≈ unchanged, chest 0.58, thigh 0.50; forearm sweat 1.06 but forearm skin blood flow reduced in phase A) means **the wrist is not a worst-case site**: the arm sits mid-gradient. A wrist-only skin-temperature model will *under-read* the strain in the trunk and legs. Build the sensor model with the wrist as an arm segment, not as "mean skin".

### 2.3 Cardiovascular response

| Finding | Value | Population | Source |
|---|---|---|---|
| **Cardiac output at the limit of thermal tolerance** | **7.4 ± 0.2 (older) vs 11.1 ± 0.7 L/min (young) = 0.67×** | 7 young (23 ± 1) vs 7 older (70 ± 3) men, water-perfused suit | Minson CT, Wladkowski SL, Cardell AF, Pawelczyk JA, Kenney WL. "Age alters the cardiovascular response to direct passive heating." *J Appl Physiol* 1998;84:1323. [doi:10.1152/jappl.1998.84.4.1323](https://doi.org/10.1152/jappl.1998.84.4.1323) |
| Stroke volume | **68 ± 4 vs 99 ± 7 mL/beat = 0.69×** — the primary cause | same | Minson 1998 |
| **Absolute HR rise** | **similar** in young and older | same | Minson 1998 |
| **HR as % of HR_max** | **75 ± 4 % (older) vs 62 ± 3 % (young)** — older use more of their chronotropic reserve for the same HR | same | Minson 1998 |
| Splanchnic + renal redistribution | 720 ± 100 vs 960 ± 80 mL/min = **0.75×** | same | Minson 1998 |
| Esophageal and skin temperature rise, and time to tolerance | **no difference** | same | Minson 1998 |
| Relative HR rise in 3 h at 44 °C | **+25 % in both** older and young | 30 vs 30 | Kenny 2017 [MC E8] |
| Resting HR vs indoor temperature, 72 y | 60 / 62 / 69 / 74 bpm at 22/26/31/36 °C; **+1.0 bpm per °C ambient**; +13 bpm at 36 °C | 16 adults, 8 h | Meade 2024 [ALG §3] |
| RMSSD | 20.4 / 17.3 / 13.5 / 9.3 ms (**halved** by 36 °C); −0.8 ms per °C | same | Meade 2024 [ALG §3] |
| Systolic BP | 142 → 114 mmHg; **−2.1 mmHg per °C** ambient; 3/16 had orthostatic symptoms at 36 °C | same | Meade 2024 [ALG §3] |
| HR/HRV discrimination of a >1 °C core rise in older adults | **AUC ≤ 0.65** (poor) | 39 older, 9 h at 40 °C | Carrillo et al. 2024, [doi:10.1139/apnm-2024-0191](https://doi.org/10.1139/apnm-2024-0191) · [ALG §3] |
| HR_max | 208 − 0.7 × age (SD ≈ 10 bpm) | meta-analysis, 18,712 | Tanaka 2001 [MC E15] |

**HR per °C of core — the open number.** Two sources disagree:
- Derived from Meade 2024: core +0.07 °C/°C ambient and HR +1.0 bpm/°C ambient ⇒ **≈ 14 bpm per °C core** at rest. (This is *my* arithmetic on their two linear trends, not their published result.)
- Minson 1998 and Kenny 2017: the absolute and relative HR rises are the **same as young**, which for passive heat in young adults is typically 25–35 bpm/°C core.

REPORT §7 already records this as the κ ambiguity (κ ≈ 1.0 from Kenny 2017, ≈ 0.8 from JOS-3, ≈ 0.72 reserve-matched), and MEDICAL_CALIBRATION §5.2 shows Danger holds at 26–29/33 across that range while false alarms double at κ = 1. **Simulate the full range κ ∈ [0.7, 1.0] and report per-κ results**; do not pick one.

### 2.4 Body composition, fluid and perception

| Finding | Value | Source |
|---|---|---|
| PSU HEAT 65+ cohort | n = 49 (21 M, 28 F), age 71 (65–92), height 1.7 ± 0.1 m, BMI 26 ± 5 (18.7–38.1), A_D 1.82 ± 0.23 m² (1.40–2.33), A_D/mass 0.025 ± 0.003 m²/kg (0.019–0.031), VO₂max 28 ± 9 (15–50) mL/(kg·min) | Kenney 2025 *EBioMedicine*, Table 1 |
| Total body water | **falls 10–15 %** in older people; urine concentrating ability reduced; dehydrated older inpatients ≈ 6× mortality | Cohen, Fernie & Roshan Fekr, *Nutrients* 2021;13:2092. [doi:10.3390/nu13062092](https://doi.org/10.3390/nu13062092) · [ALG §3] |
| Sarcopenia → thermal properties | muscle and fat differ in water content, so specific heat changes; fat-free weight explains **> 80 %** of between-person variance in blood volume, and blood volume drives the heat-stress cardiac response | Kenney WL & Buskirk ER, *J Gerontol A* 1995;50(Spec):78. [doi:10.1093/gerona/50a.special_issue.78](https://doi.org/10.1093/gerona/50a.special_issue.78) |
| **Thirst after 24 h water deprivation** | older men **less thirsty, drank less**, did not restore plasma/urine dilution, despite *greater* rises in plasma osmolality, Na⁺ and vasopressin | **Phillips PA, Rolls BJ, Ledingham JG, et al. *N Engl J Med* 1984;311:753.** [doi:10.1056/NEJM198409203111202](https://doi.org/10.1056/NEJM198409203111202) |
| Higher osmotic operating point for thirst; slower rehydration | qualitative | Kenney & Chiu, *MSSE* 2001;33:1524 [MC E10] |
| Hypohydration does **not** cut older adults' sweating the way it cuts young adults' | young: evaporative loss 199 ± 6 (hypo) vs 211 ± 10 W/m² (eu) light, 287 ± 15 vs 307 ± 13 moderate (both p ≤ 0.01). **Middle-aged: no change** (223 ± 6, 299 ± 15 across conditions, p ≥ 0.32) at ~4 % body-mass deficit | Meade et al. *Acta Physiol* 2019;226:e13226. [doi:10.1111/apha.13226](https://doi.org/10.1111/apha.13226) |
| Mechanism: blunted osmotic sensitivity | 3 % NaCl infusion raised end-exercise rectal T in young (38.3 ± 0.4 vs 37.9 ± 0.3 °C) but **not** in 61 ± 5 y (38.3 ± 0.3 vs 38.2 ± 0.2 °C) | Meade et al. *J Physiol* 2020;598:5133. [doi:10.1113/JP280132](https://doi.org/10.1113/JP280132) |
| Core-temperature penalty of hypohydration (young/general) | **+0.1 to +0.23 °C per 1 % body-mass loss**; 1 % is the critical level; raises the sweating threshold without changing the slope; reduces skin blood flow at a given core temperature | Sawka MN, Montain SJ, Latzka WA. *Body Fluid Balance During Exercise-Heat Exposure*, USARIEM TN96-2 (1996), p. 12–15. [apps.dtic.mil/sti/pdfs/ADA307206.pdf](https://apps.dtic.mil/sti/pdfs/ADA307206.pdf) |
| Fluid intake in 8 h indoor heat, 72 y | 0.48 L at 22 °C → **1.22 L at 36 °C**; net deficit still −0.5 to −0.7 % body mass | Meade 2024 [ALG §3] |
| Thermal perception | older adults "appear to perceive physiological strain poorly" | Millyard 2020 · [ALG §3] |

**Simulator recommendation on dehydration.** Model the fluid state, but apply the hypohydration penalty **weakly in 65+**: Meade 2019/2020 show the sweat-suppressing arm of the response is already blunted by middle age. The real age penalty is *behavioural* (Phillips 1984: they do not drink), not thermoregulatory. So in the simulator, dehydration in an older agent should accumulate faster (less drinking) but add less *extra* sweat suppression than Sawka's young-adult coefficient implies. Use +0.10 °C per % body-mass loss as a lower-bound carry-over, and say it is an extrapolation.

---

## 3. Older-adult environmental limits

### 3.1 Critical limits, recomputed from the raw PSU HEAT trial data

All values below are **means over individual trials** in dataset 3 of `/home/claude/hgdata/heat_guardian_train.sqlite` (Zenodo 10197956, the trial data behind Wolf et al. 2023 [MC E12]). This table adds the **older-adult Rest condition**, which MEDICAL_CALIBRATION does not tabulate.

| Protocol | Group | n | T_db,crit [°C] | P_a,crit [kPa] | RH [%] | Net M [W/m²] | Sweat [g/(m²·h)] |
|---|---|---|---|---|---|---|---|
| 34 °C, rising P_a | older Rest | 12 | 33.9 | **3.53** | 66.8 | 49.8 | 45 |
| 34 °C, rising P_a | older ADL | 12 | 33.9 | **3.41** | 64.6 | 75.5 | 77 |
| 34 °C, rising P_a | young ADL | 14 | 33.9 | 4.23 | 79.8 | 84.2 | 122 |
| 36 °C, rising P_a | older Rest | 14 | 36.2 | **3.52** | 58.7 | 46.8 | 58 |
| 36 °C, rising P_a | older ADL | 13 | 36.2 | **3.21** | 53.5 | 80.7 | 84 |
| 36 °C, rising P_a | young ADL | 14 | 36.0 | 3.95 | 66.6 | 78.0 | 136 |
| 38 °C, rising P_a | older Rest | 14 | 38.1 | **3.57** | 53.5 | 50.2 | 68 |
| 38 °C, rising P_a | older ADL | 14 | 38.0 | **3.07** | 46.1 | 82.4 | 89 |
| 38 °C, rising P_a | young ADL | 12 | 38.1 | 3.96 | 59.6 | 81.9 | 202 |
| 40 °C, rising P_a | older Rest | 14 | 40.1 | **2.88** | 38.8 | 49.1 | 65 |
| 40 °C, rising P_a | older ADL | 14 | 40.2 | **2.54** | 34.1 | 84.4 | 90 |
| 40 °C, rising P_a | young ADL | 13 | 40.0 | 3.80 | 51.6 | 83.0 | 178 |
| 12 mmHg, rising T_db | older Rest | 15 | **46.1** | 1.54 | 15.6 | 51.5 | 52 |
| 12 mmHg, rising T_db | older ADL | 16 | **42.9** | 1.58 | 18.8 | 77.8 | 92 |
| 12 mmHg, rising T_db | young ADL | 17 | 49.3 | 1.62 | 13.7 | 88.9 | 186 |
| 16 mmHg, rising T_db | older Rest | 13 | **44.1** | 2.14 | 24.0 | 52.5 | 52 |
| 16 mmHg, rising T_db | older ADL | 10 | **40.3** | 2.12 | 28.6 | 78.7 | 83 |
| 16 mmHg, rising T_db | young ADL | 17 | 46.4 | 2.15 | 21.0 | 85.5 | 142 |

Linear fits over **individual trials** (not group means — this differs from, and should be preferred to, the group-mean fits in MEDICAL_CALIBRATION §3):

| Group / activity | Fit (P_a,crit in kPa, T_db in °C) | n | r |
|---|---|---|---|
| **Older, ADL** | `P_a,crit = 8.048 − 0.1399 · T_db` | 79 | −0.59 |
| **Older, Rest** | `P_a,crit = 8.308 − 0.1370 · T_db` | 82 | −0.70 |
| Young, ADL | `P_a,crit = 10.174 − 0.1701 · T_db` | 87 | −0.93 |

The low r for older adults is itself a finding: **older adults' limits are far more variable** (SD of T_crit ≈ 4 °C vs ≈ 2 °C in young — Fisher, Cottle, Kenney & Wolf, *Int J Exerc Sci* 2023, [conference abstract](https://digitalcommons.wku.edu/cgi/viewcontent.cgi?article=7973&context=ijesab): T_crit 49.3 ± 2.3 young, 45.1 ± 4.0 middle-aged (54 ± 8 y), 43.2 ± 4.1 older (71 ± 5 y); P_crit 31.7 ± 1.6, 27.9 ± 5.5, 23.1 ± 5.8 mmHg; T_crit declines linearly with age R² = 0.34, P_crit curvilinearly R² = 0.50, **steepening from about age 50**).

**Critical wet-bulb temperature** (computed here from each trial's T_db and RH with the Stull approximation):

| Group / activity | T_wb,crit humid protocols (34–40 °C) | T_wb,crit dry protocols (12/16 mmHg) |
|---|---|---|
| Older, ADL | **27.0–28.3 °C** | 24.0–25.6 °C |
| Older, Rest | **28.3–29.9 °C** | 24.7–26.7 °C |
| Young, ADL | 30.6–31.2 °C | 25.9–27.4 °C |

This independently reproduces two published statements: Kenney 2025's "for older adults in environments over 50 % rh, critical T_wb ≈ **28.5 °C**", and Vecellio et al. 2022's young-adult mean of **30.55 ± 0.98 °C**, well below the theoretical 35 °C limit (*J Appl Physiol* 2022;132:340, [doi:10.1152/japplphysiol.00738.2021](https://doi.org/10.1152/japplphysiol.00738.2021)). **A critical T_wb is a usable one-number rule in humid heat; it fails in dry heat**, where the limit is set by radiant/convective gain instead.

### 3.2 Rate of core-temperature rise

| Condition | Rate [°C/h] | Source |
|---|---|---|
| **Above** the critical limit, older, ADL | **0.62 ± 0.48** | Wolf 2023 [MC E12] |
| Above the limit, older, Rest | **0.69 ± 0.50** | Wolf 2023 (full text, §Results) |
| Above the limit, young, ADL | 0.70 ± 0.54 | Wolf 2023 |
| Uncompensable, young: warm-humid MinAct / LightAmb | 0.74 / 0.87 | Cottle et al. *J Appl Physiol* 2022;133:1011. [doi:10.1152/japplphysiol.00388.2022](https://doi.org/10.1152/japplphysiol.00388.2022) |
| Uncompensable, young: hot-dry MinAct / LightAmb | 0.71 / 0.93 | Cottle 2022 |
| **Compensable** (just below the limit), young: WH MinAct / LightAmb | **0.06 / 0.09** | Cottle 2022 |
| Compensable, young: HD MinAct / LightAmb | **0.12 / 0.15** | Cottle 2022 |
| Time to reach the heat-stroke criterion of 40.2 °C | **4–10 h above** the critical limit; **35–36 h just below** it | Kenney 2025 *EBioMedicine* |
| 3 h at 44 °C / 30 % RH, 55–73 y | end rectal **37.8 ± 0.3** vs young 37.6 ± 0.2 °C; heat storage 358 ± 173 vs 202 ± 92 kJ (**1.8×**) | Kenny 2017 [MC E8] |
| 8 h seated at 36 °C / 45 % RH, 72 y | core **+0.9 °C** (CI 0.8–1.1); at 31 °C **+0.7** (0.5–0.8); at 26 °C **+0.2** (0.0–0.3, not meaningful) | Meade 2024 [ALG §3, §6] |
| 9 h at 40 °C, 64–79 y | **39 % (15/39)** had a core rise > 1.0 °C; 67 % had systolic BP fall > 10 mmHg | Carrillo 2024 · [ALG §3] |

**Critically for the band: heart-rate drift arrives before the core rise.** In older adults at ADL metabolic rate, the HR inflection consistently precedes the core-temperature inflection: at 36 °C, cardiovascular drift began at **53 % RH (CI 47–59)** while T_c inflected at **57 % RH (CI 50–64)**; at 12 mmHg, HR rose at **41 °C (CI 38–43)** and T_c at **43 °C (CI 41–45)**. HR reaches an elevated steady state 30–40 min in, then is "forced out of equilibrium". (Kenney 2025 *EBioMedicine* §"Heart rate drift as a precursor"; detail in Cottle et al. *J Appl Physiol* 2024;137, [doi:10.1152/japplphysiol.00117.2024](https://doi.org/10.1152/japplphysiol.00117.2024).) **The Virtual Elders simulator must emit an HR channel whose drift onset sits ~4 RH points / ~2 °C T_db earlier than the core inflection** — that is the margin the band's warning tier lives in.

**Sex.** Older women have **lower** limits than age-matched men in both humid and dry heat; women aged 40–60 have limits comparable to men over 65 (Kenney 2025, Fig. 4; Leach et al. 2024; Cottle & Fisher et al. 2024, *Am J Physiol Regul Integr Comp Physiol* 2024, [doi:10.1152/ajpregu.00114.2024](https://doi.org/10.1152/ajpregu.00114.2024)). **Simulate sex explicitly and give women a ~5–10 y age offset.**

### 3.3 Indoor and night-time thresholds

| Threshold | Value | Source |
|---|---|---|
| WHO room temperature | **< 32 °C day, < 24 °C night**; check at 08:00–10:00, 13:00, after 22:00; above 35 °C fans may not prevent heat illness | WHO public information sheet · [ALG §6] |
| Experimentally supported indoor limit for 65+ | **26 °C** ("supports a 26 °C indoor temperature limit for reducing physiological strain and discomfort") | Meade 2024 *EHP*, Discussion. [doi:10.1289/EHP13159](https://doi.org/10.1289/EHP13159) |
| Cellular stress (autophagy/apoptosis markers) | rose at 31 and 36 °C, **not at 26 °C** | McCormick et al. *APNM* 2024, [doi:10.1139/apnm-2023-0361](https://doi.org/10.1139/apnm-2023-0361) · [ALG §6] |
| Best bedroom temperature for sleep, 65+ | **20–25 °C**; a clinically relevant **5–10 % drop in sleep efficiency** from 25 → 30 °C; relationship nonlinear, large between-person variation | Baniassadi A, Manor B, Yu W, Travison T, Lipsitz L. *Sci Total Environ* 2023;899:165623. [doi:10.1016/j.scitotenv.2023.165623](https://doi.org/10.1016/j.scitotenv.2023.165623) |
| 30 °C vs 27 °C bedroom, 65+ | total sleep time **−26.3 min**, sleep efficiency **−5.5 %**, REM **−5.3 min**, wake time **+27.0 min**; sympathetic overactivity and **raised wrist skin temperature** | Yan Y, Zhang H, Kang M, Lan L, Wang Z, Lin Y. *Indoor Air* 2022;32:e13159. [doi:10.1111/ina.13159](https://doi.org/10.1111/ina.13159) |
| **8 h bed rest at 31 °C / 45 % RH, median 71 y** | peak core **37.8 ± 0.2 °C (+1.1 ± 0.5 °C)** with no fan; **37.6 °C (+0.9 °C)** with a 1.5 m/s ceiling fan (−0.2 °C, CI 0.1–0.3, p < 0.001); HR ~5 bpm lower with fan | O'Connor FK, Meade RD, et al. *J Am Geriatr Soc* 2026;74:200. [doi:10.1111/jgs.70109](https://doi.org/10.1111/jgs.70109) |
| 8 h seated at 36 °C with pedestal fans 0 / 2 / 4 m/s, 72 ± 7 y | end core **+1.0 °C in all three** — fans did not help at 36 °C | Lee BJ et al. *Physiol Rep* 2025;13:e70390. [doi:10.14814/phy2.70390](https://doi.org/10.14814/phy2.70390) |
| Air-conditioned respite | 2 h at ~23 °C cut core by 0.8 °C; **benefit gone within ~2 h** of returning to the heat | Meade et al. *EHP* 2023, [doi:10.1289/ehp11651](https://doi.org/10.1289/ehp11651) · [ALG §3] |
| Athens mortality threshold | daily max apparent temperature **32.7 °C**; +4.22 % deaths per °C above it for 75+ | Baccini 2008 [MC E19] |

**Circadian core-temperature rhythm — simulator must include it.**

| Parameter | Value | Source |
|---|---|---|
| Core amplitude, adults 21–78 y (ingestible pill, free-living) | **0.2–0.7 °C** between-subject range; mesor 36.6–37.5 °C; bathyphase (minimum) **23:50–06:50** | Huang Q, Komarzynski S, Bolborea M, Finkenstädt B, Lévi FA. *Front Physiol* 2021;12:659973. [doi:10.3389/fphys.2021.659973](https://doi.org/10.3389/fphys.2021.659973) |
| Endogenous circadian amplitude, older vs young (constant routine / forced desynchrony) | **reduced by 20–30 %** in 65–75 y vs 20–30 y | Dijk DJ, Duffy JF, Czeisler CA. *Chronobiol Int* 2000;17:285. [doi:10.1081/cbi-100101049](https://doi.org/10.1081/cbi-100101049) |
| Phase | **≈ 1 h advance** of the core-temperature and melatonin rhythms in older people; they also wake at an earlier circadian phase | Dijk 2000 |
| Chest-surface temperature circadian amplitude *increases* with age | older subjects showed larger chest-temperature amplitude and reduced ultradian variability | Huang 2021 |
| Baseline resting core, 72 y, thermoneutral | **36.7 ± 0.2 °C** | Meade 2024 [ALG §3] |

**Recommended rhythm for the simulator:** mesor 36.9 °C, amplitude **0.35 °C for 65–85 y** (0.45 °C young × 0.75), minimum at **04:30** (young 05:30, advanced 1 h), cosine with a slight sawtooth (faster evening fall, slower morning rise). Night heat is dangerous partly because it blocks the nocturnal fall: an agent sleeping at 30 °C should show the circadian nadir *attenuated*, not just a higher mean.

---

## 4. Consecutive days and heat waves

**The honest state of the evidence: there is no published multi-day chamber study in adults 65+.** Every older-adult study found is a single exposure of 2–9 h. A 3-consecutive-day protocol exists but is in **18–40-year-olds** and, as of this search, only the protocol is published:

| Finding | Value | Source |
|---|---|---|
| 3 consecutive 8-h simulated workdays, 35 °C / 63 % RH / 31 °C WBGT, 4.3 MET, n = 14 | **protocol only** — primary outcome core temperature; results not yet published; healthy adults **18–40 y** | Main LC, Moore DC, Lum J, Lee B, Corrigan SL, Aisbett B, Notley SR. *Trials* 2026;27:122. [doi:10.1186/s13063-025-09414-4](https://doi.org/10.1186/s13063-025-09414-4). ACTRN12623001069640 |
| **Consecutive work shifts in real heat (~34 °C), 2 days** | peak core day 1 **38.1 ± 0.2 °C** (3/4 workers above 38.0); day 2 **38.4 ± 0.2 °C** (**4/4** above) — *despite* resting more (51 ± 15 % → 66 ± 5 % of the shift). Shift-average core 37.6 ± 0.1 → 37.7 ± 0.2 °C. Peak and average HR **unchanged** between days. All workers dehydrated before *and* after work both days (USG 1.025 → 1.029 pre-shift) | Meade RD, D'Souza AW, Krishen L, Kenny GP. *J Occup Environ Hyg* 2017;14:986. [doi:10.1080/15459624.2017.1365151](https://doi.org/10.1080/15459624.2017.1365151) (n = 4, case report) |
| Overnight recovery removed by warm nights | 2 h of AC respite is undone within ~2 h of return to heat | Meade 2023 (§3.3) |
| Seasonal acclimatisation **reduces** older adults' heat storage more than young | older −213 kJ (CI 131–295, p < 0.001) vs young −25 kJ (p = 0.458) over 3 h at 44 °C; the pre-acclimatisation older–young gap of 222 kJ **disappeared** after summer | Notley SR, Meade RD, Akerman AP, Poirier MP, Boulay P, Sigal RJ, Flouris AD, Kenny GP. *Exp Physiol* 2020;105:1491. [doi:10.1113/EP088728](https://doi.org/10.1113/EP088728) |
| 7 days of passive heat acclimation (warm-water immersion), 68 y | resting renin **+68 %**; **no** change in the magnitude of the acute exercise-heat stress response for any biomarker | Lee BJ, McCormick JJ, et al. *Am J Physiol Regul Integr Comp Physiol* 2026;331:R364. [doi:10.1152/ajpregu.00099.2026](https://doi.org/10.1152/ajpregu.00099.2026) |

**What the simulator should do, and label as a modelling assumption:**
1. **Carry hydration across days.** This is the only mechanism with direct multi-day evidence (Meade 2017: workers started day 2 *more* dehydrated than day 1 and ended higher). Deficit carry-over with a slow (12–24 h) refill constant plus Phillips-1984 blunted thirst reproduces it.
2. **Carry thermal state across nights** by *not* letting the agent reach its circadian nadir when the bedroom is above ~26 °C. Do not invent a "cumulative heat debt" term: no measurement supports one in 65+.
3. **Allow a mild acclimatisation gain over a heat wave** (Notley 2020 says it is real and *larger* in older adults), which partly offsets 1 and 2. Switching it off is a conservative choice; switching it on is the evidenced one. Report both.
4. **HR does not reveal the cumulative effect** (Meade 2017: HR identical day 1 vs day 2 while core was 0.3 °C higher). This is the single strongest argument in the literature for the band's environmental/heat-dose prior, which MEDICAL_CALIBRATION §4c flags as costing false alarms on young walkers but keeps on literature grounds. **Multi-day is where that prior earns its place.**

---

## 5. Medication effects

The best quantitative source is a 2024 meta-analysis of 35 randomised heat-stress studies (353 people, 27 drugs, mean age < 30 y, only one clinical population) — which **contradicts parts of the CDC guidance used in MEDICAL_CALIBRATION [MC E14]**.

| Drug class | Effect on core temperature under heat stress | Certainty | Source |
|---|---|---|---|
| **Strong anticholinergics** (evidence limited to atropine) | **+0.42 °C** (95 % CI 0.04–0.79, p = 0.03) at T_air ≥ 30 °C, with reduced sweating | moderate | Hospers L, Dillon GA, McLachlan AJ, Alexander LM, Kenney WL, Capon A, Ebi KL, Ashworth E, Jay O, Mavros Y. *EClinicalMedicine* 2024;77:102886. [doi:10.1016/j.eclinm.2024.102886](https://doi.org/10.1016/j.eclinm.2024.102886) |
| **Non-selective beta-blockers** | **+0.11 °C** (0.02–0.19, p = 0.02) | — | Hospers 2024 |
| Anti-Parkinson's agents | **+0.13 °C** (0.07–0.19, p = 0.02) | — | Hospers 2024 |
| Adrenaline | +0.41 °C (0.21–0.61) | — | Hospers 2024 |
| **Antidepressants, diuretics, weak anticholinergics** | **no detectable change** in core temperature | — | Hospers 2024 |
| Atropine 2 mg i.m., 49 °C walking | sweat loss **−65 %** (−151 g/(m²·h)); rectal **+0.4 °C**, skin **+2.8 °C**, HR **+48 % (+53 bpm)**. After heat acclimation the sweat penalty fell to −33 % | — | Kolka MA, Levine L, Cadarette BS, Rock PB, Sawka MN, Pandolf KB. *Aviat Space Environ Med* 1984;55:1107. PMID 6517816 |
| Propranolol 80 mg, 40 min cycling at 60 % VO₂max | esophageal T **+0.48 °C at 22 °C** (37.66 → 38.14) and **+0.28 °C at 32 °C** (38.13 → 38.41); HR 137 → 104 bpm at 32 °C; reduced slope of the forearm-blood-flow-vs-core relationship and lower maximal forearm blood flow; systolic BP −20 mmHg | 6 fit men | Pescatello LS, Mack GW, Leach CN, Nadel ER. *J Appl Physiol* 1987;62:1448. [doi:10.1152/jappl.1987.62.4.1448](https://doi.org/10.1152/jappl.1987.62.4.1448) |
| Propranolol, 90 min at 40 % VO₂max, 31.7 °C | lower forearm blood flow, **no significant rectal change**, *greater* sweat loss | 14 subjects | Freund 1987 [MC E13] |
| HR_max on beta-blockers | **164 − 0.7 × age** (SEE 18 bpm, r² = 0.13) | 334 CHD patients | Brawner 2004 [MC E16] |
| Antipsychotics + benzhexol, real-world | recurrent heat stroke then heat exhaustion in one patient; neuroleptics combine anticholinergic and central effects, and antidopaminergic action can raise the set-point | case report | Kwok & Chan, *Ann Pharmacother* 2005;39:1940. [doi:10.1345/aph.1G130](https://doi.org/10.1345/aph.1G130) |
| Clinical guidance (qualitative) | beta-blockers: ↓superficial vasodilation, ↓sweating, hypotension/falls · diuretics: volume depletion, dehydration, ↓thirst · ACE-I/ARB: ↓thirst, hypotension · anticholinergics/antipsychotics: ↓sweating, impaired central thermoregulation | expert opinion | CDC 2025 [MC E14]; EODY [MC E7] |

**Parameterisation for the simulator:**

| Flag | Simulator change | Justification |
|---|---|---|
| Beta-blocker (non-selective) | HR_max = 164 − 0.7·age; **flatten the HR-vs-core slope by the same factor** (Pescatello: 137 → 104 bpm at a *higher* core); reduce max skin blood flow by a further ~15 %; core offset **+0.11 °C** | Brawner 2004, Pescatello 1987, Hospers 2024 |
| Beta-1 selective (atenolol etc.) | HR flattened, **no core penalty** | Hospers 2024 found the effect only for non-selective agents; Trinity 2010 (*J Appl Physiol* 109:745, [doi:10.1152/japplphysiol.00377.2010](https://doi.org/10.1152/japplphysiol.00377.2010)) used low-dose atenolol purely to hold HR flat |
| Strong anticholinergic / antipsychotic | **sweat capacity × 0.35–0.65**, core offset **+0.42 °C**, HR **+45 %** of the un-medicated rise | Hospers 2024, Kolka 1984 |
| Diuretic | start the day with a **0.5–1.5 % body-water deficit** and raise urine output; **do not** add a direct core-temperature penalty | Hospers 2024 (no core effect), CDC (volume depletion) |
| ACE-I / ARB | blunt the thirst drive further; **no direct thermal term** | Hospers 2024, CDC |

**This is a correction to the band's current medication model.** MEDICAL_CALIBRATION §6 fires the diuretic flag by moving the Drink-water tier 0.1 °C earlier, and labels that size "a design choice". Hospers 2024 now says diuretics do not change core temperature at all — so the *right* place for a diuretic flag is the hydration state and the thirst/behaviour model, not the core-temperature threshold. The Virtual Elders simulator should implement it that way, and the band's threshold shift should be re-justified as a hydration proxy, not a thermal one.

**Limits of all of the above:** every number in the table comes from people with a mean age **under 30**, almost all men (16/353 women), in short exposures. There is no randomised heat-stress trial of a beta-blocker in a 75-year-old. Label every medication result **SIM, literature prior, unvalidated**.

---

## 6. Clinical thresholds for the alarm tiers

Fully sourced in MEDICAL_CALIBRATION §2; summarised here with what is *specific to older adults*.

| Threshold | Meaning | Source |
|---|---|---|
| **38.0 °C** | WHO limit for prolonged daily heavy work; NIOSH: heat exhaustion = core > 38 °C with abnormal organ function; ACGIH action-limit territory. The applicable limit for an unacclimatised, non-medically-selected older person | [MC E4], [MC E5] |
| **38.5 °C** | ACGIH limiting core temperature — explicitly "allows a margin to safely leave" the heat | [MC E5] |
| 38–39 °C | typical heat-exhaustion range (OSHA); ACSM: heat exhaustion = inability to sustain cardiac output/BP, body temperature usually < 40 °C | [MC E2], [MC E3] |
| **> 40 °C with CNS disturbance** | heat stroke. A core ≥ 40 °C **alone is not the diagnosis**; CNS change (personality change → confusion → delirium → stupor → unconsciousness) is the primary identifying sign (ACSM strength-of-recommendation A). Can reach 41 °C within 10–15 min | [MC E1], [MC E3] |
| 40.5 °C | clinical heat stroke (NIOSH); EODY heat-stroke sign list for Greece uses > 40.5 °C | [MC E4], [MC E7] |
| **40.2 °C** | the PSU HEAT working criterion for heat-related illness; reachable in **4–10 h above** the critical environmental limit | Cottle 2022; Kenney 2025 |
| ACGIH HR limit | discontinue exposure on sustained HR ≥ 180 − age | [MC E6] |
| Age statement | NIOSH: "those over the age of 60 are at additional risk"; EODY: older people are a vulnerable group, should not be left alone | [MC E4], [MC E7] |
| **ACGIH limits validated against a >1 °C core rise** | the ACGIH Action Limit Values were tested for validity in moderate-intensity work; relevant because the band's tiers inherit from them | Notley SR et al. *Appl Physiol Nutr Metab* 2022;47:711. [doi:10.1139/apnm-2022-0003](https://doi.org/10.1139/apnm-2022-0003) |

**Specific to older adults — why to act earlier:**
1. **39 % of healthy 64–79-year-olds exceed a 1 °C core rise in 9 h at 40 °C** (Carrillo 2024), i.e. a sizeable minority cross 37.8–38.0 °C in an ordinary indoor heat day.
2. **67 % had a systolic BP fall > 10 mmHg** in the same study, and 3/16 had frank orthostatic symptoms at 36 °C in Meade 2024. Orthostatic collapse arrives **before** the core thresholds. A core-temperature-only alarm ladder will miss the dominant mechanism of heat-wave death, which is cardiovascular (94 % of excess deaths in the 1995 Chicago heat wave had cardiovascular sequelae — Kenney 2025, citing the Chicago series).
3. **HR drift precedes core rise** by ~4 RH points / ~2 °C T_db (§3.2) — an earlier, environment-indexed trigger exists and is measured.
4. **Perception is unreliable** (Millyard 2020), and **thirst is blunted** (Phillips 1984), so the wearer will not self-rescue.
5. **ω_max of 0.85 assumed by ISO is unreachable** for most 65+ (measured 0.31–0.47), so standards-based safe-duration tables **overestimate** what is safe for them (Kenney 2025, explicit).

The band's existing 0.2 °C earlier watch margin at age ≥ 65 [MC §3, sourced to Kenny 2017] is consistent with all of this and is, if anything, conservative.

---

## 7. Validation targets — the checklist the simulator must pass

Every row is a published number the simulator must reproduce. **SIM** rows are runs I did here against the installed models, included so the builder knows what the baseline already achieves.

### 7.1 Resting / indoor

| # | Target | Required value | Tolerance | Source |
|---|---|---|---|---|
| V1 | Resting core, thermoneutral, 72 y | **36.7 ± 0.2 °C** (accept 36.8–37.2 at other times of day) | ±0.2 | Meade 2024 |
| V2 | Core rise after 8 h seated at 26 / 31 / 36 °C, 45 % RH | **+0.2 / +0.7 / +0.9 °C** | ±0.15 | Meade 2024 |
| V3 | Mean skin temperature at 22 / 26 / 31 / 36 °C | **31.7 / 32.9 / 34.9 / 35.9 °C** | ±0.5 | Meade 2024 |
| V4 | Resting HR at 22 / 26 / 31 / 36 °C | **60 / 62 / 69 / 74 bpm**; trend +1.0 bpm/°C | ±3 bpm | Meade 2024 |
| V5 | Sweat rate at 22 / 26 / 31 / 36 °C | **20 / 26 / 31 / 80 g/(h·m²)** | ±15 | Meade 2024 |
| V6 | Fluid intake, 8 h, 22 °C → 36 °C | **0.48 → 1.22 L**, net deficit −0.5 to −0.7 % body mass | ±0.2 L | Meade 2024 |
| V7 | 8 h bed rest at 31 °C | peak core **37.8 ± 0.2 °C (+1.1 °C)**; with 1.5 m/s fan **37.6 °C (+0.9 °C)** | ±0.2 | O'Connor 2026 |
| V8 | 8 h seated at 36 °C with fans at 0/2/4 m/s | **+1.0 °C in all three** (fans do not help) | ±0.2 | Lee 2025 |
| V9 | Circadian core amplitude, 65–85 y | **0.30–0.40 °C** (young 0.45–0.50 × 0.70–0.80), nadir ≈ 04:30 (1 h advanced) | ±0.1 °C, ±1 h | Dijk 2000, Huang 2021 |
| V10 | Mean skin temperature range indoors, 22–36 °C | **31.5–36.0 °C**; wrist skin typically within 0.5–1.5 °C of mean skin at rest | — | Meade 2024 (wrist-specific data **do not exist** — see §8) |

### 7.2 Heat stress and limits

| # | Target | Required value | Source |
|---|---|---|---|
| V11 | 3 h at 44 °C / 30 % RH, 55–73 y vs young | end rectal **37.8 ± 0.3 vs 37.6 ± 0.2 °C**; heat storage 358 ± 173 vs 202 ± 92 kJ (1.8×); relative HR rise +25 % in both | Kenny 2017 [MC E8] |
| V12 | Critical P_a, older ADL, at 34/36/38/40 °C | **3.41 / 3.21 / 3.07 / 2.54 kPa** (25.6 / 24.1 / 23.0 / 19.0 mmHg) | PSU HEAT raw data, §3.1 |
| V13 | Critical P_a, older **Rest**, at 34/36/38/40 °C | **3.53 / 3.52 / 3.57 / 2.88 kPa** | PSU HEAT raw data, §3.1 (**new**) |
| V14 | Critical T_db, older ADL, at 12 / 16 mmHg | **42.9 / 40.3 °C** (young 49.3 / 46.4 °C) — **≈ 6 °C lower** | §3.1 |
| V15 | Critical T_db, older **Rest**, at 12 / 16 mmHg | **46.1 / 44.1 °C** | §3.1 (**new**) |
| V16 | Critical T_wb, older, humid | **27.0–28.3 °C** ADL, 28.3–29.9 °C Rest; young **30.6–31.2 °C** | computed, §3.1 |
| V17 | Core rise rate above the limit | **0.62 ± 0.48 °C/h** older ADL, 0.69 ± 0.50 Rest, 0.70 ± 0.54 young | Wolf 2023 |
| V18 | Core rise rate just **below** the limit | **0.06–0.15 °C/h** | Cottle 2022 |
| V19 | HR drift onset vs core inflection, 65+ | HR first: 53 % vs 57 % RH at 36 °C; 41 vs 43 °C at 12 mmHg | Kenney 2025 |
| V20 | ω_max, 65+ | **0.47 / 0.40 ADL**, 0.31 / 0.34 Rest — never 0.85 | Kenney 2025, Table 2 |
| V21 | Whole-body sweat rate at the limit, older vs young | ratio **0.44–0.63** | PSU HEAT raw data |
| V22 | Cardiac output at thermal tolerance, older vs young | **7.4 vs 11.1 L/min (0.67×)**, SV 68 vs 99 mL (0.69×), same absolute HR rise, 75 % vs 62 % HR_max | Minson 1998 |
| V23 | Fraction of 64–79 y exceeding +1.0 °C core in 9 h at 40 °C | **≈ 39 %** | Carrillo 2024 |
| V24 | Age at which the decrement appears | heat storage elevated from **40–44 y**; evaporative impairment only above ~400 W heat production | Larose 2013, Stapleton 2015 |
| V25 | Inter-individual spread, 65+ | T_crit SD **≈ 4 °C** (vs ≈ 2 °C young); P_crit SD ≈ 5.8 mmHg (vs 1.6) | Fisher 2023 |
| V26 | Sex | older women's limits **below** age-matched men; women 40–60 ≈ men 65+ | Kenney 2025, Cottle & Fisher 2024 |

### 7.3 Multi-day

| # | Target | Required value | Source |
|---|---|---|---|
| V27 | Consecutive days in ~34 °C | peak core **day 1 38.1 ± 0.2 → day 2 38.4 ± 0.2 °C** despite more rest; **HR unchanged between days** | Meade 2017 (n = 4, workers, not 65+) |
| V28 | Hydration carry-over | pre-shift USG **1.025 → 1.029**; dehydrated before and after on both days | Meade 2017 |
| V29 | AC respite decay | 0.8 °C benefit from 2 h at 23 °C, **gone within ~2 h** | Meade 2023 |
| V30 | Seasonal acclimatisation, older | heat storage **−213 kJ** over 3 h at 44 °C (young −25 kJ, n.s.) | Notley 2020 |

### 7.4 Baseline model performance (SIM, run here)

Gagge–Ji older-adult two-node model (`pythermalcomfort.two_nodes_gagge_ji`), 73.2 kg / 1.70 m / A_D 1.84 m², v = 0.1 m/s, 45 % RH, 480 min, unacclimatised, seated:

| met (ASHRAE) | clo | ΔT_core at 26 / 31 / 36 °C | Measured (V2) | T_skin at 26 / 31 / 36 °C | Measured (V3) |
|---|---|---|---|---|---|
| 1.00 | 0.4 | +0.48 / +0.67 / +0.84 | +0.2 / +0.7 / +0.9 | 31.8 / 33.7 / 34.9 | 32.9 / 34.9 / 35.9 |
| **0.86** | **0.4** | **+0.17 / +0.67 / +0.83** | **+0.2 / +0.7 / +0.9** | 32.9 / 33.6 / 34.7 | 32.9 / 34.9 / 35.9 |
| 0.86 | 0.5 | +0.24 / +0.68 / +0.82 | — | 33.3 / 33.6 / 34.8 | — |

**Findings the builder must act on:**
1. **Set `met = 0.86`, not 1.0, for a seated older adult.** It is the measured PSU resting rate (50 W/m² net) and it moves the 26 °C prediction from +0.48 °C (wrong, over double) to **+0.17 °C** (right). At met = 1.0 the model wrongly declares 26 °C a strain condition — exactly the threshold the whole product turns on.
2. **The skin node runs 1.0–1.3 °C cold at 31 and 36 °C.** Either apply a calibrated offset to the reported skin temperature, or reduce the skin-node heat loss (raise effective clo on the skin node, or lower core→skin conductance). Note the comparison is not perfectly like-for-like: Meade's value is an 8-site ISO 9886 mean skin temperature, the model's is a single lumped node.
3. **The model is not monotonic in `met` around 1.1–1.2** (at met 1.2, ΔT_core at 31 °C fell to +0.24 then jumped to +0.72 at 36 °C with T_skin 36.1 °C). The sweating/wettedness fixed-point loop misbehaves there. **Clamp `met` to the measured values (0.86 rest, 1.37 ADL) and assert monotonicity in a unit test**; do not sweep `met` continuously through that band.

---

## 8. Where the evidence is thin or contradictory

1. **JOS-3 vs PSU HEAT in humid heat (carried from REPORT §7, unchanged).** JOS-3 predicts older adults tolerate +0.20 to +0.40 kPa *more* vapour pressure than young; PSU measured 0.70–1.30 kPa *less*. JOS-3 gets dry heat approximately right (−6.5 to −7.0 °C vs measured −6.1 to −6.5 °C). **Do not use JOS-3 for humid Athens nights.** The Gagge–Ji model is the better humid-heat choice here because its age effect is in the thresholds and the `ω_max`/SkBF ceilings, which is where PSU located it.

2. **Calorimetric vs thermometric heat storage do not reconcile.** Kenny 2017's 358 kJ of stored heat in a ~75 kg older adult implies a mean-body rise of 358/(3.49 × 75) = **1.37 °C**, but the measured rectal rise was only ~0.4–0.8 °C. Young: 202 kJ → 0.77 °C implied vs ~0.6 measured. The older group's discrepancy is much larger. Either their storage is disproportionately peripheral (consistent with impaired core→skin convection) or the calorimetric and thermometric methods diverge with age. **A two-node model calibrated to core temperature will under-report heat storage in older agents; calibrated to storage, it will over-report core temperature.** Pick core temperature (that is what the band estimates) and say so.

3. **HR per °C core in older adults is unresolved** (§2.3): ~14 bpm/°C derived from Meade's resting trends vs "same as young" from Minson and Kenny. This is the single largest free parameter in the sensor model. Simulate κ ∈ [0.7, 1.0].

4. **Diuretics: CDC vs meta-analysis.** CDC lists diuretics as a heat risk [MC E14]; Hospers 2024 finds no core-temperature effect in randomised trials. Resolution: the risk is real but runs through volume/hydration and blood pressure, not through a thermal set-point. Model it that way.

5. **Beta-blockers: three studies, three answers.** Pescatello 1987 (young, 40 min, 60 % VO₂max): +0.28 to +0.48 °C. Freund 1987 (young, 90 min, 40 % VO₂max): no significant rectal change [MC E13]. Hospers 2024 (meta-analysis): +0.11 °C, non-selective only. The band's switch correctly targets the **measurement** problem (a blunted HR makes an HR-based estimate read low), not a claim that users heat faster — keep that framing.

6. **No multi-day data in 65+ at all** (§4). Every consecutive-day number available is from four electrical workers or an unpublished protocol in 18–40-year-olds. Any multi-day scenario the simulator generates is an **extrapolation**, and the manager should say so in the WAICY submission.

7. **No wrist skin-temperature data in older adults during passive heat.** All the older-adult studies use 8-site ISO 9886 mean skin temperature [ALG §3, Gaps]. The one datum found is indirect: Yan 2022 reports raised **wrist** skin temperature in 65+ sleeping at 30 °C vs 27 °C, without numbers. The sim-to-real link for the band's primary sensor therefore rests on a mean-skin-to-wrist transfer that is itself unvalidated in this population.

8. **ω_max is not a constant.** PSU measured 0.31–0.47 in 65+, varying with environment *and* metabolic rate, against the ISO assumption of 0.85. Treating `ω_max` as a fixed number — as both the Gagge and Ji implementations do — is wrong for this population. Make it a function of (condition, activity) or at minimum draw it per agent from 0.31–0.57.

9. **Cohort bias in every source.** All the Ottawa HEAT and PSU HEAT cohorts are healthy, community-dwelling volunteers who passed a cardiologist's screen; PSU's 65+ group had VO₂max 28 ± 9 mL/(kg·min), which is fit for 71. **Frail, multimorbid, dementia and heart-failure older adults — the people who actually die indoors alone — are not represented anywhere in this handbook.** The simulator should generate a frailty axis, and every result for it is unvalidated by construction.

10. **ISO 7933 PHS, ISO 8996 and ISO 9920 were not opened** (paywalled), continuing the [MC E22] rule. The metabolic and clothing numbers here come from ASHRAE 55 tables as reproduced in `pythermalcomfort`, from the peer-reviewed Older Adult Compendium, and from the PSU HEAT measurements. Where ISO is named in this document it is as context, never as the source of a number.

---

## 9. Source list

Peer-reviewed unless marked. All URLs/DOIs were resolved during this pass except where noted.

**Two-node models**
- Gagge AP, Stolwijk JAJ, Nishi Y (1971), two-node model — as implemented in ASHRAE 55 and `pythermalcomfort.models.two_nodes_gagge` (source read at `/usr/local/lib/python3.13/site-packages/pythermalcomfort/models/two_nodes_gagge.py`).
- Ji L, Laouadi A, Wang L, et al. *Building Simulation* 2022;15(10):1815–1829. [doi:10.1007/s12273-022-0890-3](https://doi.org/10.1007/s12273-022-0890-3). Reported accuracy ≈0.30 °C core, ≈0.60 °C mean skin. Parameters read from `two_nodes_gagge_ji.py`; the publisher PDF would not fetch.
- Fiala D, Psikuta A, Jendritzky G, et al. *Front Biosci (Schol)* 2010;2:939. [doi:10.2741/s112](https://doi.org/10.2741/s112) — multi-node reference; Fiala's model underlies UTCI (Jendritzky, de Dear & Havenith, *Int J Biometeorol* 2012;56:421, [doi:10.1007/s00484-011-0513-7](https://doi.org/10.1007/s00484-011-0513-7)).
- JOS-3 age coefficients read from `jos3/thermoregulation.py` and `jos3/construction.py` (cardiac index × 1.00 / 0.85 / 0.75 / 0.70 for < 50 / 50–59 / 60–69 / ≥ 70 y).

**Ageing thermoregulation**
- Kenney WL, Munce TA. *J Appl Physiol* 2003;95:2598. [doi:10.1152/japplphysiol.00202.2003](https://doi.org/10.1152/japplphysiol.00202.2003)
- Holowatz LA, Kenney WL. *J Appl Physiol* 2010;109:1538. [doi:10.1152/japplphysiol.00338.2010](https://doi.org/10.1152/japplphysiol.00338.2010)
- Minson CT, Wladkowski SL, Cardell AF, Pawelczyk JA, Kenney WL. *J Appl Physiol* 1998;84:1323. [doi:10.1152/jappl.1998.84.4.1323](https://doi.org/10.1152/jappl.1998.84.4.1323)
- Kenney WL, Buskirk ER. *J Gerontol A* 1995;50(Spec):78. [doi:10.1093/gerona/50a.special_issue.78](https://doi.org/10.1093/gerona/50a.special_issue.78)
- Inoue Y, Nakao M, Araki T, Murakami H. *J Appl Physiol* 1991;71:2453. [doi:10.1152/jappl.1991.71.6.2453](https://doi.org/10.1152/jappl.1991.71.6.2453)
- Inoue Y, Shibasaki M. *Eur J Appl Physiol* 1996;74:78. [doi:10.1007/BF00376498](https://doi.org/10.1007/BF00376498)
- Inoue Y, Shibasaki M, Hirata K, Araki T. *Eur J Appl Physiol* 1998;79:17. [doi:10.1007/s004210050467](https://doi.org/10.1007/s004210050467)
- Inoue Y, Shibasaki M, Ueda H, Ishizashi H. *Eur J Appl Physiol* 1999;79:121. [doi:10.1007/s004210050485](https://doi.org/10.1007/s004210050485)
- Larose J, Boulay P, Sigal RJ, Wright HE, Kenny GP. *PLoS ONE* 2013;8:e83148. [doi:10.1371/journal.pone.0083148](https://doi.org/10.1371/journal.pone.0083148)
- Larose J, Boulay P, Wright-Beatty HE, Sigal RJ, Hardcastle S, Kenny GP. *J Appl Physiol* 2014;117:69. [doi:10.1152/japplphysiol.00123.2014](https://doi.org/10.1152/japplphysiol.00123.2014)
- Stapleton JM, Poirier MP, Flouris AD, Boulay P, Sigal RJ, Malcolm J, Kenny GP. *J Appl Physiol* 2015;118:299. [doi:10.1152/japplphysiol.00722.2014](https://doi.org/10.1152/japplphysiol.00722.2014)
- Stapleton JM, Fujii N, Carter M, Kenny GP. *Exp Physiol* 2014;99:921. [doi:10.1113/expphysiol.2013.077644](https://doi.org/10.1113/expphysiol.2013.077644)
- D'Souza AW et al. *MSSE* 2020. [doi:10.1249/mss.0000000000002373](https://doi.org/10.1249/mss.0000000000002373)
- Millyard A et al. *Gerontol Geriatr Med* 2020;6. [doi:10.1177/2333721420932432](https://doi.org/10.1177/2333721420932432)
- Kenny GP et al. *Temperature* 2017;4:79 [MC E8]
- Notley SR, Meade RD, Akerman AP, et al. *Exp Physiol* 2020;105:1491. [doi:10.1113/EP088728](https://doi.org/10.1113/EP088728)
- Lee BJ, McCormick JJ, et al. *Am J Physiol Regul Integr Comp Physiol* 2026;331:R364. [doi:10.1152/ajpregu.00099.2026](https://doi.org/10.1152/ajpregu.00099.2026)

**Environmental limits (PSU HEAT)**
- Wolf ST, Cottle RM, Fisher KG, Vecellio DJ, Kenney WL. *Commun Earth Environ* 2023;4:486. [doi:10.1038/s43247-023-01159-9](https://doi.org/10.1038/s43247-023-01159-9) [MC E12]; trial data Zenodo 10197956 = dataset 3 of `heat_guardian_train.sqlite`.
- Kenney WL, Cottle RM, Vecellio DJ, Fisher KG, Leach OK, Kong Q, Wolf ST. *EBioMedicine* 2025;122:106020. [doi:10.1016/j.ebiom.2025.106020](https://doi.org/10.1016/j.ebiom.2025.106020)
- Wolf ST, Cottle RM, Vecellio DJ, Kenney WL. *J Appl Physiol* 2022;132:327. [doi:10.1152/japplphysiol.00737.2021](https://doi.org/10.1152/japplphysiol.00737.2021)
- Vecellio DJ, Wolf ST, Cottle RM, Kenney WL. *J Appl Physiol* 2022;132:340. [doi:10.1152/japplphysiol.00738.2021](https://doi.org/10.1152/japplphysiol.00738.2021)
- Cottle RM, Lichter ZS, Vecellio DJ, Wolf ST, Kenney WL. *J Appl Physiol* 2022;133:1011. [doi:10.1152/japplphysiol.00388.2022](https://doi.org/10.1152/japplphysiol.00388.2022)
- Cottle RM, Fisher KG, et al. *J Appl Physiol* 2024;137. [doi:10.1152/japplphysiol.00117.2024](https://doi.org/10.1152/japplphysiol.00117.2024) (abstract; publisher full text blocked)
- Leach OK et al. *Am J Physiol Regul Integr Comp Physiol* 2024. [doi:10.1152/ajpregu.00114.2024](https://doi.org/10.1152/ajpregu.00114.2024)
- Wolf ST, Vecellio DJ, Kenney WL. *Am J Hum Biol* 2023;35:e23801. [doi:10.1002/ajhb.23801](https://doi.org/10.1002/ajhb.23801)
- Fisher KG, Cottle RM, Kenney WL, Wolf ST. *Int J Exerc Sci* 2023 (**conference abstract**, not full peer review). [digitalcommons.wku.edu](https://digitalcommons.wku.edu/cgi/viewcontent.cgi?article=7973&context=ijesab)

**Indoor heat, night and sleep**
- Meade RD, Akerman AP, Notley SR, Kirby NV, Sigal RJ, Kenny GP. *EHP* 2024;132:27003. [doi:10.1289/EHP13159](https://doi.org/10.1289/EHP13159)
- Meade RD et al. *EHP* 2023. [doi:10.1289/ehp11651](https://doi.org/10.1289/ehp11651)
- O'Connor FK, Meade RD, et al. *J Am Geriatr Soc* 2026;74:200. [doi:10.1111/jgs.70109](https://doi.org/10.1111/jgs.70109)
- Lee BJ et al. *Physiol Rep* 2025;13:e70390. [doi:10.14814/phy2.70390](https://doi.org/10.14814/phy2.70390)
- Baniassadi A, Manor B, Yu W, Travison T, Lipsitz L. *Sci Total Environ* 2023;899:165623. [doi:10.1016/j.scitotenv.2023.165623](https://doi.org/10.1016/j.scitotenv.2023.165623)
- Yan Y, Zhang H, Kang M, Lan L, Wang Z, Lin Y. *Indoor Air* 2022;32:e13159. [doi:10.1111/ina.13159](https://doi.org/10.1111/ina.13159)
- McCormick JJ et al. *APNM* 2024. [doi:10.1139/apnm-2023-0361](https://doi.org/10.1139/apnm-2023-0361)
- Carrillo AE et al. 2024. [doi:10.1139/apnm-2024-0191](https://doi.org/10.1139/apnm-2024-0191)
- Dijk DJ, Duffy JF, Czeisler CA. *Chronobiol Int* 2000;17:285. [doi:10.1081/cbi-100101049](https://doi.org/10.1081/cbi-100101049)
- Huang Q, Komarzynski S, Bolborea M, Finkenstädt B, Lévi FA. *Front Physiol* 2021;12:659973. [doi:10.3389/fphys.2021.659973](https://doi.org/10.3389/fphys.2021.659973)

**Hydration and multi-day**
- Phillips PA, Rolls BJ, Ledingham JG, Forsling ML, Morton JJ, Crowe MJ, Wollner L. *NEJM* 1984;311:753. [doi:10.1056/NEJM198409203111202](https://doi.org/10.1056/NEJM198409203111202)
- Kenney WL, Chiu P. *MSSE* 2001;33:1524 [MC E10]
- Meade RD, Notley SR, D'Souza AW, Dervis S, Boulay P, Sigal RJ, Kenny GP. *Acta Physiol* 2019;226:e13226. [doi:10.1111/apha.13226](https://doi.org/10.1111/apha.13226)
- Meade RD, Notley SR, Rutherford MM, Boulay P, Kenny GP. *J Physiol* 2020;598:5133. [doi:10.1113/JP280132](https://doi.org/10.1113/JP280132)
- Sawka MN, Montain SJ, Latzka WA. USARIEM TN96-2, 1996 (**government technical note**). [apps.dtic.mil/sti/pdfs/ADA307206.pdf](https://apps.dtic.mil/sti/pdfs/ADA307206.pdf)
- Cohen R, Fernie G, Roshan Fekr A. *Nutrients* 2021;13:2092. [doi:10.3390/nu13062092](https://doi.org/10.3390/nu13062092)
- Meade RD, D'Souza AW, Krishen L, Kenny GP. *J Occup Environ Hyg* 2017;14:986. [doi:10.1080/15459624.2017.1365151](https://doi.org/10.1080/15459624.2017.1365151) (**case report, n = 4**)
- Main LC, Moore DC, Lum J, Lee B, Corrigan SL, Aisbett B, Notley SR. *Trials* 2026;27:122. [doi:10.1186/s13063-025-09414-4](https://doi.org/10.1186/s13063-025-09414-4) (**protocol only**)

**Medications**
- Hospers L, Dillon GA, McLachlan AJ, Alexander LM, Kenney WL, Capon A, Ebi KL, Ashworth E, Jay O, Mavros Y. *EClinicalMedicine* 2024;77:102886. [doi:10.1016/j.eclinm.2024.102886](https://doi.org/10.1016/j.eclinm.2024.102886)
- Pescatello LS, Mack GW, Leach CN, Nadel ER. *J Appl Physiol* 1987;62:1448. [doi:10.1152/jappl.1987.62.4.1448](https://doi.org/10.1152/jappl.1987.62.4.1448)
- Kolka MA, Levine L, Cadarette BS, Rock PB, Sawka MN, Pandolf KB. *Aviat Space Environ Med* 1984;55:1107. PMID 6517816
- Trinity JD, Pahnke MD, Lee JF, Coyle EF. *J Appl Physiol* 2010;109:745. [doi:10.1152/japplphysiol.00377.2010](https://doi.org/10.1152/japplphysiol.00377.2010)
- Kwok JS, Chan TY. *Ann Pharmacother* 2005;39:1940. [doi:10.1345/aph.1G130](https://doi.org/10.1345/aph.1G130)
- Brawner CA et al. *Am Heart J* 2004;148:910 [MC E16]; Tanaka H et al. *JACC* 2001;37:153 [MC E15]
- Freund BJ et al. *J Appl Physiol* 1987;63:930 [MC E13]; CDC 2025 [MC E14]; EODY [MC E7]

**Metabolic rate and clothing**
- Herrmann SD et al. "Older Adult Compendium of Physical Activities." *J Sport Health Sci* 2024; values from [pacompendium.com/older-adult-compendium](https://pacompendium.com/older-adult-compendium/)
- Li Y, Liu J, Quan M, et al. *J Phys Act Health* 2022;19:404. [doi:10.1123/jpah.2022-0011](https://doi.org/10.1123/jpah.2022-0011)
- Roberts SB, Dallal GE. *Public Health Nutr* 2005;8:1028. [doi:10.1079/phn2005794](https://doi.org/10.1079/phn2005794) — total energy expenditure falls ≈150 kcal/decade; PAL 1.75 (2nd decade) → 1.28 (9th decade)
- Bouskill LM, Havenith G, Kuklane K, Parsons KC, Withey WR. *AIHA J* 2002;63:262. [doi:10.1080/15428110208984712](https://doi.org/10.1080/15428110208984712)
- ASHRAE 55 met and clo tables as reproduced in `pythermalcomfort.utilities.met_typical_tasks` / `clo_typical_ensembles`
- Notley SR, Akerman AP, Friesen BJ, et al. *Appl Physiol Nutr Metab* 2022;47:711. [doi:10.1139/apnm-2022-0003](https://doi.org/10.1139/apnm-2022-0003)

**Thresholds** — ACSM/Roberts 2023 [MC E1, E2]; OSHA [MC E3]; NIOSH 2016-106 [MC E4]; ACGIH & WHO via Garzón-Villalba et al. *Ann Work Expo Health* 2017;61:621 [MC E5, E6]; EODY [MC E7]; WHO heat-wave public sheet [ALG §6]; NWS heat index and Steadman apparent temperature [ALG §6]; Baccini et al. *Epidemiology* 2008;19:711 [MC E19].

**Reproducibility.** Three scripts in `/home/claude/hg_ai/research/` regenerate every number computed in this pass (as opposed to quoted from a paper):

| Script | Produces |
|---|---|
| `R1_psu_recompute.py` | the PSU HEAT table in §3.1, the three `P_a,crit` fits, and the critical-wet-bulb table |
| `R1_calib_units.py` | the BSA / met / W·m⁻² / mL·kg⁻¹·min⁻¹ conversion table in §1.6 and the first Gagge–Ji run |
| `R1_calib_sweep.py` | the clo × met sensitivity sweep behind §7.4 |

Run each with `python3 -I <script>` from that directory. `R1_psu_recompute.py` reads `/home/claude/hgdata/heat_guardian_train.sqlite` (dataset 3); the other two need `pythermalcomfort` only.
