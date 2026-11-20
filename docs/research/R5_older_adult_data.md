# R5 — Real older-adult data hunt (Nov 12 2026)

**Question:** is there any real time series from people aged 60–65+ in heat that we can use?

**Answer in three lines:**
1. **Yes, for the band's own signals at home.** HeatIN (Montreal, summer 2025, CC BY 4.0) gives ~3.5 million watch-minutes of wrist PPG heart rate + near-wrist temperature + motion from 35 watches worn by older social-housing tenants at home, with per-minute room temperature/humidity. Downloaded.
2. **Yes, a small one with true core temperature.** Brighton/Waldock (CC BY-ND 3.0): 10 people aged 65–76, 35 °C / 50 % RH, rectal + HR + 4 skin sites + ambient every 5 min, 3 sessions each (~30 sessions, 390 rectal rows, peak 38.34 °C). Downloaded. It is 5-minute, not per-minute.
3. **No, for the big one.** Nobody has published per-minute core temperature from 65+ in a daylong heat exposure. Kenny (Ottawa), PSU HEAT, Jay (Sydney) all say "on request"; Kenny requires a re-analysis plan and a signed access agreement. Emails are drafted in section 5.

**What I did not do:** no training, no evaluation, no model fitting. I opened files, read headers and first rows, and computed counts and marginal quantiles (listed per source under "What I looked at") so the manager can decide what may still be sealed.

**Disk warning:** the workspace had ~250 MB free when I started (2.7 GB at the end). I filled it once with a partial download and deleted my own two partial files immediately. The two big HeatIN tables are therefore stored as column-subset gzip, not byte-identical originals (details in 2.1).

---

## 1. Summary table

| # | Source | Ages, n | Core | HR | Skin | Sampling | Setting | Licence | Here? | Best use |
|---|---|---|---|---|---|---|---|---|---|---|
| A | **HeatIN 2025**, Montreal | ≥ 50 by protocol (ages not in deposit), 35 watches | oral, 3×/day, **raw only** | wrist PPG | near-wrist (watch) | 1 min | own home, all summer | CC BY 4.0 | yes (slim) | **Real exam for false alarms and routine; sensor-realism calibration** |
| B | **Brighton / Waldock** | 65–76, n = 10 | **rectal** + ear | yes | chest, bicep, quad, calf | 5 min | chamber 35 °C/50 %, 30 min rest + 30 min cycling, ×3 | CC BY-ND 3.0 | yes | **Real older-adult exam for core estimation (small)**; Virtual Elders calibration |
| C | **Montreal June 2024 heatwave** | 53–84 (median 70.5; 21 of 26 ≥ 65) | oral, **corrected** | at BP readings | no | spot (≤ 3/day); room hourly | own home, before/during/after heatwave | CC BY 4.0 | yes | Calibration of Virtual Elders at home; pitch evidence |
| D | PSU HEAT skin wettedness (2 records) | older + middle-aged + young; 55 and 40 older subjects | no (inflection point only) | no | mean skin at inflection | per trial | chamber, critical limits | none stated | yes | Virtual Elders calibration (skin temp, sweat rate at the limit) |
| E | Phoenix HeatSuite 2024 (code zip) | 45–75 (median 59; 9 of 34 ≥ 65) | no | no (in EDI package) | no | 10 min | free-living, record summer | data CC BY 4.0 | exposure only | Realistic personal-temperature day profiles for Tomorrow Engine |
| F | Cole hot-water immersion | 45–64, n = 9 | **rectal** | yes | 4 sites | 5 min | 40 °C bath, 45 min ×2 | CC BY 4.0 | yes | Weak: water not air, mostly middle-aged. Passive-heating HR–core slope check only |
| G | Phoenix HeatSuite physiology (EDI) | same 39 people | oral | wrist PPG | near-wrist | 1 min | free-living | CC BY 4.0 | **no — by hand** | Same use as A, in a much hotter climate |
| H | Kenny lab daylong exposures | 65–85 | rectal | ECG | yes | per-minute | chamber 8–9 h, 26–36 °C; bed rest; fans | request + agreement | no | **The best possible exam.** Email 5.1 |
| I | PSU HEAT raw trials | 65–85 | pill | yes | yes | per-minute | chamber, progressive heat | request | no | Email 5.2 |
| J | Jay lab fan trials | older, incl. heart disease | rectal | yes | yes | per-minute | chamber 38 °C/60 %, 45 °C/15 % | request | no | Email 5.3 |

