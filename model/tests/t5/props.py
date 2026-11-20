#!/usr/bin/env python3
"""T5 property tests + independent tier oracle on random SCRIPTED-core sequences (C build sc_O2).
The oracle recomputes every tier CONDITION from the frozen rule text (FROZEN.txt M11.2/M11.3/M12/M13, ARCH 7.2,
DECISIONS M1.3/M3.1/M5.2) and runs my own v1.2 tier()/ladder; then compares with the C tiers/level minute by minute.
  python3 props.py N   -> out/props.json"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc
F = np.float32
T_DRINK, T_COOL, DELTA, UNC, CAP = F(37.85), F(38.35), F(0.3), F(0.0179999992), F(0.2)
Z_DG, Z_PD = F(-1.45000994), F(-2.19722509)

class Tier:
    """ARCH 7.2 'Hold / debounce' as v1.2 tier(): on after 2 consecutive true minutes; off at the 10th consecutive false minute"""
    def __init__(s): s.run = 0; s.on = 0; s.off = 0
    def step(s, c):
        s.run = s.run + 1 if c else 0
        if s.run >= 2: s.on = 1; s.off = 0
        elif s.on:
            if c: s.off = 0
            else:
                s.off += 1
                if s.off >= 10: s.on = 0
        return s.on

def margins(p):
    m = F(0.2) if p["age"] >= 65 else F(0); md = mc = m; f = p["med_flags"]
    if f & 4: mc = F(mc + F(0.1))
    if f & 1: mc = F(mc + F(0.1))
    return mc

def check(prof, rows, c):
    v = {k: 0 for k in ["tier_mismatch", "level_mismatch", "level_skip", "family_without_check", "family_early", "family_press_in_window",
                        "danger_not_in_check", "help_latch", "help_cleared_wrongly", "ask_haptic", "hour_clean_under_alarm",
                        "calm_learned_under_alarm", "notworn_display", "notworn_tiers_changed"]}
    first = {}
    def bad(k, t, info=None):
        v[k] += 1
        if k not in first: first[k] = (t, info)
    mc = margins(prof)
    drink, cool, danger, coolp = Tier(), Tier(), Tier(), Tier()
    level = 0; hr_bad = 0; strain_run = 0; still_run = 0; cool_min = 0; cool_ack = 0; pd_cool = 0; ring = [F(0)] * 11; ri = 0; pn = 0
    help_id = None; nw = 0
    for t, r in enumerate(rows):
        o = c[t]; prev = c[t - 1] if t else None
        worn = r["worn"]; msd = o["msd"]
        valid = worn == 2 and msd >= 5; thermal_ok = valid and msd >= 20
        ood = F(r["x14"]) > F(0.6) or F(r["x10"]) > F(108)
        core20, v12 = F(r["core20"]), F(r["v12f20"])
        f20a = v12 if (ood and v12 > core20) else core20
        unc = UNC if thermal_ok else F(0)
        heat_ctx = F(r["tair"]) >= F(30) or r["eao"] or ood
        a_base, a_base_n = F(o["a_base"]), o["a_base_n"]
        c_drink = (valid and heat_ctx and v12 >= F(T_DRINK - unc)) or (thermal_ok and a_base_n > 0 and F(f20a - a_base) >= F(DELTA - unc)) \
                  or r["erun"] >= 10 or r["edose"] >= 10            # NN logit_p38 path: cut 1e9 (M5.3) -> never
        low_c = min(F(mc + unc), CAP)
        hr_bad = 0 if r["hr_valid"] else hr_bad + 1
        ring[ri] = f20a; ri = (ri + 1) % 11; old = ring[ri]; pn = min(pn + 1, 11)
        lg = hr_bad <= 5 and valid and F(r["v12z"]) >= Z_DG
        if worn != 0:
            strain_run = strain_run + 1 if (thermal_ok and F(r["strain"]) >= F(7)) else 0
            c_cool = (thermal_ok and f20a >= F(T_COOL - low_c)) or r["edose"] >= 97 or strain_run >= 10
            on_d = drink.step(c_drink); on_c = cool.step(c_cool)
            still_run = still_run + 1 if r["still"] else 0
            pd_cool = pd_cool + 1 if on_c else 0
            slope = pn >= 11 and F(f20a - old) >= F(0)
            pers = on_c and pd_cool >= 20 and slope and (r["ea"] or (thermal_ok and F(r["l385"]) >= F(0)) or (valid and F(r["v12z"]) >= Z_PD))
            wp = coolp.step((thermal_ok and v12 >= F(T_COOL - min(mc, CAP))) or r["edose"] >= 97)
            if wp:
                cool_min += 1
                if r["button"]: cool_ack = 1
            else: cool_min = 0; cool_ack = 0
            beh = wp and cool_min >= 10 and still_run >= 10 and not cool_ack
            danger.step(lg or beh or pers)
            tgt = 3 if danger.on else 2 if cool.on else 1 if drink.on else 0
            level = level + 1 if tgt > level else tgt
        tiers = drink.on | (cool.on << 1) | (danger.on << 2)
        if tiers != o["tiers"]: bad("tier_mismatch", t, (tiers, o["tiers"]))
        if level != o["level"]: bad("level_mismatch", t, (level, o["level"]))
        if prev and o["level"] > prev["level"] + 1: bad("level_skip", t)
        if worn == 0 and prev and (o["tiers"] != prev["tiers"] or o["level"] != prev["level"]): bad("notworn_tiers_changed", t)
        nw = nw + 1 if worn == 0 else 0
        if nw >= 10 and o["state"] not in (3, 4, 8, 5) and o["state"] != 6: bad("notworn_display", t, o["state"])
        # ---- CHECK / family / HELP
        fam_on = o["family_alert"] and not (prev and prev["family_alert"])
        if o["help"] and not (prev and prev["help"]): help_id = o["alarm_id"]
        if fam_on and o["state"] != 8:
            if not o["check_active"]: bad("family_without_check", t)
            else:
                cr = o["check_reason"]; fmin = 5 if (cr & (1 | 2 | 16)) else 10
                if o["check_min"] < fmin: bad("family_early", t, (o["check_min"], cr))
                s = t - o["check_min"]
                # no short press may have been accepted between the CHECK start and the family flag (worn minutes)
                for u in range(max(s + 1, 0), t + 1):
                    if rows[u]["button"] == 1 and rows[u]["worn"] != 0 and c[u - 1]["check_active"] and not c[u - 1]["help"]: bad("family_press_in_window", t, u); break
        if o["level"] == 3 and worn != 0 and not o["help"] and o["snooze"] == 0 and o["state"] != 5 and not o["check_active"]:
            bad("danger_not_in_check", t)
        if (o["state"] == 8) != bool(o["help"]): bad("help_latch", t)
        if prev and prev["help"] and not o["help"]:
            cmd = r["cmd"]
            okc = cmd and cmd[0] == 0x12 and cmd[1] == 3 and (int.from_bytes(cmd[2:6], "little") & 0xFFFF) == (help_id & 0xFFFF)
            if not okc: bad("help_cleared_wrongly", t)
        if o["check_active"] and o["check_min"] in (0, 2, 5) and (not prev or prev["check_min"] != o["check_min"]) and o["haptic"] not in (3, 5):
            bad("ask_haptic", t, o["check_min"])
        # ---- learning frozen (M7.3 (i): COOL / DANGER / CHECK / not worn freeze routine learning; DRINK does not)
        if ((o["tiers"] & 6) or o["check_active"] or worn != 2) and r["mod"] < 1440 and o["hour_clean"]: bad("hour_clean_under_alarm", t)
        if prev and o["a_n"] > prev["a_n"] and (prev["level"] != 0 or not thermal_ok or worn != 2 or r["act"]): bad("calm_learned_under_alarm", t)
    return v, first

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    tot = {}; firsts = {}; mins = 0; fam = 0; dmin = 0; pers_seen = 0
    for i in range(N):
        prof, rows, calm = sc.rand_script(i)
        c = sc.run_c(prof, rows, calm); mins += len(rows)
        v, f = check(prof, rows, c)
        for k, x in v.items():
            tot[k] = tot.get(k, 0) + x
            if x and k not in firsts: firsts[k] = (i, f[k])
        fam += sum(1 for t in range(1, len(c)) if c[t]["family_alert"] and not c[t - 1]["family_alert"])
        dmin += sum(1 for o in c if o["tiers"] & 4)
    r = dict(sequences=N, minutes=mins, family_onsets=fam, danger_tier_minutes=dmin, violations=tot, first=firsts)
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "props.json"), "w"), indent=1, default=str)
    print(json.dumps(r, indent=1, default=str))
