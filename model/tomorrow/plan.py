"""Tomorrow's safe-hours plan (ARCHITECTURE §6 plan.py). Physics-based planning — SIMULATION.

For each hour h of the target date:
  (a) indoor trajectory: the wearer's routine at home in the modelled room (indoor.py), 1-min physics;
  (b) counterfactual errand starting at h: 60 min walk, 2.2 met, outdoors at the SUN-EXPOSED apparent
      temperature (t_db = t_r = AT_sun = shade AT + Steadman radiation term, see sun_exposed_at; Open-Meteo's
      hourly apparent_temperature turned out to be a shade value), v = 1 m/s, clo 0.5, then 30 min seated back
      home; the same walk at 22 degC / 50 % is the reference. extra = peak core (hot) - peak core (22 degC).
Advice: OK if extra < 0.15, SHORT if < 0.30, AVOID otherwise (REPORT §8 cut-offs, design choices);
escalated one level if the indoor core in that hour reaches 37.85 - margins in a room >= 26 degC
(v1.2 HG_T_DRINK_WATER and its margins, ARCHITECTURE §7.2).
safe = (advice == OK) AND daylight (is_day == 1): no outdoor advice before sunrise / after sunset.
Flags: heat_day = daily max of the SHADE apparent temperature AT = -2.653 + 0.994 Ta + 0.0153 Td^2 >= 32.7 degC
(the formula and the threshold of Baccini et al. 2008, Epidemiology 19:711; hourly instead of 3-hourly values);
night_heat = modelled bedroom min over the coming night, 23:00 of the date -> 06:59 next day, >= 26 degC
(Meade 2024 limit, ARCHITECTURE §6); wave_day = consecutive heat days ending at the date; margin +0.10 degC
from wave day 2 (D'Ippoliti 2010).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import indoor, physics, advice_gr, ble_frame
from .openmeteo import ATTRIBUTION, Forecast
from .routine import RoutineTemplate, MET_REST, CLO_HOME, CLO_OUT

VERSION = "tomorrow-1"
HEAT_DAY_AT = 32.7          # Baccini et al. 2008, Epidemiology 19:711 (Athens max apparent T threshold)
NIGHT_HEAT_MIN = 26.0       # Meade et al. 2024 (indoor limit for older adults), ARCHITECTURE §6
T_DRINK = 37.85             # v1.2 HG_T_DRINK_WATER (REPORT §5c)
M_OLDER, M_BB, M_LOW_SWEAT, M_DIURETIC, M_WAVE = 0.20, 0.10, 0.10, 0.10, 0.10   # ARCHITECTURE §7.2, §6
EXTRA_OK, EXTRA_SHORT = 0.15, 0.30   # REPORT §8 (design choices)
ERRAND_MET, ERRAND_V, ERRAND_MIN, RECOVER_MIN = 2.2, 1.0, 60, 30
REF_T, REF_RH = 22.0, 50.0
FAN_V, STILL_V, FAN_ON_T = 1.5, 0.1, 28.0   # R1 V7 fan 1.5 m/s; fan used when the room >= 28 degC (design)
ORDER = ["OK", "SHORT", "AVOID"]
ESCALATE_MIN_ROOM_T = 26.0  # Meade 2024 indoor limit (see classify)
STALE_FORECAST_H = 20.0     # cache at least this old (i.e. tonight's call did not happen/failed) -> label, advice line, 0x14 tag 'C' (R3 §5)


def margins(twin: dict, wave_day: int) -> dict:
    flags = int(twin.get("med_flags", 0))
    hyd = flags & (physics.MED_DIURETIC | physics.MED_ACE_ARB)
    m = {"older": M_OLDER if float(twin.get("age", 78)) >= 65 else 0.0,
         "beta_blocker": M_BB if flags & physics.MED_BETA_BLOCKER else 0.0,
         "low_sweat": M_LOW_SWEAT if flags & physics.MED_LOW_SWEAT else 0.0,
         # ARCH §7.2: diuretic/ACE/ARB 0.10 on DRINK only (one 0.10 even if both), labelled hydration proxy
         "diuretic_ace_arb_hydration_proxy": M_DIURETIC if hyd else 0.0,
         "wave_day": M_WAVE if wave_day >= 2 else 0.0}
    m["total"] = round(sum(m.values()), 3)
    return m


def dew_point(ta, rh):
    """Magnus (Alduchov & Eskridge 1996)."""
    ta = np.asarray(ta, float); rh = np.clip(np.asarray(rh, float), 1, 100)
    g = np.log(rh / 100.0) + 17.625 * ta / (243.04 + ta)
    return 243.04 * g / (17.625 - g)


def baccini_at(ta, td):
    """Shade apparent temperature as used by Baccini 2008 (Kalkstein & Valimont form)."""
    return -2.653 + 0.994 * np.asarray(ta, float) + 0.0153 * np.asarray(td, float) ** 2


def daily_at_max(fc: Forecast) -> pd.Series:
    """Daily max of the Baccini shade AT from hourly T and dew point (dew point from RH when absent)."""
    H = fc.hourly
    td = H["dew_point_2m"] if "dew_point_2m" in H else pd.Series(np.nan, index=H.index)
    td = td.where(~td.isna(), pd.Series(dew_point(H["temperature_2m"], H["relative_humidity_2m"]), index=H.index))
    at = pd.Series(baccini_at(H["temperature_2m"], td), index=H.index)
    return at.groupby(H.index.normalize()).max()


SUN_Q_FRACTION = 0.175      # absorbed short-wave per m2 body = 0.7 absorptivity x 0.25 projected-area factor (design)


def sun_exposed_at(at_shade, shortwave, wind_ms):
    """Add Steadman's (1994) radiation term to a SHADE apparent temperature: + 0.70 Q / (ws + 10),
    Q = SUN_Q_FRACTION x global short-wave. Needed because Open-Meteo's apparent_temperature carries almost no
    solar term: on the cached Athens response (n = 429 h) AT - shade-Steadman(T, e, ws) regressed on
    0.70 S/(ws+10) gives a slope of 0.002-0.004 (DERIVED, B4-fix), i.e. it is a shade value."""
    sw = np.nan_to_num(np.asarray(shortwave, float)); w = np.nan_to_num(np.asarray(wind_ms, float), nan=2.0)
    return np.asarray(at_shade, float) + 0.70 * SUN_Q_FRACTION * sw / (np.maximum(w, 0.0) + 10.0)


def wave_count(at_max: pd.Series, date: pd.Timestamp) -> int:
    n, d = 0, date
    while d in at_max.index and at_max[d] >= HEAT_DAY_AT:
        n += 1; d = d - pd.Timedelta(days=1)
    return n


def _interp_minutes(hourly_vals, next_val=None):
    v = np.asarray(hourly_vals, dtype=float)
    nxt = np.r_[v[1:], v[-1] if next_val is None else next_val]
    f = np.arange(60) / 60.0
    return (v[:, None] * (1 - f) + nxt[:, None] * f).ravel()


def simulate_day(person: dict, room_t, room_rh, bed_t, bed_rh, out_at, out_rh, routine: RoutineTemplate,
                 fan_available: bool, errands: bool = True):
    """Run the indoor trajectory and the 24 errand counterfactuals. Hourly arrays of 25 values
    (24 h + the next 00:00 for interpolation). Returns dict of per-minute and per-hour results."""
    met, clo, asleep = routine.minute_plan()
    tr = _interp_minutes(room_t[:24], room_t[24]); hr_ = _interp_minutes(room_rh[:24], room_rh[24])
    tb = _interp_minutes(bed_t[:24], bed_t[24]); hb = _interp_minutes(bed_rh[:24], bed_rh[24])
    at = _interp_minutes(out_at[:24], out_at[24]); ro = _interp_minutes(out_rh[:24], out_rh[24])
    bed = asleep & ((np.arange(1440) < routine.wake_minute) | (np.arange(1440) >= routine.bed_minute))
    t_room = np.where(bed, tb, tr); rh_room = np.where(bed, hb, hr_)
    fan = fan_available & (t_room >= FAN_ON_T)
    model, label = physics.make_model(person, start_minute=0)
    core = np.empty(1440)
    snaps = []
    for i in range(1440):
        if i % 60 == 0:
            snaps.append(physics.snapshot(model))
        env = {"t_db": t_room[i], "t_r": t_room[i], "rh": rh_room[i], "v_air": FAN_V if fan[i] else STILL_V,
               "met": met[i], "clo": clo[i], "drink_mL": 0.0, "minute_of_day": float(i)}
        core[i] = model.step(env)["T_core"]
    res = {"core": core, "t_room": t_room, "fan": fan, "physics_label": label}
    if not errands:
        return res
    extra = np.zeros(24); peak_hot = np.zeros(24); peak_ref = np.zeros(24)
    for h in range(24):
        peaks = []
        for hot in (True, False):
            m = physics.snapshot(snaps[h])
            pk = -np.inf
            for j in range(ERRAND_MIN + RECOVER_MIN):
                i = min(h * 60 + j, 1439)
                mod = float((h * 60 + j) % 1440)
                if j < ERRAND_MIN:
                    t, rh = (at[i], ro[i]) if hot else (REF_T, REF_RH)
                    env = {"t_db": t, "t_r": t, "rh": rh, "v_air": ERRAND_V, "met": ERRAND_MET, "clo": CLO_OUT, "drink_mL": 0.0,
                           "minute_of_day": mod}
                else:
                    env = {"t_db": t_room[i], "t_r": t_room[i], "rh": rh_room[i], "v_air": FAN_V if fan[i] else STILL_V,
                           "met": MET_REST, "clo": CLO_HOME, "drink_mL": 0.0, "minute_of_day": mod}
                pk = max(pk, m.step(env)["T_core"])
            peaks.append(pk)
        peak_hot[h], peak_ref[h] = peaks
        extra[h] = peaks[0] - peaks[1]
    res.update(extra=extra, peak_hot=peak_hot, peak_ref=peak_ref)
    return res


def classify(extra: float, indoor_peak: float, thr: float, t_room: float = 99.0) -> str:
    """B4 brief: OK < 0.15, SHORT < 0.30, AVOID otherwise, escalated one level when the INDOOR
    trajectory itself reaches 37.85 - margins in that hour (the errand peak is reported, not used:
    it contains the indoor baseline and would double-count it).
    Design choice (B4): the escalation needs a warm room, T_in >= 26 degC (Meade 2024 limit), so that
    exertion in a cool room (cooking at 24 degC + the afternoon circadian peak reached 37.65 degC in the
    stub) does not mark a cool day as unsafe; the plan is about heat, not effort."""
    a = 0 if extra < EXTRA_OK else (1 if extra < EXTRA_SHORT else 2)
    if indoor_peak >= thr and t_room >= ESCALATE_MIN_ROOM_T:
        a = min(2, a + 1)
    return ORDER[a]


def window_open_hour(t_out_night, t_in_night, start_h: int = 20):
    """First hour from 20:00 (through 05:00 next day) at which outdoor air is cooler than the room by > 0.5 degC
    (opening helps). Arrays start at 20:00 of the date. Design choice, B4."""
    for k in range(min(len(t_out_night), len(t_in_night))):
        if t_out_night[k] < t_in_night[k] - 0.5:
            return (start_h + k) % 24
    return None


DEFAULT_SLEEP = (23 * 60, 7 * 60)    # manager B4-fix2: 23:00-07:00 when the band has not learned a sleep window


def sleep_window_of(routine: RoutineTemplate) -> tuple[int, int]:
    """[bed, wake) minutes of day: the band's learned window (B5 profile) when available, else 23:00-07:00."""
    if routine.source.startswith("band profile"):
        return int(routine.bed_minute) % 1440, int(routine.wake_minute) % 1440
    return DEFAULT_SLEEP


