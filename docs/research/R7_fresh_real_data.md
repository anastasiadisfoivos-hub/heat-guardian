# R7: Fresh real heat data for a new sealed exam (Nov 13 2026)

**Short answer: no.** I found no new dataset that is openly downloadable and has people aged 60 or over in heat with a core-temperature reference. Brighton/Waldock and HeatIN are spent, and nothing open replaces them today. The three best older-adult sources (Ottawa, VU Amsterdam, UT Southwestern) exist and fit well, but each is "on request". So the next sealed older-adult exam has to come from an email, not a download. The fresh open data I did find is all from young adults.

**Where I searched:** the DataCite API, which covers Zenodo, Figshare, Dryad, Mendeley, OSF, Dataverse/Borealis, Yoda and university repositories (about 45 queries). I also searched the Zenodo and Figshare APIs, OSF project titles, PhysioNet topics, and Europe PMC full text (older-adult heat papers since 2016, plus author searches for Kenny, Meade, Notley, Jay, Kenney, Crandall, Gagnon, Flouris, Maxwell and Bach). I read the data-availability statement of each relevant paper. Japanese and Australian older-adult heat studies turned up nothing with open data.

**Not fresh (excluded):** everything in `heat_guardian_train.sqlite` (24 datasets), `candidates.json` and R5. That includes PSU HEAT (3 Zenodo records), Cole hot-water immersion, the Montreal 2024 heatwave data, Phoenix HeatSuite, Wilson OSF and Loughborough sweat maps.

**What I opened:** one 16 KB CSV (OSF 36k7c, see #5). I read its header, its variable list and some HR rows, so that file is "seen by R7". I opened nothing else.

## Ranked top 5

| # | Source | n, ages | Core ref | Other signals | Protocol | Licence / access | Exam value |
|---|---|---|---|---|---|---|---|
| 1 | **Ottawa 3-day simulated heatwave.** Meade, …, Kenny, *Lancet Planet Health* 2026, doi:10.1016/j.lanplh.2026.101517, NCT06633302 | 18, ages 65–85 (median 74), 9 F | **rectal**, continuous | HR (ECG); skin probably | Studio-apartment chamber, 3 days + 2 nights: 34 °C by day, 26 °C at night, 45 % RH, vs a 26 °C control. About 72 h per condition. | No deposit found; Kenny lab terms are a re-analysis plan + signed agreement | **Best possible exam**: daylong, passive, real 74-year-olds, ~2,600 h of rectal data. Add it to R5 email 5.1 as the first ask. |
| 2 | **VU Amsterdam: elderly in uncompensable heat.** EJAP 2024, PMC11322401 (VU + Georgia + HAN) | 31 (16 M / 15 F), 69 ± 5 y, all ≥ 60 | **GI pill** (BodyCap) | HR, skin temperature, sweat, ambient T/RH logged | 39 °C / 25 % RH, then RH +2 % every 5 min; 20 min seated, then ≥ 40 min at 10 W, up to 135 min; stopped at Tgi 39.5 °C | No data statement found. This team publishes raw data on VU Yoda (see #4), so a request is plausible (Hein Daanen). | **Strong second exam**: the core actually climbs (uncompensable), there are 31 people, and the pill gives a continuous reference. |
| 3 | **UT Southwestern (Crandall lab), Dallas** | 18–22 older adults per paper, ages 66–84 (e.g. PMC11444497, PMC12841276, PMC13394156) | rectal or pill (mixed per person) | ECG HR; 6-site skin | 47 °C/15 % and 41 °C/40 %, 3 h, light cycling bouts; cooling arms | The Figshare supplements (25416805, 30698441, 29298224) are only summary tables in docx. Data "on reasonable request". | Good exam if they share. Mixed core methods need per-person handling. |
| 4 | **VU Yoda raw data from two young-adult heat-acclimation studies.** doi:10.48338/VU01-PH2K50 (CALERA sensor vs rectal, CC BY-NC 4.0) and doi:10.48338/VU01-8GXANQ (critical limits and rate of rectal temperature rise, custom licence) | young adults (n not shown on the landing pages) | **rectal**, raw | PH2K50: CALERA skin/core estimate, but heat flux withheld. HR and skin not confirmed. | heat acclimation, progressive heat | Open, but the files sit on `data.yoda.vu.nl:9443`, which this sandbox can't reach and WebFetch is blocked by robots.txt. **A human must download them.** | The best **fresh secondary** exam (young adults, raw rectal). Check the signal list and licence before sealing; NC is fine for a competition. |
| 5 | **Small young-adult sets with core + HR + skin, all CC BY 4.0.** (a) Figshare 25036154: 16 adults, 35 °C vs 25 °C, rest vs cycling, Tcore/Tskin/HR, one 121 KB xlsx. (b) Abertay doi:10.57995/3dw0-d534: 14 adults, 38 °C/30 %, core/skin/HR/power before and after heat acclimation, 2 MB. (c) Mendeley gxbmjzdf35: 48 young men, rest at 32 °C vs 23 °C, core/skin/HR/HRV. | young | core (type not stated; check) | as listed | chamber | Figshare API is reachable. Figshare downloads redirect to a presigned link that answers GET only; it probably works, but I did not test it. For Mendeley and Abertay a browser is safest. | Fresh, but probably summary time points, not per-minute. Only worth it as a sealed **young** exam after checking the resolution. |

## Also seen, lower value

- **OSF 36k7c** (Lakehead fan study, CC0, 16 KB CSV): 10 adults aged **19–39**, room warmed 38 → 47 °C, fan vs no fan, one value per 1 °C step: HR, BP, *change in* core temperature, skin temperature, skin blood flow, sweat rate. There is no absolute core value, and I already looked at its HR rows. Not an exam.
- **Portsmouth** repeated hot-water immersion in older adults (doi:10.17029/a46c1d53…, /40adb0f3…, /6ed6cf5d…; CC BY 4.0): SPSS summary files of 14–17 KB. Water immersion, no time series.
- **OSF 3skxt** "Prep4heat", heat acclimation in older adults with overweight (2026): only a 15 MB analysis HTML, no licence. Data might be embedded in it; not checked. Worth one look by a human.
- **Zenodo 18745170** ElderlyPhysio-v02 (CC BY 4.0, 7.5 MB): Fitbit data from elderly people over 49 days, HR every 1–3 s, wrist and body skin temperature every 1 s. **No core, no heat.** Only useful for sensor-realism or contact work.
- **Borealis CHUSIB** (e-Celsius capsule bench validation, CC0) and **Edmond JZIJSH** (40 h forced desynchrony, BodyCap pill, CC BY 4.0, ~70 GB): not heat, and the second is too big.

## What to do

1. **Email Kenny** (R5 5.1) and name the 3-day heatwave trial (#1) first. Ask for 5-min rectal + HR per participant, heatwave arm only.
2. **Email Daanen** (VU) for #2. Use the same re-analysis-plan template, and ask whether the elderly data can go on Yoda like the young studies.
3. **Email Crandall** (UTSW) for #3, older-adult arms only.
4. **Foivos, in a browser:** download VU PH2K50 and 8GXANQ from their Yoda pages. Hash both before anyone opens them, then decide whether they become a sealed young-adult exam.
5. Until 1–3 reply, any claim about older adults stays limited to the spent Brighton (n = 10) and HeatIN (no core) results.
