# R3 — Indoor heat, routine learning, forecast and alert design (feeds Tomorrow Engine + Guardian Loop)

*Research agent, 12 Nov 2026. Extends `/home/claude/research_notes/Heat Guardian band hardware/algorithms.md` (§3 older-adult physiology, §6 WHO 32/24 °C, §7 Welford baseline) and `verification_algorithms.md` (§5 baseline detector incl. the slow-heatwave FAIL, §7 state machine). Nothing from those files is repeated unless a new number changes it. Every number has a DOI/URL; where a figure is my own derivation from the Bath dataset, it says DERIVED. Simulation-only claims are labelled.*

Files produced alongside this document (all in `/home/claude/hg_ai/research/`):
- `bath_indoor_outdoor_stats.csv` / `.py` — per-house lag, amplitude ratio, night minimum, hours > 24/26 °C from the Bath older-adult homes (dataset 22).
- `bath_indoor_model_fit.csv` / `.py` — per-house fitted time constants and gains for the indoor model in §1.6.
- `openmeteo_sample.json` — one live Open-Meteo forecast for Athens (16 days + 2 past days, all variables we need). `openmeteo_url.txt` — the three URLs tried (one succeeded, two hit 429, see §5).

---

## 1. Indoor heat in the homes of older people

### 1.1 What the measurements say (Mediterranean / Greece)

