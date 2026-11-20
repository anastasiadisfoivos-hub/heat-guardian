"""Every wearer-facing Greek string fits 2 lines at 35-40 px (u8g2_font_10x20_t_greek x2 = 20 px/char, 224 px
usable -> 11 chars/line) and has an id + source/reason in strings_el.json (manager B4-fix item 5)."""
import json
import os

from tomorrow import advice_gr as A, plan, demo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_all_strings_have_id_source_and_fit():
    with open(os.path.join(HERE, "strings_el.json"), encoding="utf-8") as f:
        S = json.load(f)["strings"]
    assert A.MAX_CHARS == 11
    for s in S:
        assert s["id"] and s["text"] and s["source_or_reason"] and "approved" in s
        if s["kind"] == "retired":
            continue
        txt = s["text"].format(**A.WORST)
        assert A.fits(txt), (s["id"], A.wrap(txt))


def test_emitted_lines_fit_demo_and_cool_day():
    for fc, date in ((demo.demo_forecast(), demo.DEMO_DATE),
                     (demo.synthetic_forecast([(18, 24)] * 4, "2026-05-01", rh_lo=50, rh_hi=70), "2026-05-04")):
        p = plan.make_plan(fc, date, "B")
        for line in p["advice_gr"]:
            assert A.fits(line), A.wrap(line)
        ids = p["details"]["advice_ids"]
        assert all(i in A.STRINGS and A.STRINGS[i]["kind"] != "retired" for i in ids)


def test_retired_strings_never_emitted():
    p = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
    assert A.OPEN_WINDOWS_EVENING not in p["advice_gr"]