---

## 2. Downloaded sources

All are under `/home/claude/hgdata/raw/older_<name>/`, each with a `README_SOURCE.md` (licence, provenance, SHA-256). Nothing was added to the SQLite database or to `MANIFEST.csv`.

### 2.1 HeatIN summer 2025 — `older_heatin_montreal/` (108 MB)

- **Record:** Borealis doi:10.5683/SP3/DYSESG. "Replication Data for: HeatIN: Deriving indoor heat-health relationships from remote physiological and behavioural monitoring of older adults living in social housing." Depositor Luc Souilla, Université de Montréal. Protocol: OSF 10.17605/OSF.IO/ZN8QE (PDF saved in the folder). More summers (2026, 2027) are promised in the record.
- **Licence:** CC BY 4.0.
- **Who:** tenants of Montreal social housing (OMHM). Protocol inclusion is **age ≥ 50**, target 40 people per summer. **The deposit has no age or sex table.** In the same team's 2024 cohort from the same housing (source C) the median age was 70.5 and 21 of 26 were ≥ 65, but that is a different year and must not be quoted as HeatIN's ages.
- **Kit:** Bangle.js 2 watch (VC31B optical HR, KX023 accelerometer, BMP280 "near wrist temperature"), room node (SHT85, globe temperature, anemometer, CO2), oral thermistor probe, BP cuff, scale.

**Files and what I measured in them:**

| File | Rows | Content |
|---|---|---|
| `summer_2025_smartwatch_data.SLIM.csv.gz` | 3,483,349 | 1 row per minute per watch: `hr`, `hr_conf`, `baro_temp` (near-wrist °C), `steps`, `acc_min/max/avg/sum`, `charging`. 35 watch IDs; median 124,534 minutes per watch. 99.4 % of gaps are exactly 60 s. |
| `summer_2025_indoor_environment.SLIM.csv.gz` | 3,075,945 | ~1 row per minute per room node (27 nodes): air T/RH (SHT85 and others), globe T, wind speed, CO2. |
| `summer_2025_oral_temperature.csv` | 6,403 | 33 IDs. `temp` plus the raw sample series `measures`. |
| `summer_2025_blood_pressure.csv` | 6,628 | SBP, DBP, HR, quality flags. 34 IDs. |
| `summer_2025_survey.csv` | 56,259 | thermal sensation, satisfaction, preference, sweating, thirst, at-home, indoor/outdoor, fatigue, sleep. |
| `…_mass`, `…_urine`, `…_sleep_analysis`, `…_smartwatch_daily_data`, `…_daily_indoor_environment` | small | daily summaries. |

**Numbers (descriptive only):**
- HR present in 90.8 % of watch rows; 1st / 50th / 99th percentile 56 / 82 / 113 bpm.
- Near-wrist temperature 1st / 50th / 99th percentile: 19.8 / 30.3 / 35.8 °C.
- **31 % of watch rows have `charging = true`** (watch on the charger, not on the wrist). About 2.42 million minutes (~40,000 h) are off-charger. Off-charger is not the same as worn; wear detection is still needed.
- Room air (SHT85): median 28.7 °C, 99th percentile 34.3 °C. About 51,600 node-hours at ≥ 28 °C and 23,300 at ≥ 30 °C.