| Finding | Value | Source |
|---|---|---|
| Athens, 50 low-income non-AC homes, summer 2007 (three heat waves): indoor max | up to **40 °C** | Sakka, Santamouris, Livada, Nicol, Wilson 2012, *Energy and Buildings* 49:69–77, [10.1016/j.enbuild.2012.01.023](https://doi.org/10.1016/j.enbuild.2012.01.023) |
| Same: average indoor **night minimum** | always **> 28 °C** | same |
| Same: indoor warming rate | **+0.2 K/day** early in the wave, **+0.8 K/day** on peak days | same |
| Same: share of the hot period with indoor > 30 °C | **~85 %**; runs of **~216 continuous hours** > 30 °C; six days > 33 °C in many buildings | same |
| Same: mean indoor rise above the normal climatic period | up to **+4.2 K** | same |
| Athens UHI during heat waves (summer 2012, NOA vs 4 coastal stations) | mean UHI **up to +3.5 °C** higher than background during heat waves; **nocturnal UHI +1.5 °C** above normal | Founda & Santamouris 2017, *Sci Rep* 7:10973, [10.1038/s41598-017-11407-6](https://doi.org/10.1038/s41598-017-11407-6) |
| Athens night-time heat stress during heat waves (1960–2017, UTCI + Humidex) | night urban-minus-suburban stress difference up to **6.4 °C UTCI**; minimum (night) thermal stress **+5 °C UTCI** vs non-heat-wave; hours of "no thermal stress" (UTCI < 26 °C) fall from **57 % to 27 %**; heat waves 0.8/yr overall, **1.9/yr in the 2000s** | Katavoutas & Founda 2019, *Atmosphere* 10:483, [10.3390/atmos10090483](https://doi.org/10.3390/atmos10090483) |
| Greater Athens mortality threshold (Thissio station, 2000–2012) | **31.5 °C Tmax** (lag 0–3 mean); 75+: **+5.17 %/°C** (4.65–5.69) | Zafeiratou et al. 2019, *IJERPH* 16:3689, [10.3390/ijerph16193689](https://doi.org/10.3390/ijerph16193689) |

Why it matters for the simulator: an Athens apartment without AC does not cool at night. The whole "night recovery" that WHO's 24 °C night limit assumes (algorithms.md §6) is absent for a week at a time, and the indoor temperature creeps up ~0.2–0.8 K/day while the outdoor forecast may look flat.

### 1.2 Floor, roof, orientation, insulation (what the band must ask once at onboarding)

| Effect | Size | Source |
|---|---|---|
| Each floor higher | **+0.3 °C** living room, **+0.4 °C** bedroom (univariate) | Zuurbier et al. 2021, *Sci Total Environ* 766:144376, [10.1016/j.scitotenv.2020.144376](https://doi.org/10.1016/j.scitotenv.2020.144376) (113 homes of 65+ residents, NL, 2012) |
| Room directly under the roof vs ground floor | **+1.6 °C** living room, **+2.2 °C** bedroom (multivariate) | same |
| East/south/west-facing window area | **+0.2 °C per m²** (bedroom, multivariate) | same |
| Homes built ≥1985 vs pre-1930 | **+0.6 °C** warmer | same |
| Indoor rise over the first 5 days of a warm week | **≈ +3.5 °C** | same |
| Weekly-mean indoor vs weekly-mean outdoor | **+0.9 °C/°C** living room, **+1.1 °C/°C** bedroom (R² 0.36 / 0.34) | same |
| France 2003: lives on the top floor | OR **2.33** (1.33–4.09) univariate | Vandentorren et al. 2006, *Eur J Public Health* 16:583, [10.1093/eurpub/ckl063](https://doi.org/10.1093/eurpub/ckl063) |
| France 2003: bedroom directly under the roof | OR **4.06** (1.26–13.10) multivariate | same |
| France 2003: good insulation | OR **0.21** (0.07–0.64) multivariate | same |
| France 2003: temperature index around the building, per °C (200 m radius) | OR **1.82** (1.27–2.60) | same |
| Chicago 1995: top-floor residence | OR **4.7** | Semenza et al. 1996, *NEJM* 335:84, [10.1056/NEJM199607113350203](https://doi.org/10.1056/NEJM199607113350203) |

Design consequence: a 3-question onboarding (floor / top floor under roof? / windows facing S-W?) shifts the indoor model by 1.5–2.5 °C, which is the same size as the whole difference between "no strain" and "meaningful strain" at 26 vs 31 °C in Meade 2024 (algorithms.md §3).

### 1.3 General indoor–outdoor relationships (temperate reference points)

| Finding | Value | Source |
|---|---|---|
| Boston, 16 homes, daily means, above 12.7 °C outdoor | indoor = β·outdoor, **β = 0.41** (SE 0.02), r = 0.91; daily-min β = 0.49; absolute humidity indoor/outdoor r = 0.96, β = 0.69 | Nguyen, Schwartz, Dockery 2014, *Indoor Air* 24:103, [10.1111/ina.12052](https://doi.org/10.1111/ina.12052) |
| NL older-adult homes: indoor vs outdoor by time of day | outdoor exceeds indoor only **~11:00–23:00** on warm days; indoor is higher than outdoor at night | Zuurbier 2021 (above) |
| NL older adults: per +1 °C indoor | heat annoyance **+33 %**, sleep disturbance **+24 %** | van Loenhout et al. 2016, *Environ Res* 146:27, [10.1016/j.envres.2015.12.012](https://doi.org/10.1016/j.envres.2015.12.012) |

### 1.4 Bath older-adult homes — DERIVED from our own copy of the data

Dataset 22 (`/home/claude/hgdata/raw/22_bath_elderly_homes/`, iButton every 90 min in bedroom + living room, 2017–2018 summers, external hourly weather). I resampled indoor to hourly, aligned to the external series (23 Jul 2017 → 1 Oct 2018, max outdoor 29.4 °C; 30 days with Tmax ≥ 25 °C) and computed per house (`bath_indoor_outdoor_stats.csv`, 76 room-series):

| Statistic (medians across houses; IQR) | Bedroom | Living room |
|---|---|---|
| Lag of indoor behind outdoor (cross-correlation of de-trended hourly anomalies) | **3.5 h** (2–4) | **3 h** (2–4) |
| Diurnal amplitude ratio (indoor daily range / outdoor daily range) | **0.18** (0.11–0.31) | 0.18 |
| Daily-mean slope on a 7-day EWMA of outdoor mean (α = 0.2) | **0.61 °C/°C** (intercept 11.7 °C) | 0.57 (12.6) |
| Hot days (Tout max ≥ 25): indoor max vs outdoor max | **25.9 vs 25.0 °C** | 24.6 vs 25.0 |
| Hot days: indoor min vs outdoor min | **23.2 vs 14.5 °C** (+8.7 °C) | 22.8 vs 14.5 |
| Hot-day mean profile: indoor peak hour vs outdoor peak hour | **19:00 vs 16:00** | 18:00 vs 16:00 |
| Hot-day mean profile: indoor minimum hour | 06:00 (24.6 °C) | 07:00 (23.7) |
| Share of night hours (23–07) > 24 °C, whole summer | 3 % (max house 39 %) | 4 % (max 34 %) |

Honest reading: Bath is a temperate climate and the UK homes are insulated and heated by internal gains, so the **offset** (+9 °C at night) will not transfer to Athens; the **dynamics** (lag 2–4 h, amplitude ratio ~0.2, slow multi-day drift, bedroom warmer and later than the living room) are the transferable part, and they agree with Zuurbier (indoor > outdoor at night, bedroom warmer) and with Sakka (slow 0.2–0.8 K/day creep).

Model fit (`bath_indoor_model_fit.csv`): a first-order lag `T_in' = (off + gain·T_out − T_in)/τ` fitted per house on the longest contiguous run (≥ 15 days, 2-day warm-up excluded) gives **τ = 24–36 h (median 36 h), gain 0.6–0.8, RMSE 0.9 °C** (IQR 0.77–1.13). A two-node version (slow τ_s 48–120 h + fast τ_f 1–6 h, fast gain 0.10–0.20) did not beat it on RMSE in this grid search but is the form that reproduces the 3 h lag and 0.18 diurnal ratio simultaneously (a single τ = 36 h would give lag ≈ 5 h and ratio ≈ 0.10). Persistence (yesterday's same hour) has RMSE ≈ 0.19 °C, i.e. indoor is very smooth: the forecast problem is the multi-day drift, not the hour-to-hour wiggle.

### 1.5 Guidance values (indoor temperature)

| Guidance | Value | Source |
|---|---|---|
| WHO public heat-wave sheet | rooms **< 32 °C day, < 24 °C night**; check at 08–10, 13:00, after 22:00 | already in algorithms.md §6 ([WHO sheet](https://www.who.int/docs/default-source/documents/radiation/phe-info-for-the-public--heatwaves.pdf)) |
| WHO Housing and Health Guidelines 2018 | recommend protecting against high indoor temperatures; **no numeric indoor threshold** is set (evidence judged insufficient); older people named as a priority group | WHO 2018, [who.int news item](https://www.who.int/news/item/26-11-2018-housing-impacts-health-new-who-guidelines-on-housing-and-health) — the chapter page itself was blocked by a CAPTCHA, so this is from the WHO summary page; treat the "no threshold" statement as to-be-rechecked |
| Older adults' sleep (50 people ≥ 65, Boston, ~11,000 person-nights) | sleep efficiency best at **20–25 °C**; **up to −10 %** when bedroom goes from 25 to 30 °C | Baniassadi et al. 2023, *Sci Total Environ*, [10.1016/j.scitotenv.2023.165623](https://doi.org/10.1016/j.scitotenv.2023.165623) (via [ScienceAlert summary](https://www.sciencealert.com/new-study-reveals-the-best-temperature-for-getting-a-good-nights-sleep); the paper itself was not opened) |
| Ottawa HEAT lab: core +0.7 °C at 31 °C, +0.9 °C at 36 °C, 8 h seated | in algorithms.md §3 (Meade 2024) | — |

### 1.6 The indoor model for the simulator (Virtual Elders) and the phone (Tomorrow Engine)

Two-node lumped model, hourly step, inputs from Open-Meteo: `T_out(t)` (temperature_2m), `S(t)` (shortwave_radiation, W/m²), `is_day`, plus a one-time home profile.

```
# Slow node = building mass + air, tracks the outdoor running mean
T_slow[t+1] = T_slow[t] + (1/τ_s) · ( T_out[t] + ΔT_home − T_slow[t] )
# Fast node = ventilation / window path, follows the outdoor diurnal swing with a lag
T_fast[t+1] = T_fast[t] + (1/τ_f) · ( g_f·(T_out[t] − T_slow[t] + ΔT_home) + g_sun·S[t]·κ_orient − T_fast[t] )
T_in[t] = T_slow[t] + T_fast[t]
RH_in: conserve absolute humidity (indoor/outdoor AH ratio 0.69, Nguyen 2014) and recompute RH at T_in.
```

Parameters by building class (priors; the Bath numbers are measured, the Athens numbers are literature-anchored and must be refitted on the pilot's room logger):

| Class | τ_s (h) | g_s offset ΔT_home (°C) | τ_f (h) | g_f | g_sun·κ (°C per 100 W/m², at the hour) | Anchor |
|---|---|---|---|---|---|---|
| A. Insulated temperate (Bath-like) | 36 (24–48) | +4 to +5 on hot days (DERIVED, hot-day mean indoor 25.3 vs outdoor 20.5) | 3 | 0.15 (0.10–0.20) | 0 | Bath fit, this file |
| B. Athens concrete apartment, mid floor, shaded, windows closed by day, open at night | 48–72 | +2 to +3 (Sakka: indoor min > 28 °C when the 2007 nights were ~26–28 °C; Zuurbier: night indoor > outdoor) | 3 | 0.20–0.25 | 0.1 | Sakka 2012, Zuurbier 2021 |
| C. Athens top floor / under roof, S-W windows, no shading | 24–36 | +4 to +5 (B + 1.6–2.2 °C under-roof + 0.2 °C/m² of S-W glass) | 2 | 0.30 | 0.3 | Zuurbier 2021, Vandentorren 2006 |
| D. Ground floor, old masonry, shutters | 72–120 | +1 to +2 | 4–6 | 0.10 | 0 | Zuurbier (pre-1930 −0.6 °C; ground floor −1.6/−2.2 °C) |

Add the **urban offset** before the model when the Open-Meteo grid point is not the dense city: +1.5 °C at night and up to +3.5 °C on heat-wave days for central Athens (Founda & Santamouris 2017). Open-Meteo's cell for (37.98, 23.73) resolved to elevation 99 m at 37.96/23.73, which is central Athens, so the offset should be small there; keep it as a tunable.

Sanity targets the simulator must reproduce: (i) Sakka: indoor night minimum ≥ 28 °C through a 3-day heat wave with outdoor Tmin 26–28 °C; indoor > 30 °C for ≥ 85 % of the hot period; creep 0.2–0.8 K/day. (ii) Bath: lag 2–4 h, amplitude ratio 0.1–0.3, bedroom peak 18–19 h. (iii) Zuurbier: +3.5 °C over 5 warm days; bedroom 0.4–0.6 °C warmer than living room.

What it cannot claim: there is no Athens home dataset in our training set; class B–D parameters are expert priors built from three papers, not fits. Say so on every plot.

---

## 2. Heat-wave mortality mechanics in 65+ (pitch-usable numbers)

| Claim | Number | Source |
|---|---|---|
| Europe summer 2022: heat deaths | **61,672**; Greece **280 per million, 2nd highest** (Italy 295); **~60 % aged 80+**, ~75 % aged 65+; women 145/million vs men 93/million | Ballester et al. 2023, *Nat Med*, [10.1038/s41591-023-02419-z](https://doi.org/10.1038/s41591-023-02419-z) (numbers via [ISGlobal release](https://isglobal.org/en/-/el-calor-record-del-verano-de-2022-causo-mas-de-61-000-muertes-en-europa)) |
| Athens heat wave 23 Jun–2 Jul 2025 (rapid attribution study, Imperial Grantham Institute, 12 cities) | **~175 deaths in Athens**; **88 % of climate-attributable heat deaths were ≥ 65** | [To Vima report](https://www.tovima.com/society/athens-heatwave-claims-175/amp/) — rapid study, not peer-reviewed; label as such |
| BC heat dome 2021 (619 deaths) | **98 % indoors, 67 % aged 70+, 56 % lived alone**, > 60 % had seen a clinician in the previous month; on 29 June 52 % of 911 calls missed the 5-s target | BC Coroners Service review via [CTV](https://bc.ctvnews.ca/here-s-what-a-coroners-review-uncovered-about-b-c-s-2021-heat-dome-deaths-1.5936108) (already in BRIEF; the 911 numbers are new) |
| **Lag structure**: heat effect is immediate | Baccini: "the effect of high apparent temperature is immediate" in both Mediterranean and north-continental cities; the model uses **lag 0–3 days**; cumulative effects decline after the first 5 days, non-significant after ~15 days (Mediterranean) with some later deficit (displacement) | Baccini et al. 2008, *Epidemiology* 19:711, [10.1097/EDE.0b013e318176bfcd](https://doi.org/10.1097/EDE.0b013e318176bfcd) |
| Same, global | "heat effects appeared quickly and did not last long" (vs cold: delayed, many days) | Guo et al. 2014, *Epidemiology* 25:781, [10.1097/EDE.0000000000000165](https://doi.org/10.1097/EDE.0000000000000165) |
| Athens threshold and slope | **32.7 °C max apparent temperature** (32.1–33.3); **+5.54 % natural deaths per °C** above it (4.30–6.80); Mediterranean 75+: **+4.22 %/°C** | Baccini 2008 (already E19 in MEDICAL_CALIBRATION; the 5.54 % Athens-specific figure is new) |
| **Consecutive days** (EuroHEAT, 9 cities, 65+) | heat-wave days raise daily mortality **+21.8 % (Mediterranean)** vs +12.4 % (north); **long-duration waves 1.5–3× the daily effect** of short ones; long + intense ≈ **2×**; duration matters more than intensity; a wave starting < 3 days after the previous has a weaker effect; first wave of the summer larger in some cities; Athens had the highest Tmin of the study (26.4 °C) | D'Ippoliti et al. 2010, *Environ Health* 9:37, [10.1186/1476-069X-9-37](https://doi.org/10.1186/1476-069X-9-37) |
| Consecutive days (43 US cities) | **+3.74 %** mortality per heat-wave day; early-season waves **+5.04 %** vs late-season +2.65 %; hotter and longer waves worse | Anderson & Bell 2011, *EHP* 119:210, via [Tillett EHP summary, 10.1289/ehp.119-a81](https://doi.org/10.1289/ehp.119-a81) |
| Heat-wave definition used by EuroHEAT | ≥ 2 consecutive days with Tapp-max > monthly 90th percentile, **or** Tmin > 90th percentile and Tapp-max > monthly median | D'Ippoliti 2010 |
| **Living alone / not found** (Chicago 1995, 339 cases) | lived alone OR **2.3**; did not leave home daily OR **6.7**; confined to bed OR **8.2**; working AC OR **0.3**; social contacts protective | Semenza 1996 (above) |
| Meta-analysis, 6 case-control studies, 1,065 deaths | confined to bed OR **6.44**; not leaving home daily **3.35**; unable to care for self **2.97**; psychiatric illness **3.61**; cardiovascular **2.48**; working AC **0.23**; visiting cool places **0.34**; **increased social contact 0.40** | Bouchama et al. 2007, *Arch Intern Med* 167:2170, [10.1001/archinte.167.20.ira70009](https://doi.org/10.1001/archinte.167.20.ira70009) |
| France 2003 (315 cases living at home) | confined to bed OR **9.59**; unable to dress/wash **4.03**; did not leave home 3.90 (univariate); dressed lightly **0.22**; cooling device/technique **0.32**. Note: living alone was **protective** here (OR 0.59) — the French sample of people living at home is not Chicago | Vandentorren 2006 (above) |
| Greek EODY guidance | older people are a vulnerable group and **«Να μη μένουν μόνοι τους τις ημέρες του καύσωνα»**; heat-stroke sign body temperature **> 40.5 °C**; medication list (diuretics, β-blockers, antipsychotics, antidepressants, antihistamines, anticholinergics) | [EODY leaflet (municipal mirror)](https://www.e-kilkis.gr/wp-content/uploads/2025/06/ΕΟΔΥ.pdf) |
| Greek Ministry of Health circular Δ1α/Γ.Π.οικ.37556, 10 Jul 2023 | risk groups list (older adults; heart/vessel disease, hypertension, diabetes, lung/kidney/liver disease, mental illness, dementia; diuretics, anticholinergics, psychiatric drugs, insulin); advice for older people: do not leave them alone, ensure fluids, keep rooms cool and ventilated, ask the doctor about doses | [Circular PDF (UoA mirror)](https://hub.uoa.gr/wp-content/uploads/2023/07/Εγκύκλιος_Πρόληψη-επιπτώσεων-από-καύσωνα.pdf) |

Pitch sentence that every number above supports: *"Most heat deaths happen indoors, alone, on the 2nd–4th hot day; the risk is immediate (lag 0–3 days) and doubles when the wave lasts; the two biggest modifiable factors are being reached by someone (social contact OR 0.4) and being moved to a cool place (OR 0.34)."* That is exactly the Guardian Loop's job: detect the un-reached person and trigger the contact.

What it cannot claim: nobody has measured that a wristband reduces heat mortality; the ORs above are observational. "No one found them for days" is documented in reportage, not in a number I could source; do not put a figure on it.

---

## 3. Routine learning and anomaly detection for older adults living alone

### 3.1 What the telecare literature actually does

| Method | Detail | Source |
|---|---|---|
| **Inactivity timeline by time slot** (GE / Cuddihy) | 30-min slots over 24 h; for each slot store min/avg/**max** historical "quiet duration"; alert when the current quiet duration exceeds the historical max **plus a buffer** (example buffers 60/75/**90**/75/60 min across the neighbouring slots, so a late waking near the morning cliff does not trigger); a **sleep window** = slot block with highest average inactivity, buffers widened there; learning needs **10–20 points per slot**, 7–10 days is workable, 30–90 days preferred; away periods (door + no motion) are excluded; readings that caused an alert are excluded so the baseline does not drift insensitive | US 7,091,865 (GE, 2006), [Google Patents](https://patents.google.com/patent/US7091865) |
| Floeck & Litz inactivity-based AAL | same idea with PIR sensors; full paper not retrievable here | cited in [Gerontechnology eHome paper](https://journal.gerontechnology.org/archives/1790-1822-1-PB.pdf) |
| TigerPlace / Skubic 1-D alert | per-feature daily deviations vs a rolling baseline → nurse alerts; 21 residents, 9 months; clinicians rated each alert and the ratings trained a classifier to cut false alerts | Skubic et al. 2015, *IEEE JTEHM*, [10.1109/JTEHM.2015.2421499](https://doi.org/10.1109/JTEHM.2015.2421499) |

### 3.2 Sleep/wake from a wrist accelerometer (so the band knows "asleep" vs "still and awake")

| Algorithm | Equation | Validation | Source |
|---|---|---|---|
| **Cole–Kripke 1992** (1-min epochs) | `D = P·(W−4·A−4 + W−3·A−3 + W−2·A−2 + W−1·A−1 + W0·A0 + W+1·A+1 + W+2·A+2)`; ActiLife form: `SI = 0.001·(106·C[t−4] + 54·C[t−3] + 58·C[t−2] + 76·C[t−1] + 230·C[t] + 74·C[t+1] + 67·C[t+2])`, counts scaled /100 and clipped at 300; **sleep if D (SI) < 1** | 88 % epoch agreement with PSG in the original (young/middle-aged adults) | Cole et al. 1992, *Sleep* 15:461; implementation [actigraph.sleepr](https://rdrr.io/github/dipetkov/actigraph.sleepr/src/R/apply_cole_kripke.R) (its doc and code disagree on the direction; the original paper's rule is D < 1 = sleep) |
| **Sadeh 1994** | `PS = 7.601 − 0.065·MW5 − 1.08·NAT − 0.056·SD6 − 0.703·LOGACT`; MW5 = mean counts over the 11-min window (±5 epochs); NAT = number of epochs in that window with 50 ≤ counts < 100; SD6 = SD over the epoch + 5 previous; LOGACT = ln(counts + 1); **sleep if PS ≥ 0** | 91–93 % minute agreement with PSG (adults and adolescents) | Sadeh, Sharkey, Carskadon 1994, *Sleep* 17:201, [OUP link](https://academic.oup.com/sleep/article/17/3/201/2749453) |
| **HDCZA** (van Hees 2018), no counts needed, raw g only | z-angle = atan(az / √(ax²+ay²)) from 5-s medians; take |Δangle| between 5-s epochs; 5-min rolling median; per noon-to-noon day threshold = **15 × the 10th percentile**; inactive blocks = below threshold for **> 30 min**; merge blocks with gaps **< 60 min**; the longest block = sleep period | vs diary (3,752 people, 25,645 nights): MAE onset 40 min, wake 30 min; vs PSG: accuracy 87–89 %, c-statistic 0.83–0.87 | van Hees et al. 2018, *Sci Rep* 8:12975, [10.1038/s41598-018-31266-z](https://doi.org/10.1038/s41598-018-31266-z) |

HDCZA is the one to put on the band: it needs only the ICM-20649 accelerometer at ≥ 1 Hz, a 5-s median, a 5-min median and a daily percentile, and it is insensitive to band orientation. Cole–Kripke/Sadeh need "counts" whose definition is device-specific (ActiGraph) — reproduce them only if a count emulation is written.

### 3.3 Circadian descriptors (for the weekly "routine health" view and for the sim's ground truth)

Nonparametric rhythm descriptors (Van Someren 1999, as used in the SOF cohort of 1,232 cognitively healthy women, mean age 82.6): **IS** interdaily stability (0–1, higher = same timing every day), **IV** intradaily variability (0–2, higher = fragmented), **RA** relative amplitude = (M10 − L5)/(M10 + L5), **L5** least-active 5 h, **M10** most-active 10 h. Cohort quartile cut-points: **IS 0.73 / 0.80 / 0.85; IV 0.51 / 0.63 / 0.77; RA 0.82 / 0.88 / 0.92; L5 midpoint 01:42–04:39**. Lowest-RA quartile → OR 1.96 for dementia in 5 years; **≥ 5 days** of recording recommended for IS/IV (3 days used, flagged as less accurate). Posner et al. 2021, *Sleep* 44:zsab119, [10.1093/sleep/zsab119](https://doi.org/10.1093/sleep/zsab119).

Use: the simulator should generate elders with IS 0.7–0.9 and IV 0.5–0.8 (that is what "older people have routines" means numerically), and the band's learned profile can be checked against them.

### 3.4 Concrete lightweight method for the band (proposal, built from §3.1–3.3)

Per-minute features already produced by the firmware plan (verification_algorithms.md §10): `a_std` (1-min SD of |a| in g), the z-angle change (HDCZA), on-wrist flag, home/out flag (§4).

1. **Minute class**: `ACTIVE` if a_std > 0.02 g (walking/handling; the 0.002 g "still" criterion in MEDICAL_CALIBRATION §4e is for the Danger behaviour path and is far stricter), `QUIET` otherwise. `ASLEEP` = inside the HDCZA sleep window (computed each noon from the last 24 h). Off-wrist minutes are excluded.
2. **Hourly profile**: for each of 24 hour-slots keep Welford mean/SD of (a) active minutes in the hour, AM[h], and (b) the **longest quiet run that ended in that hour**, Q[h], over the learning days; SD floors 5 min (AM) and 15 min (Q). Memory: 24 × 2 × 12 B = 576 B. Learning days needed: **3 minimum, 7 preferred** (GE: 10–20 points per slot; HDCZA/IS-IV: ≥ 5 days). Stop learning while any alarm is active (same rule as the Welford detector in verification_algorithms §5).
3. **Deviation score** (awake hours only): `z_h = (μ_AM[h] − AM[h]) / max(σ_AM[h], 5)`; concern if z_h ≥ 2 for 2 consecutive hours during the person's own "usually active" hours (μ_AM[h] ≥ 10 min).
4. **Unusual stillness rule (GE-style)**: let `q` = current quiet run (minutes since last ACTIVE minute). Raise **CHECK** when `q > max_Q[h] + B[h]` where max_Q is the learned maximum quiet run for that slot and the buffer **B = 90 min** in the current slot, 60–75 min in the neighbours (GE example values), and B is widened to cover the whole sleep window (so a long night never triggers). Until a slot has ≥ 3 learned days, use a fixed fallback: awake-hours quiet run **> 180 min** → CHECK.
5. **No wake-up rule**: expected wake W = median HDCZA wake time of the last 7 days (fallback 08:00). If still ASLEEP (or QUIET with no ACTIVE minute) at **W + 2 h**, cap **10:00**, raise CHECK; if a heat-day flag is set (max apparent temperature forecast ≥ 32.7 °C, Baccini), use **W + 1 h**. The GE patent's own answer to late sleepers is the widened buffer, not a clock; the 10:00 cap is our design choice, stated as such.
6. **CHECK = tier-1 button check** on the band (vibration + «Είστε καλά;» + button), then escalate per §6.3.
7. **Heat coupling**: when indoor T_in ≥ 31 °C (Meade 2024: meaningful strain) or the Go-cool tier is on, halve B and the 180-min fallback. That ties the routine detector to the thermal state so "napping in a 34 °C room" is treated differently from "napping at 24 °C".

False-alarm arithmetic that must be measured (not guessed): the only free-living wrist datasets in our store are office hours (dataset 16) and lab sessions (15), neither is a multi-day 65+ home record, so the per-week CHECK rate has to come from the pilot's own logs. Design target: ≤ 1 CHECK per wearer-week outside heat days; the verification file §4e gives the only measured analogue (awake adults still ≤ 0.002 g for ≥ 10 min: 0.017–0.08 runs/h) and warns that resting older people are stiller.

### 3.5 Fall detection from a wrist IMU — do not sell it

| Evidence | Numbers | Source |
|---|---|---|
| 13 published algorithms replayed on **29 real-world falls** (waist sensor, older people) | mean sensitivity **57 % ± 27**, specificity **83 % ± 30**; best (Bourke "velocity + impact + posture") **83 % / 97 %** with **≈ 5 false alarms per day** on 24-h recordings | Bagalà et al. 2012, *PLoS ONE* 7:e37062, [10.1371/journal.pone.0037062](https://doi.org/10.1371/journal.pone.0037062) |
| Wrist (left) vs belt, 5 young volunteers, scripted falls; 57-day real-life stream | sensitivity **70 %** (all fast falls, only **40 % of slow falls**), specificity 90 %; impact rule: max−min of |a| in a 1-s window **> 21 m/s² (≈ 2.1 g)** followed by no movement; **9–15 false alarms in 57 days** real life | Gjoreski et al. 2016, *Sensors* 16:800, [10.3390/s16060800](https://doi.org/10.3390/s16060800) |
| Long-term, 16 older residents, 15,500 h, 15 real falls | sensitivity **80 %**; false alarms **0.049/h → 0.025/h** after tuning (≈ **1 per 40 h**, ~0.6/day) | Kangas et al. 2014, *Gerontology* 61:61, [10.1159/000362720](https://doi.org/10.1159/000362720) |
| Commercial wearable, 18 community older adults, 4 months | **1 of 4** worn falls detected; **83 of 84 alarms false**; PPV 0.02; adherence fell mid-study | Chaudhuri et al. 2015, *J Am Geriatr Soc* 63:2415, [10.1111/jgs.13804](https://doi.org/10.1111/jgs.13804) |
| Apple Watch hard-fall flow (for the UX pattern only) | taps + alarm + "I'm OK"; if **immobile ~1 min** → **30-s countdown** with escalating taps → emergency call + text to contacts | [Apple support](https://support.apple.com/en-ie/guide/watch/apd34c409704) |

Verdict: heat collapse in a 65+ wearer is a *slow* fall (sit-to-floor, sliding off a chair), exactly the class detected 40 % of the time at the wrist. Attempting a fall classifier would add ~0.5–5 false family alerts per day on the published numbers and cost the trust that the heat alarm needs. Instead: keep the **impact + post-impact stillness** signature (≥ 2 g peak followed by ≥ 60 s with a_std < 0.002 g) as *one more input to the CHECK path* (button check first, never a direct family call), and say in the pitch "we do not claim fall detection; we detect the stillness that follows."

---

## 4. Home / out inference without GPS

| Signal | Published behaviour | Source |
|---|---|---|
| **Air T/RH step at the wrist** | On warm days outdoor exceeds indoor only ~11:00–23:00 (Zuurbier 2021); Bath hot-day profile: outdoor 26.5 °C at 16:00 vs bedroom 25.8 °C, but outdoor 14 °C at 06:00 vs bedroom 24.6 °C (DERIVED §1.4). So the *sign and size of the step* at a transition depends on the hour: at night a −5…−10 °C step with a sharp RH rise = "went outside", by day a +1…+5 °C step with RH fall = "went outside". Absolute humidity is the more stable indoor/outdoor discriminator (Nguyen 2014: AH indoor = 0.69 × outdoor) | §1.3, §1.4 |
| **Phone-based indoor/outdoor (IODetector)** | light > **2000 lux** = outdoor/semi-outdoor (day), ~50 lux at night; cellular RSS change ≥ **15 dB** within 10 s per tower (drop = entering); magnetic-field variance > 18 while moving = indoor; stateless fusion ~82 % accuracy, HMM (indoor cannot jump straight to outdoor) slightly better, ~10 s warm-up; three classes incl. **semi-outdoor** (balcony, courtyard) | Zhou et al., SenSys 2012, [PDF](https://personal.ntu.edu.sg/limo/papers/SenSys12_IODetector.pdf) |
| **BLE RSSI to the phone** | reference RSSI at 1 m ≈ **−82 dBm**, path-loss exponent ≈ **1.96** (log-distance model); device-to-device spread up to **10 dB**, orientation up to **10 dB**, BLE channel up to **15 dB**, a walking body up to **30 dB**, body shadowing "tens of dB"; distance error ~0.75 m at 1.5 m, ~1.5 m at 3 m in controlled tests; encounter detection 81–96 % only in non-realistic settings | Maccaria & Cagno 2020, [arXiv 2005.10187](https://arxiv.org/pdf/2005.10187) (contact-tracing review) |
| Shortwave radiation on the skin side | not a published home/out method; our two TMP117s will see a sunlit wrist as skin-vs-reference divergence; treat as a weak cue | design note |

Proposal (no published equivalent; label as design): a 3-state HMM on the band — HOME, TRANSIT, OUT — with 1-min emissions: (a) |ΔT_air| and ΔAH over 5 min relative to the last stable indoor value, (b) steps/activity (walking bouts ≥ 3 min), (c) BLE link state to the phone bucketed as *connected strong* (RSSI > −75 dBm), *connected weak*, *lost* (the phone stays at home for most 65+ users; "lost" for > 5 min while walking = OUT), (d) time-of-day prior from the learned hourly profile (errands cluster at the same hours), (e) forecast context: if Open-Meteo says outdoor is 36 °C and the wrist air sensor reads 29 °C with RH matching the indoor AH, the state is HOME regardless of BLE. Transition constraints as in IODetector (HOME→OUT must pass through TRANSIT with ≥ 2 min walking). The only hard number to promise: BLE alone cannot separate "same room" from "same flat" (10–30 dB of uncontrolled variation), so BLE is a *presence* cue, not a range.

What it cannot claim: no accuracy figure exists for this fusion; the simulator must generate it (errand at 11:00, balcony at 20:00, night) and the pilot must label it.

---

## 5. Open-Meteo API — verified by a live call

Docs: [open-meteo.com/en/docs](https://open-meteo.com/en/docs) · terms: [open-meteo.com/en/terms](https://open-meteo.com/en/terms) · archive: [historical-weather-api](https://open-meteo.com/en/docs/historical-weather-api).

**Hourly variables (exact names, all confirmed present in the live JSON):** `temperature_2m` (°C), `relative_humidity_2m` (%), `apparent_temperature` (°C, "feels-like combining wind chill, relative humidity and solar radiation"), **`wet_bulb_temperature_2m` (°C — exists, returned)**, `dew_point_2m`, `shortwave_radiation` (W/m², preceding-hour mean), `wind_speed_10m` (km/h by default; `wind_speed_unit=ms` for m/s), `uv_index`, `is_day` (1/0). Also useful: `direct_radiation`, `cloud_cover`, `vapour_pressure_deficit`, `weather_code`.

**Daily variables:** `temperature_2m_max/min/mean`, `apparent_temperature_max/mean/min`, `uv_index_max`, `shortwave_radiation_sum`, `sunrise`, `sunset`, `daylight_duration`.

**Parameters:** `forecast_days` 0–**16** (default 7); `past_days` 0–**92**; `timezone=Europe%2FAthens` or `auto`; `temperature_unit=celsius` (default); `cell_selection=land` (default); `models=auto` picks the best model (ECMWF IFS 9 km updates every 6 h; ICON 2–11 km every 3 h); `start_date`/`end_date` (yyyy-mm-dd) or `start_hour`/`end_hour`.

**Non-commercial limits (terms page):** **600 calls/min, 5,000/h, 10,000/day, 300,000/month, per IP and per application**; CC BY 4.0 attribution required ("Weather data by Open-Meteo.com"); free tier is for non-commercial use only; commercial use needs an API key and the `customer-` host prefix.

**Archive:** `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=..` — ERA5 (25 km, 5-day delay), ERA5-Land (11 km, 5-day delay), ECMWF IFS 9 km (no delay); same hourly names. For "yesterday" use the forecast endpoint with `past_days`. Related: Historical Forecast API (forecasts as issued, for evaluating Tomorrow Engine's own forecast error) and Previous Runs API (fixed lead times 1–7 days).

**Ready-to-use URL (tested, HTTP 200, 432 hours, cached in `openmeteo_sample.json`):**

```
https://api.open-meteo.com/v1/forecast?latitude=37.98&longitude=23.73
 &hourly=temperature_2m,relative_humidity_2m,apparent_temperature,wet_bulb_temperature_2m,shortwave_radiation,wind_speed_10m,uv_index,dew_point_2m,is_day
 &daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,uv_index_max
 &timezone=Europe%2FAthens&forecast_days=16&past_days=2
```

Sample sanity: `utc_offset_seconds 7200`, grid cell 37.96 N / 23.73 E, elevation 99 m; November values T 9.0–23.1 °C, RH 49–99 %, AT 7.4–23.9 °C, wet-bulb 8.0–19.0 °C, shortwave 0–563 W/m², UV 0–3.9; 3 nulls at the end of the 16-day horizon (handle `null`). `uv_index` is a preceding-hour mean.

**Rate-limit incident (important for the demo):** the second call (archive, July 2024 Athens) returned **429 "Hourly API request limit exceeded"**, and a retry after 30 s plus one forecast call with `past_days=92` returned **429 "Daily API request limit exceeded"**. The limit is per IP, and this workspace's egress IP is shared with other users, so a single call here can fail. On Foivos's Mac it is a non-issue, but Tomorrow Engine must: fetch **once per night** (one call covers 16 days), cache to disk with the fetch time, fall back to the cached forecast (and say "forecast from last night" on the band) when a call fails, and never retry in a loop. No archive sample was obtained; the simulator should use `past_days` on the Mac to pull the summer-2026 Athens hours (one call) rather than the archive endpoint.

---

## 6. Alert design evidence (lead time, wording, haptics, button check, family)

### 6.1 Who the message is for, and why it must not say "you are at risk because you are old"
- 73 interviews, aged 72–94 (London, Norwich): "few respondents considered *themselves* either old or at risk from the effects of heat", though most had a chronic illness; they saw risk in *others*; state intervention was often seen as intrusive, community-based and well-disseminated advice was accepted. Abrahamson et al. 2009, *J Public Health* 31:119, [10.1093/pubmed/fdn102](https://doi.org/10.1093/pubmed/fdn102).
- Consequence: the band's text should name the room and the action, not the person's vulnerability: «Το δωμάτιο έχει 33 °C. Πιείτε ένα ποτήρι νερό.» rather than «Είστε ευάλωτος». The existing Greek reason lines in MEDICAL_CALIBRATION §4g already follow this; keep the explanation (the "why") on the phone screen and the action on the band.

### 6.2 Text size and layout on the 1.69" 240×280 screen
- Systematic review of font size for older adults on mobile devices (12 studies): recommendations run **14–22 pt** for English on tablets (= **42–66 arcmin** of visual angle), 17–20 px for intensive reading on a phone; "bigger is not always better" above ~60 arcmin. Hou, Anicetus, He 2022, *Front Psychol*, [10.3389/fpsyg.2022.931646](https://doi.org/10.3389/fpsyg.2022.931646).
- DERIVED for our screen: 240 px over ≈ 29.5 mm → 0.123 mm/px. At a 35 cm wrist-viewing distance, 42 arcmin = 4.3 mm = **35 px** cap height, 66 arcmin = 6.7 mm = **55 px**. That is **one line of 6–8 Greek characters at 35–40 px**, two lines maximum, one action verb per message («Πιείτε νερό», «Πάτε σε δροσερό μέρος», «Είστε καλά;»). High contrast (white on black on the IPS) — the review found higher contrast improved readability but gives no number.

### 6.3 Vibration that older skin can feel
- Vibrotactile thresholds rise with age, **faster after 65**, and the Pacinian channel (the 200–300 Hz band that coin ERM/LRA motors excite) loses sensitivity fastest of the four channels (ages 10–89). Gescheider et al. 1994, *Somatosens Mot Res* 11:345, [PubMed 7778411](https://pubmed.ncbi.nlm.nih.gov/7778411). At 250 Hz the threshold–age correlation was **0.94–0.96** and **temporal summation decreased with age** (older subjects gain less from longer bursts), [ASA 1994 abstract](https://auditory.org/asamtgs/asa94mit/2aBV/2aBV8.html).
- Consequence (design, derived): drive the DRV2605L at full amplitude; use **long pulses (≥ 300–500 ms) with ≥ 300 ms gaps**, and distinguish tiers by *count and rhythm*, not by subtle amplitude or frequency: Watch = 2 long pulses; Go-cool = 3 long pulses repeated once after 10 s; Danger/CHECK = continuous 1 s on / 1 s off for 30 s (same escalating pattern as Apple's hard-fall flow). Pattern recognition in older adults needs training and repetition (Pomplun 2022 in verification §11; a HAL paper "Haptic patterns and older adults: to repeat or not to repeat?" exists but was blocked, so no number).

### 6.4 Button-check timing before escalating to family
- Published PERS pattern (Apple Watch hard fall): alert → if **immobile ~60 s** → **30-s countdown** with escalating taps and sound → automatic call → text to contacts with location. [Apple support](https://support.apple.com/en-ie/guide/watch/apd34c409704).
- Our tiers are slower events than a fall, so the window can be longer; the verification state machine (§7) uses **15 min no-response at ORANGE → caregiver**. Proposed Guardian Loop sequence: CHECK fires → 30 s of escalating vibration + «Είστε καλά; Πατήστε το κουμπί» → repeat at 2 min and 5 min → **no press by 10 min → family alert** (phone relays; band also shows «Ειδοποιήσαμε την οικογένεια»). For the Danger tier (P(core ≥ 38.5) path) keep the 2-min detection debounce already calibrated in MEDICAL_CALIBRATION and the same 10-min check. A short press = "I am OK" (logs the response time as a routine feature); a long press (≥ 2 s) = HELP, latched (verification §7).

### 6.5 False-alarm tolerance of families
- Real-world fall-device study: **83 of 84 alarms were false**, PPV 0.02, and adherence dropped mid-study (Chaudhuri 2015, above). Long-term fall sensor accepted in a care setting at **~1 false alarm per 40 h** (Kangas 2014). Bagalà's best algorithm ≈ 5/day was judged unusable.
- Design targets (ours, derived): family alerts ≤ 1 false per wearer-month in normal weather; CHECK prompts (which stay on the band and are answered by a button press) ≤ 1 per wearer-week; the Watch tier (vibration only) can be more frequent on heat days because it carries an action that is harmless (drink, move). Report all three rates per hour from the pilot logs, as the BRIEF requires.

### 6.6 Greek public-health wording to reuse (short phrases, verbatim)
From the EODY leaflet and the Ministry circular (sources in §2): «Πίνετε άφθονα υγρά», «Να μη μένουν μόνοι τους τις ημέρες του καύσωνα», «Μην αφήνετε ποτέ σε κλειστό αυτοκίνητο νήπια, ηλικιωμένους, κατοικίδια», heat-stroke signs «αυξημένη θερμοκρασία σώματος (>40.5 °C)», «σύγχυση», «απώλεια αισθήσεων», first-aid «μεταφορά σε δροσερό, αεριζόμενο ή κλιματιζόμενο χώρο», «χλιαρά ντους», «κρύες κομπρέσες στο κεφάλι και στον αυχένα», medicines «συμβουλευτείτε τον γιατρό σας – ίσως χρειαστεί αλλαγή δόσης». Band-length versions (design, consistent with the above): «Πιείτε νερό τώρα» · «Πάτε σε πιο δροσερό δωμάτιο» · «Ανοίξτε παράθυρα το βράδυ» · «Χλιαρό ντους ή κρύα κομπρέσα» · «Είστε καλά; Πατήστε το κουμπί». Lead time: there is no published study of warning lead time for a *personal* heat alert; the public-warning literature (Abrahamson) says the barrier is self-identification, not timing. Tomorrow Engine's "safe hours" plan the evening before is therefore pitched as planning, not warning.

---

## 7. Competition angle — what WAICY gold looks like (sources: [2025 global winners PDF](https://waicy-cdn.wholeren.cn/wp-content/uploads/2025/12/WAICY-2025-Winner-Announcement-Global-3.pdf), [2024 global winners PDF](https://waicy-cdn.wholeren.cn/wp-content/uploads/2024/12/WAICY-2024-Winner-Announcement-Global.pdf), [2025 page / guidebook](https://www.waicy.org/waicy-2025/), [2026 page](https://www.waicy.org/waicy-2026/), [Lumiere summary of the 2023 rules](https://www.lumiere-education.com/post/world-ai-competition-for-youth-waicy-8-tips-to-help-you-win))

1. **Scale:** 2025 had 132,000+ students from 103 countries and 10,000+ projects; 2024 finals drew 53+ countries. One gold per track per division — the AI Showcase high-school gold is the slot.
2. **Scoring is 50 AI / 50 Design-and-Impact.** Special awards: *AI Excellence* = highest AI + technical score; *Impact Excellence* = problem statement + AI ethics + presentation/communication; *Design Excellence* = design + creativity/originality. So the technical half is only half; the problem statement and ethics are scored.
3. **Format is fixed:** 200-word description, 50-word "AI usage" statement, a **3-min presentation video + 3-min demo video** (simulation allowed, narration encouraged, English or subtitled), then live **3 + 3 min + 4 min Q&A**; absent teams lose Q&A credit. Deadline for 2026: 29 Nov, 17:00 ET; finals 4–6 Dec.
4. **2024 high-school AI Showcase gold "Pain Calculator"** (US, single student) took all three excellence awards — a health-measurement tool with a clear single number as output. Health + measurable output is a proven winner.
5. **2025 golds** were "Thrice Upon a Blooming Bloom" (UK, AI Showcase), "frIend hAnd" (Portugal, LLM track, 5-person team), plus art/video golds — titles only are published; no project descriptions, so the bar on *evidence* cannot be read from the winners list. Lumiere's advice page reports presentation ≈ 10 % and "originality and creativity" scored.
6. **Implication for evidence level:** nothing in the rubric rewards a sealed-exam number per se, but "AI Excellence" is judged on technical depth and the Q&A is 4 min of expert questions — the sealed 13-person HTT exam (0.25 °C MAE), the measured false-alarm rates per hour, and "what it cannot claim" are the answers that survive Q&A. Put them on one slide.
7. **Demo style:** a 3-min demo *video* with narration; simulations explicitly allowed. The strongest demo for us is the band on a wrist in a hot room plus the phone showing Tomorrow Engine's plan, intercut with the Virtual Elders simulation replaying a 2007-style Athens week (indoor min > 28 °C) and the band's alarms firing on it.
8. **Ethics is scored (Impact Excellence):** write the medication/fluid-restriction safety logic, the "no fall-detection claim", the family-alert consent, and "no GPS, phone optional" as the ethics section.
9. **Design is scored:** the one-action-per-screen Greek UI, the 35–55 px text, the long-pulse haptics for older skin (§6) are design points with sources — say the source on the slide.
10. **Q&A rehearsal set** (derived from the above): "Why not just a weather app?" (indoor ≠ outdoor: Sakka 28 °C nights; Bath 3 h lag; under-roof +2 °C), "How do you know it works on old people?" (we don't yet; PSU HEAT limits + Kenny 2017 margin + simulation, labelled), "What about false alarms?" (measured per hour on dev data; CHECK ≤ 1/week target), "What happens if the phone dies?" (band works alone).

---

## Open risks (for the manager)

1. **No Athens indoor dataset.** The indoor model's Athens classes are priors from three papers; the Bath fit (τ 24–36 h, gain 0.6–0.8, lag 3 h, ratio 0.18) is the only measured dynamics. A €15 room logger in the pilot home for two weeks of summer would fix this; without it the Tomorrow Engine's indoor curve is a simulation and must be labelled so.
2. **Open-Meteo rate limits are per IP.** Worked once here, then 429 twice. Single nightly fetch + cache + fallback is mandatory; the archive sample for the simulator was not obtained and should be pulled on the Mac.
3. **Routine detector false-alarm rate is unmeasured** and cannot be measured on any dataset we hold; the GE buffer (90 min) and the 10:00 cap are design choices.
4. **Fall detection should not be claimed** (40 % sensitivity for slow falls at the wrist; 83/84 alarms false in the one real-world older-adult study).
5. **The "found days later" statistic** is not sourceable as a number; use the ORs (living alone 2.3, social contact 0.40) instead.
6. Two sources were only reachable through secondary pages (WHO HHG chapter, Baniassadi 2023 sleep paper, HAL haptics paper); they are marked and should be re-opened before any slide quotes them.