def morning_close_minute(t_out_next, t_in_next, wake_minute: int):
    """When to tell her to close the windows next morning: 1 h before the outdoor air overtakes the room
    (t_out >= t_in), but never before her wake time. Arrays start at 00:00 of the next day (13 hours)."""
    over = next((h for h in range(len(t_out_next)) if t_out_next[h] >= t_in_next[h]), None)
    m = wake_minute if over is None else max(wake_minute, (over - 1) * 60)
    return int(m)


def make_plan(fc: Forecast, date, home_class: str = "B", twin: dict | None = None,
              routine: RoutineTemplate | None = None, fan_available: bool = False,
              urban_offset=None, wave_day_override: int | None = None, extra_labels=None,
              indoor_state: dict | None = None) -> dict:
    """indoor_state: the previous night's ``details.indoor_state`` ({t, t_slow, t_fast, home_class}); when its
    time is inside the forecast the indoor model starts there (carry-over spin-up instead of a settled start)."""
    twin = dict(twin or default_twin())
    routine = routine or RoutineTemplate.default()
    date = pd.Timestamp(date).normalize()
    H = fc.hourly
    end = date + pd.Timedelta(hours=37)           # date 00:00 .. date+1 12:00 (coming night + next morning)
    hist = H.loc[H.index < end].copy()
    if len(hist.loc[hist.index >= date]) < 24:
        raise ValueError("forecast does not cover %s (it ends %s)" % (date.date(), H.index[-1] if len(H) else "-"))
    hist = hist.interpolate(limit_direction="both")
    spin = "settled start on the first forecast day (no carried-over state)"
    t_slow0 = t_fast0 = None
    start_i = 0
    if indoor_state and indoor_state.get("home_class") == home_class:
        ts = pd.Timestamp(indoor_state["t"])
        if ts in hist.index and ts <= date:
            start_i = int(np.where(hist.index == ts)[0][0])
            t_slow0, t_fast0 = float(indoor_state["t_slow"]), float(indoor_state["t_fast"])
            spin = "carried over from the state of %s" % ts
    at_max = daily_at_max(fc)
    hd_hour = np.array([at_max.get(t.normalize(), np.nan) >= HEAT_DAY_AT for t in hist.index], dtype=float)
    uo = urban_offset if urban_offset is not None else indoor.urban_offset_for(fc.lat, fc.lon)
    ind = indoor.simulate(hist["temperature_2m"].to_numpy(), hist["shortwave_radiation"].to_numpy(),
                          hist["relative_humidity_2m"].to_numpy(), home_class=home_class,
                          is_day=hist["is_day"].to_numpy(), heat_day=hd_hour, urban_offset=uo,
                          t_slow0=t_slow0, t_fast0=t_fast0 or 0.0, start_index=start_i)
    pos = np.where(hist.index >= date)[0]
    sel = pos[:25]
    if len(sel) < 25:                       # last available hour repeated for the 24:00 interpolation point
        sel = np.r_[sel, [sel[-1]] * (25 - len(sel))]
    nsel = pos[23:31]                       # 23:00 of the date .. 06:00 next day
    day = hist.iloc[sel[:24]]
    t_in = ind["t_in"][sel]; t_bed = ind["t_bed"][sel]; rh_in = ind["rh_in"][sel]; rh_bed = ind["rh_bed"][sel]
    at_shade = hist["apparent_temperature"].to_numpy()[sel]; rh_out = hist["relative_humidity_2m"].to_numpy()[sel]
    sw = hist["shortwave_radiation"].to_numpy()[sel]; ws = hist["wind_speed_10m"].to_numpy()[sel] / 3.6
    at = sun_exposed_at(at_shade, sw, ws)
    is_day = hist["is_day"].to_numpy()[sel[:24]] > 0.5
    i0 = pos[0]
    state_out = {"t": str(hist.index[i0]), "t_slow": round(float(ind["t_slow"][i0]), 4),
                 "t_fast": round(float(ind["t_fast"][i0]), 4), "home_class": home_class}

    heat_day = bool(at_max.get(date, np.nan) >= HEAT_DAY_AT)
    wave_day = wave_count(at_max, date) if wave_day_override is None else int(wave_day_override)
    mg = margins(twin, wave_day)
    thr = T_DRINK - mg["total"]
    night = ind["t_bed"][nsel]
    night_note = "23:00-06:59 of the coming night" if len(nsel) == 8 else "night truncated by the forecast end (%d h)" % len(nsel)
    night_heat = bool(len(night) and night.min() >= NIGHT_HEAT_MIN)

    person = physics.person_from_twin(twin)
    sim = simulate_day(person, t_in, rh_in, t_bed, rh_bed, at, rh_out, routine, fan_available)
    core = sim["core"].reshape(24, 60)
    hours = []
    n_err = n_ind = 0
    for h in range(24):
        ip = float(core[h].max())
        ex = round(float(sim["extra"][h]), 3)      # classify on the published (rounded) value: consistent output
        adv = classify(ex, ip, thr, float(sim["t_room"][h * 60:(h + 1) * 60].max()))
        if adv == "AVOID":
            if ex >= EXTRA_SHORT:
                n_err += 1
            else:
                n_ind += 1
        hours.append({"h": h, "t_out": round(float(day["temperature_2m"].iloc[h]), 1),
                      "rh_out": int(round(float(day["relative_humidity_2m"].iloc[h]))),
                      "t_in": round(float(t_in[h]), 1), "rh_in": int(round(float(rh_in[h]))),
                      "core_indoor": round(ip, 2), "errand_extra_rise": ex,
                      "advice": adv, "safe": bool(adv == "OK" and is_day[h])})
    indoor_cross = bool(((sim["core"] >= thr) & (sim["t_room"] >= ESCALATE_MIN_ROOM_T)).any())
    sleep_win = sleep_window_of(routine)
    t_o, t_i = hist["temperature_2m"].to_numpy(), ind["t_in"]
    win_h = window_open_hour(t_o[pos[20:31]], t_i[pos[20:31]])
    close_min = morning_close_minute(t_o[pos[24:37]], t_i[pos[24:37]], sleep_win[1]) if win_h is not None else None
    schedule = []
    stale = fc.source == "cache" and fc.forecast_age_h == fc.forecast_age_h and fc.forecast_age_h >= STALE_FORECAST_H
    lines, kinds = advice_gr.build(hours, heat_day, night_heat,
                                   win_h, indoor_cross, routine.errand_hours, stale=stale,
                                   sleep_window=sleep_win, close_minute=close_min, schedule=schedule)
    labels = ["SIMULATION", "physics-based planning, not a medical prediction",
              "indoor model: literature prior class %s" % home_class if home_class != "A"
              else "indoor model: class A (Bath fit, temperate homes)", sim["physics_label"]]
    if fc.source == "CONSTRUCTED DEMO DAY":
        labels.append("CONSTRUCTED DEMO DAY (not a measured record)")
    if stale:
        labels.append("STALE FORECAST: %.0f h old" % fc.forecast_age_h)
    if fc.fetched_at and "APPROX" in str(fc.raw.get("fetched_at_note", "")).upper():
        labels.append("forecast_age_h from an approximate fetched_at")
    labels += list(extra_labels or [])
    plan = {"version": VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": fc.source,
            "forecast_age_h": None if fc.forecast_age_h != fc.forecast_age_h else fc.forecast_age_h,
            "attribution": ATTRIBUTION,
            "date": str(date.date()), "heat_day": heat_day, "night_heat": night_heat, "wave_day": int(wave_day),
            "hours": hours,
            "safe_hours_bitmap": 0, "advice_gr": lines, "labels": labels,
            "twin_used": twin,
            "home_class": home_class,
            "stale_forecast": bool(stale),
            "details": {"threshold_core": round(thr, 3), "margins": mg, "advice_ids": kinds,
                        "avoid_from_errand": n_err, "avoid_from_indoor_escalation": n_ind,
                        "errand_peak_core": [round(float(x), 3) for x in sim["peak_hot"]],
                        "errand_ref_peak_core": [round(float(x), 3) for x in sim["peak_ref"]],
                        "bedroom_t": [round(float(x), 2) for x in t_bed[:24]],
                        "apparent_t_sun": [round(float(x), 1) for x in at[:24]],
                        "apparent_t": [round(float(x), 1) for x in at_shade[:24]],      # shade (forecast value)
                        "at_max": None if np.isnan(at_max.get(date, np.nan)) else round(float(at_max.get(date)), 2),
                        "at_max_definition": "Baccini 2008 shade AT, daily max of hourly values",
                        "indoor_night_min": round(float(night.min()), 2) if len(night) else None,
                        "indoor_night_window": night_note,
                        "indoor_spinup": spin, "sleep_window": ["%02d:%02d" % divmod(sleep_win[0], 60),
                                                                 "%02d:%02d" % divmod(sleep_win[1], 60)],
                        "advice_schedule": schedule, "indoor_state": state_out,
                        "is_day": [int(x) for x in is_day],
                        "urban_offset": list(uo), "fan_available": bool(fan_available),
                        "routine": routine.to_dict(), "forecast_notes": list(fc.notes),
                        "fetched_at": fc.fetched_at}}
    plan["safe_hours_bitmap"] = ble_frame.safe_bitmap(plan)
    plan["ble"] = {"forecast_chunks_hex": [f.hex() for f in ble_frame.forecast_chunks(plan)],
                   "safe_hours_hex": ble_frame.safe_hours_frame(plan).hex()}
    return plan


def default_twin() -> dict:
    """'Maria, 78' (REPORT §8): population defaults, no medication, sweat prior at the midpoint."""
    return {"name": "Maria (constructed profile)", "age": 78, "sex_m": 0, "mass": 65.0, "height": 1.60,
            "med_flags": 0, "rest_hr": 70.0, "sweat_capacity": 0.44, "k_person": 0.12, "core_offset": 0.0}