**Problems to know before using it:**
1. **Not byte-identical originals.** The two big tables (522 MB and 581 MB) were streamed and saved with a column subset, all rows kept. Dropped columns are listed in the folder README. Re-download the originals on the Mac (section 6).
2. **Oral `temp` is a raw probe value** (median 32.0 °C, zero readings ≥ 37.5 °C). It is not usable as a core reference until processed the way the authors did for 2024 (`temp_corrected`). Their processing code is promised but not yet public. **So HeatIN has no usable core reference today.**
3. **No key between watch IDs and room-node IDs** in the deposit. The watch's own `baro_temp` and the survey's at-home answer are available without it, but pairing a person with their room needs the key.
4. Some rows carry a timestamp near 1970 (clock not set).

**Use:**
- **Real older-adult exam for the Guardian Loop without core:** alarms per wearer-day and per hour on real wrist HR + wrist temperature + motion at home in summer. This is the measured false-alarm rate we lack (M16 item 3: the DRINK budget is unverified on real people). Every alarm on these days is "unconfirmed", not "false", because there is no core reference; say that.
- **Routine anomaly detector:** real multi-week daily rhythms of older people (wake time, stillness, steps).
- **Virtual Elders sensor realism:** real distribution of wrist-PPG dropouts, HR confidence, and near-wrist temperature against room temperature. A BMP280 inside a watch case is not our TMP117 on skin; treat it as a relative of our reference sensor, not of the skin sensor.
- **Not for:** training or testing core-temperature estimation.

**What I looked at:** headers, first rows, and the marginal counts/quantiles above, over the whole file. No per-person series were plotted or modelled.

### 2.2 Brighton / Waldock — `older_brighton_adl_waldock/` (0.5 MB)

- **Record:** University of Brighton, doi:10.17033/DATA.00000107 (Maxwell, Hayes, Watt). Paper: Waldock KAM, Hayes M, Watt PW, Maxwell NS. Public Health 2021, doi:10.1016/j.puhe.2021.01.016.
- **Licence:** **CC BY-ND 3.0.** We may use it and cite it. We may not redistribute a modified version, so derived tables stay internal (not in the public zip, not in a public repo).
- **Mismatch to note:** the repository abstract describes a 28-person study at 15/25/35 °C. The file itself is the **10-person cooling study at 35 °C** ("Eastbourne Leisure Trust Heat Stress study data linked to K Waldock PhD"). I report what is in the file.
- **Who:** 10 people, ages 65, 67, 67, 67, 68, 69, 69, 70, 71, 76 (mean 68.9). Height, mass, BSA, skinfolds per person.
- **Protocol per session:** chamber ~35.5 °C, ~51 % RH, WBGT ~30. 30 min seated rest, a cognitive test, 30 min cycling at a personal fixed power, cognitive test. Three sessions per person: Control, Water, Menthol.
- **Signals, every 5 min:** rectal temperature, ear temperature, HR, skin at chest / bicep / quadriceps / calf and mean skin, RPE, thermal sensation, comfort, measured ambient T / RH / WBGT. Also pre/post body mass, sweat patches, 6-minute walk, Douglas-bag VO2 at each power.
- **Size:** sheets `P1`…`P10` hold the per-person sessions; 390 rows carry a rectal value. Rectal range 36.13–38.34 °C.

