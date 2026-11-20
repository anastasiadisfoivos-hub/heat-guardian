"""T4 — margin table vs ARCHITECTURE §7.2 row 'Medication margins' (diuretic/ACE/ARB 0.10 on DRINK) and the
class-C cool-day case. Run: python3 /home/claude/hg_ai/tests/t4/t4_margins.py"""
import sys
sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import plan, physics, demo
for name, f in [("none", 0), ("beta", physics.MED_BETA_BLOCKER), ("diuretic", physics.MED_DIURETIC),
                ("low_sweat", physics.MED_LOW_SWEAT), ("ACE_ARB", physics.MED_ACE_ARB)]:
    print(name, plan.margins({"age": 78, "med_flags": f}, 1)["total"])
fcc = demo.synthetic_forecast([(18, 24)] * 4, "2026-05-01", rh_lo=50, rh_hi=70)
tw = dict(plan.default_twin(), med_flags=physics.MED_BETA_BLOCKER | physics.MED_LOW_SWEAT)
p = plan.make_plan(fcc, "2026-05-04", "C", twin=tw)
print("classC 24C day meds:", "".join(h["advice"][0] for h in p["hours"]), "t_in max", max(h["t_in"] for h in p["hours"]),
      "core max", max(h["core_indoor"] for h in p["hours"]), "thr", p["details"]["threshold_core"], "extra max", max(h["errand_extra_rise"] for h in p["hours"]))
