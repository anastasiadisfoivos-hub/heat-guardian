# tomorrow/cache — Open-Meteo forecast cache

Weather data by Open-Meteo.com (CC BY 4.0, https://open-meteo.com/en/terms). Non-commercial use only.

- `openmeteo_37.98_23.73.json` — central-Athens forecast (grid cell 37.96 N / 23.73 E, 99 m), hourly
  2026-11-10 00:00 → 2026-11-27 23:00 local (3 trailing null hours), daily 2026-11-10 → 11-27.
  **Provenance:** this is R3's live call of 12 Nov 2026 (`research/openmeteo_sample.json`, the R3 §5 URL),
  copied here with `fetched_at = 2026-11-12T00:00:00+00:00` (**approximate** — R3 did not record the time).
  B4's own single permitted live attempt (12 Nov 2026 ≈ 09:24 UTC — corrected: the earlier "11:24 UTC" was local time, UTC+2; same URL) returned **HTTP 429**, the one
  retry 60 s later got **connection reset**; no further calls were made (R3 §5: the workspace IP is shared
  and rate-limited). The code path that produced the fallback is `openmeteo.fetch` (one retry, then cache).
- `plan_live.json` — plan for 2026-11-13 from that cache (`source: "cache"`): all 24 hours OK, no flags.
- `plan_demo_C.json`, `plan_demo_D.json`, `plan_demo_B_stub.json` — the CONSTRUCTED demo day for home
  classes C and D, and class B with the stub physics (for comparison with `../plan.json`).

The cache is refreshed at most once per night (< 20 h old → no call).
