"""T4 — diagnose why errand_extra_rise is ~flat across apparent temperature on the demo day:
re-run the demo with the 30-min home recovery removed (plan.RECOVER_MIN = 0) and compare per-hour extra.
Run: cd /tmp && unshare -rn python3 -W ignore /home/claude/hg_ai/tests/t4/t4_errand_mask.py"""
import json, sys
sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import plan, demo
a = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
plan.RECOVER_MIN = 0
b = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
rows = [(h, a["details"]["apparent_t"][h], a["hours"][h]["t_in"], a["hours"][h]["errand_extra_rise"], b["hours"][h]["errand_extra_rise"],
         a["details"]["errand_ref_peak_core"][h], b["details"]["errand_ref_peak_core"][h]) for h in range(24)]
print("h AT t_in extra(builder) extra(no recovery) refpeak(builder) refpeak(no rec)")
for r in rows: print(*r)