**Use:**
- **The only real ≥ 65 core + HR + skin time series we hold.** Suitable as a small **real older-adult exam** for Core Sense and v1.2 (HR → core), about 30 sessions × ~65 min.
- **Limits to state with any number from it:** 5-minute sampling; n = 10 healthy active volunteers; one hour per session; light exercise, not daylong passive heat; no wrist skin site; HR from a lab monitor; never reaches a danger-level core temperature.
- **Sealing:** if it is to be a sealed exam, hash the file now (SHA-256 in the folder README) and name it in a decision before anyone models on it. **What I looked at:** the participant sheet, the first ~40 rows of sheet `P1` (two sessions of person 1), the first 24 rows of the `Tre` sheet (all ten people's rectal values for the control session, minutes 0–30 of exercise), and min/max rectal over the whole file. By the brief's rule this makes it "seen by R5", so I recommend treating person 1 as dev and deciding explicitly whether the rest counts as sealed.

### 2.3 Montreal June 2024 heatwave — `older_montreal_heatwave_2024/` (2 MB)

- **Record:** Borealis doi:10.5683/SP3/YOZMYP, CC BY 4.0. HeatSuite kit, 26 older adults in Montreal social housing, one week before, during (June 18–20 2024) and one week after the heatwave. Full summer 2024 "on request" (email 5.4).
- **Who:** 26 people, age 53–84, median 70.5, 21 aged ≥ 65, 21 women. The baseline table has medications count, conditions, AC type, fan use, symptoms in past heat.
- **Tables:** oral temperature, processed and corrected (476 readings, 18 people, 34.5–38.3 °C, labelled before / during / after heatwave); BP + HR (846); room temperature and RH hourly (7,701 rows, 25 homes, median 27.0 °C, max 35.7 °C); daily activity from the watch; thermal sensation/sweating/thirst surveys; body mass; urine colour; outdoor weather.
- **No per-minute watch table** in this deposit.

**Use:** calibration targets for Virtual Elders at home (how much oral temperature, resting HR, BP and body mass shift between normal and heatwave days in real 70-year-olds, against their own room temperature), and a sourced figure for the pitch. Not a time-series exam. **What I looked at:** headers, first rows, counts and ranges.

### 2.4 PSU HEAT skin wettedness — `older_psu_skin_wettedness/` (0.2 MB)

- Zenodo 10.5281/zenodo.14592714 (Fisher, Leach, Cottle, Kenney 2025, Int J Biometeorol doi:10.1007/s00484-025-02986-5) and 10.5281/zenodo.14040987 (older + middle-aged). No licence stated on either record.
- One row per trial at the core-temperature inflection point: Tdb, Pa, **mean skin temperature**, **sweat rate (g/m²/h)**, VO2, net metabolic rate, body mass, BSA, sex. 182 older-adult trials from 55 subjects in the first file; 84 from 40 in the second (overlap between the two files not checked).
- This extends dataset #3 (which has the limits but not skin temperature). **Use:** calibrate Virtual Elders' skin temperature and sweat output at the point where older bodies stop compensating. Summary values, not time series.

### 2.5 Phoenix HeatSuite 2024, code archive — `older_phoenix_heatsuite_2024/` (19 MB zip, unextracted)

- Zenodo 10.5281/zenodo.21049820. Code MIT, data CC BY 4.0 (stated in its README). Paper: Guzman-Echavarria et al., GeoHealth 2026, doi:10.1029/2026GH001914.
- Holds only the **personal temperature exposure**: 102,590 ten-minute rows for 34 people (June 27 – Oct 17 2024, from the wearable, bedroom and main-room sensors), hourly and daily versions, and a daily table with age, sex, AC type, fan use, comorbidity count.
- Ages 45–75, median 59; **only 9 of 34 are ≥ 65.**
- **Use:** realistic "what temperature does this person actually sit in over 24 h" profiles for the Tomorrow Engine and Virtual Elders scenarios. The physiology is in source G.

### 2.6 Cole hot-water immersion — `older_hwi_cole_mendeley/` (1 MB)

- Mendeley Data doi:10.17632/tpvm2t62wr.1, CC BY 4.0. Nine people aged 45–64 (mean 51.6; one person ≥ 60), two 45-minute immersions at 40 °C.
- Rectal, four skin sites, HR every 5 min; rectal reaches about 38.9 °C in the example I saw.
- **Use:** limited. Water immersion is not air heat, skin sensors are under water, and the group is middle-aged. Keep as a passive-heating HR–core check; do not call it older-adult data.

---

## 3. Open but not downloadable from here

**G. Phoenix HeatSuite 2024 physiology — EDI package `knb-lter-cap.730.1`**, doi:10.6073/pasta/b18c58d2805b4caa1393dddc5dbe6d22, CC BY 4.0. 39 free-living people in the record Phoenix summer of 2024, HeatSuite watch (minute-level HR, near-wrist temperature, activity), oral temperature, surveys, on-body and in-home Kestrel sensors, at minute / 10-min / hourly / daily resolution. The EDI server refused every request from this workspace's proxy ("not authorized", including plain search), so the file list and sizes are unverified. Foivos downloads it in a browser: https://portal.edirepository.org/nis/mapbrowse?packageid=knb-lter-cap.730.1

---

## 4. Leads checked and set aside

| Lead | Why not |
|---|---|
| Wilson, Ward, Oates 2026 (Healthcare, doi:10.3390/healthcare14081005), OSF `5acjt` | Older adults, 4-day hot-water acclimation. Open, but a 7 KB SPSS summary file, not time series. |
| Loughborough doi:10.17028/rd.lboro.15164358 (Coull, Havenith: sweat maps, young vs older men, 32 °C) | CC BY 4.0 but only supplement tables/figures. Regional sweat ratios could inform Virtual Elders. |
| PerHeart, Zenodo 17459937 | CC BY 4.0, 27 older heart-failure patients, one month, wrist accelerometer/gyro (2,536 h), steps. 4.5 GB, no HR or temperature. Possible later use for the routine detector. Too big for this disk. |
| PhysioNet wearable-exercise-frailty (catalog #10) | Already catalogued; no heat. |
| Zenodo 18622126 (Kinet, Ghent: coastal vs urban exposure, older adults) | Restricted; request by email to the author named on the record. Not heat-specific. |
| Mendeley `scxkgxpx3k` (Chengdu, older people outdoor comfort) | Survey votes, no physiology. |
| VU Amsterdam doi:10.48338/vu01-8gxanq, vu01-ph2k50 | Open, heat acclimation and Calera sensor, but young adults (not opened; outside this mission). |
| Kenny, PSU, Jay, Flouris, Griffith "Ethos", Taiwan wearable panel | "On request" only. See section 5. |
| NHANES, MESA, UK Biobank | Not checked in this pass. None has core temperature; all need registration or applications. |

**Where I searched:** DataCite (all DOI repositories at once, ~15 queries), Zenodo, Figshare, Dryad, Harvard Dataverse, Borealis, DataverseNL, Mendeley Data, OSF, PhysioNet topics, and Europe PMC full text of ~150 open-access papers on older adults and heat, reading each data-availability statement. GitHub browsing and the EDI and ScholarSphere servers were blocked from this workspace.

---

## 5. Emails to send

**Before sending:**
- Foivos is 17. Each lab will ask who is responsible for the data. Put a teacher or parent in CC and say so in the email; Kenny's lab states it requires a **signed access agreement**, which an adult or the school will have to sign.
- Ask for the smallest thing that answers the question. A lab is far more likely to send 12 people × one condition than "everything".
- Send 5.1 first; it is the highest-value source and likely the slowest.
- Fill the `[brackets]`. Addresses marked "verified" were read from the paper's own correspondence line today.

### 5.1 Kenny lab, Ottawa — the 8–9 h older-adult exposures

- **To:** Dr Glen P. Kenny, [email removed] (verified, corresponding author). Consider CC Dr Robert Meade, [email removed] (verified on his 2025 Nature Communications paper).
- **Their stated terms** (O'Connor et al. 2026, Exp Physiol, doi:10.1113/EP094066): data "available from the corresponding author… All data requests should include a detailed re-analysis plan and will require a signed access agreement."
- **Subject:** Data request with re-analysis plan: older-adult daylong heat exposure (EHP 2024, doi:10.1289/EHP13159)

> Dear Dr Kenny,
>
> My name is Foivos [surname]. I am a student in Athens, Greece. For the WAICY 2026 student AI competition I have built a wristband that tries to warn people over 65 before heat strain becomes dangerous at home. Your trial of daylong indoor overheating in older adults is the reason my alarm thresholds are where they are.
>
> My problem is honest and simple: every real core-temperature time series I have is from young adults. I test my estimator on a sealed hold-out set and report only that number, and today I cannot report any number for older people.
>
> **Request.** De-identified per-minute (or 5-minute) rectal temperature, heart rate and, if recorded, mean skin temperature for the participants of Meade et al., Environ Health Perspect 2024 (22, 26, 31 and 36 °C, 8 h), with age, sex, body mass and condition. Even the 26 °C and 36 °C conditions alone would be enough.
>
> **Re-analysis plan.**
> 1. The file is hashed on arrival and used only as a sealed test set. No model is trained or tuned on it.
> 2. One pre-registered analysis: mean absolute error and bias of my heart-rate-based core-temperature estimate against your rectal temperature, per condition, with bootstrap confidence intervals; and the time at which my "watch" alarm would have fired in each session.
> 3. Results are reported whether good or bad, with your study cited. I will send you the full results before the competition final (Dec 4–6 2026).
> 4. The data stay on one computer, are not redistributed, and are deleted on your request.
>
> I understand you require a signed access agreement. My [teacher / parent], [name, role, email], is in CC and will sign as the responsible adult.
>
> If this is not possible, group-mean curves per condition at 5-minute resolution would still help me calibrate my simulation.
>
> Thank you for reading this, and for the work itself.
>
> Foivos [surname]
> [school], Athens · [email]

### 5.2 PSU HEAT — raw trials behind the critical limits

- **To:** Kat G. Fisher, [email removed] (verified, corresponding author on the 2025 PSU HEAT papers). Ask her to forward to Prof. W. Larry Kenney (his address was not verified here).
- **Their stated terms** (Kenney et al. 2025, eBioMedicine, doi:10.1016/j.ebiom.2025.106020): "Data will be made available upon reasonable request."
- **Subject:** Student request: per-minute trial data from PSU HEAT older adults

> Dear Dr Fisher,
>
> I am a student in Athens building a heat-warning wristband for people over 65 for the WAICY 2026 competition. I already use your open Zenodo files (10197956, 14592714, 14040987) to set and check the environmental limits in my simulator, and I cite them.
>
> Those files give the conditions at the core-temperature inflection point. What I am missing is what the body did on the way there. Could you share, for the older-adult trials only, the de-identified per-minute series of gastrointestinal temperature, heart rate and mean skin temperature, with chamber temperature and humidity, for even a subset (for example the 16 mmHg and 36 °C protocols)?
>
> I would use it only as a sealed test set for a core-temperature estimator: the file is hashed on arrival, nothing is trained on it, one error figure is reported with your papers cited, and I send you the results. I will not redistribute it. My [teacher / parent], [name, email], is in CC as the responsible adult.
>
> Thank you,
> Foivos [surname] · [school], Athens · [email]

### 5.3 Jay lab, Sydney — fans in older adults

- **To:** Prof. Ollie Jay, [email removed] (verified). CC Dr Daniel Gagnon, [email removed] (verified, co-corresponding).
- **Paper:** Chaseling et al., JAMA Netw Open 2025, doi:10.1001/jamanetworkopen.2025.23810. Its data-sharing statement is in "Supplement 3", which I could not open; ask what the terms are.
- **Subject:** Student request: older-adult fan trial time series (JAMA Netw Open 2025)

> Dear Professor Jay,
>
> I am a student in Athens. For the WAICY 2026 competition I built a wristband that warns people over 65 of heat strain at home, and its advice screen ("fan helps / fan does not help at this temperature and humidity") follows your trials.
>
> I have no real core-temperature data from older people to test it on. Would you be able to share, under whatever terms your data-sharing statement sets, the de-identified time series of rectal temperature, heart rate and skin temperature for the older participants in the hot-humid (38 °C, 60 %) control and fan conditions?
>
> It would be a sealed test set only: hashed on arrival, never trained on, one pre-stated error analysis, results sent to you, your trial cited, no redistribution. My [teacher / parent], [name, email], is in CC.
>
> Thank you,
> Foivos [surname] · [school], Athens · [email]

### 5.4 HeatIN / HeatSuite, Montréal — three small things that unlock data we already hold

- **To:** Dr Daniel Gagnon, [email removed] (verified). Also use the "Contact Owner" button on https://doi.org/10.5683/SP3/DYSESG to reach Luc Souilla (his address was not verified here).
- **Subject:** Thank you for the open HeatIN data, and three small questions

> Dear Dr Gagnon, dear Dr Souilla,
>
> I am a student in Athens building a heat-warning wristband for people over 65 (WAICY 2026). Your open HeatIN 2025 dataset on Borealis is the first real wrist data from older people at home in summer that I have found. Thank you for publishing it under CC BY. I will cite it.
>
> Three questions:
> 1. **Ages.** The 2025 deposit has no participant table. Could you share age (or age band) and sex per watch ID, as you did for the June 2024 dataset?
> 2. **Linking.** Is there a key between the watch IDs and the room-node IDs, so I can pair each person with their own room temperature?
> 3. **Oral temperature.** The 2025 `temp` column looks like the raw probe value (median about 32 °C). Could you share the correction you applied for the 2024 `temp_corrected` column, or the corrected 2025 values?
>
> Your 2024 record also says the full summer of 2024 is available on request. If that is possible, I would be grateful.
>
> My use: measuring how often my band's alarms would fire on real older adults at home, and testing a routine-change detector. I will send you the results. My [teacher / parent], [name, email], is in CC.
>
> Thank you,
> Foivos [surname] · [school], Athens · [email]

### 5.5 FAME Lab, University of Thessaly — the Greek option

- **To:** Prof. Andreas D. Flouris, [email removed] (verified).
- This is the only lab on the list in Greece. Ask for advice and a possible visit as much as for data: FAME Lab runs older-adult heat exposures with Ottawa, and a Greek student asking a Greek lab is the most natural request here.
- **Subject:** Μαθητής από την Αθήνα: βραχιόλι προειδοποίησης θερμικής καταπόνησης για άτομα 65+

> Αξιότιμε κύριε Φλουρή,
>
> Ονομάζομαι Φοίβος [επώνυμο], είμαι 17 ετών και μαθητής στην Αθήνα. Για τον διαγωνισμό WAICY 2026 έχω κατασκευάσει ένα βραχιόλι που προσπαθεί να προειδοποιεί έγκαιρα ανθρώπους άνω των 65 για θερμική καταπόνηση μέσα στο σπίτι τους.
>
> Όλα τα πραγματικά δεδομένα θερμοκρασίας πυρήνα που έχω προέρχονται από νέους ενήλικες. Δεν έχω καμία χρονοσειρά από άτομο άνω των 65.
>
> Θα ήθελα να σας ρωτήσω δύο πράγματα:
> 1. Αν υπάρχουν ανωνυμοποιημένες χρονοσειρές (θερμοκρασία ορθού, καρδιακή συχνότητα, θερμοκρασία δέρματος) από ηλικιωμένους εθελοντές σε μελέτες του εργαστηρίου σας που θα μπορούσα να χρησιμοποιήσω αποκλειστικά ως «σφραγισμένο» σύνολο ελέγχου, χωρίς εκπαίδευση πάνω τους και με πλήρη αναφορά στη δουλειά σας.
> 2. Αν θα είχατε δέκα λεπτά για να μου πείτε πού κάνω λάθος. Θα το εκτιμούσα περισσότερο από τα δεδομένα.
>
> Θα σας στείλω όλα τα αποτελέσματα. Ο/Η [καθηγητής / γονέας], [όνομα, email], είναι σε κοινοποίηση.
>
> Με εκτίμηση,
> Φοίβος [επώνυμο] · [σχολείο], Αθήνα · [email]

### 5.6 Brighton — the unseen half of the Waldock data

- **To:** Dr Neil Maxwell, [email removed], and Dr Mark Hayes, [email removed] (both verified on the repository record).
- **Subject:** Thank you for the open elderly heat dataset (doi:10.17033/DATA.00000107), and one question

> Dear Dr Maxwell, dear Dr Hayes,
>
> I am a student in Athens building a heat-warning wristband for people over 65 (WAICY 2026). Your open dataset from Kirsty Waldock's PhD is the only real core-temperature time series from people over 65 that I have been able to find anywhere, and I will cite the Public Health paper.
>
> Two questions:
> 1. The repository abstract describes the 28-participant study at 15, 25 and 35 °C, but the file holds the 10-participant cooling study at 35 °C. Is the per-participant data from the 28-person study available too?
> 2. The licence is CC BY-ND. I plan to keep the file unmodified and report only summary error figures from it. Please tell me if that is not what you intend.
>
> My [teacher / parent], [name, email], is in CC.
>
> Thank you,
> Foivos [surname] · [school], Athens · [email]

### 5.7 Lower priority, same pattern (one short paragraph each)

| Who | Address | What they hold | Stated terms |
|---|---|---|---|
| Dr Gisel Guzman-Echavarria, Arizona State | [email removed] (verified) | Phoenix HeatSuite physiology (source G) | Open on EDI, CC BY 4.0. Email only if the EDI download fails. |
| Prof. Shannon Rutherford, Griffith (Ethos project) | [email removed] (verified) | Home sensors + wearables of older Queenslanders behind a heat early-warning system (npj Digit Med 2025, doi:10.1038/s41746-025-01505-5); bedroom temperature vs HRV (BMC Med 2025, doi:10.1186/s12916-025-04513-0) | On request; the BMC paper asks for a re-analysis plan and signed agreement. |
| Prof. Yue Leon Guo, National Taiwan University | [email removed].tw (verified) | Wearable resting HR of older adults across a summer (JMIR mHealth 2025, doi:10.2196/67721) | On reasonable request. |

---

## 6. For Foivos: commands on the Mac

Full HeatIN originals (1.1 GB):

```
mkdir -p ~/heatguardian_data/heatin && cd ~/heatguardian_data/heatin
```

```
curl -L -o summer_2025_smartwatch_data.csv "https://borealisdata.ca/api/access/datafile/1021618?format=original"
```

```
curl -L -o summer_2025_indoor_environment.csv "https://borealisdata.ca/api/access/datafile/1021617?format=original"
```

Phoenix physiology: open https://portal.edirepository.org/nis/mapbrowse?packageid=knb-lter-cap.730.1 in a browser and download the data entities.

---

## 7. What this changes, and what it does not

**Can now be said, once measured:** "alarm rate on real older adults at home over a real summer" (HeatIN), and "core-temperature error on 10 real people aged 65–76 at 35 °C" (Brighton).

**Still cannot be said:**
- Anything about detecting dangerous core temperature in older people. Brighton peaks at 38.34 °C; HeatIN has no usable core reference.
- Anything about daylong or multi-day passive heat strain in 65+ with a core reference. That needs the Kenny data.
- That HeatIN wearers are "65+". The protocol says ≥ 50 and the ages are not published.
- Anything about our own sensors on older skin. Different watch, different PPG, a case-mounted temperature sensor.

**Recommended next steps for the manager:**
1. Decide and record now whether Brighton is a sealed exam (and which people), given what R5 looked at (2.2).
2. Split HeatIN by watch ID into dev and sealed before anyone runs the Guardian Loop on it.
3. Send emails 5.1, 5.4 and 5.5 this week; the form is due Nov 29.
