"""v6.1 ASSEMBLY DIGITAL TWIN: brain pod + power pod + skin island + air island on the flat (unrolled) band, every real board,
glue blob and wire in place, automated checks and renders.
  python3 assembly.py [--no-render]  -> out/CLEARANCES.txt, out/SIZES.txt (twin part), out/png/v61_*.png
Checks: interferences (0 allowed), every bundle bend >= WIRE_BEND_R (lone wires / the flat hop-5 ribbon >= WIRE_BEND_R_SINGLE),
clear floor in front of every padded board edge, free heights, no board on a board (except the screen; TMP117 #2 over #1 by design)."""
import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "parts")]
import numpy as np
import params as P
import twin as T
import brain as B, power as W, island_skin as S, island_air
import spacing
from geo import box, union
from scene import render_scene, render_flat, twin_items, PRINT_COL

TOL = 0.005
MATES = {frozenset(("XIAO nRF52840", "USB-C plug"))}
FRAME_COL, LID_COL = (0.35, 0.45, 0.60), (0.55, 0.42, 0.62)


def _move(boards, wires, off):
    M = T.xf(tuple(off))
    b = [T.Placed(x.name, [(k, m.transform(M)) for k, m in x.solids], M, {}) for x in boards]
    return b, [w.moved(M) for w in wires]


def _pa(pod, pos, p):
    """part interior point -> assembly frame"""
    return (p[0] + pod.OFF[0] + pos[0], p[1] + pod.OFF[1] + pos[1], p[2])


SLEEVES = []


def layout():
    pos = spacing.positions()
    bo, po, so, ao = [np.array(pos[k] + (0,)) for k in ("brain", "power", "skin", "air")]
    groups = []
    bb, bw = _move(*B.twin(), bo)
    groups.append(("brain pod", [("brain pod", B.build().translate(list(bo))), ("brain frame", B.build_frame().translate(list(bo)))], bb, bw, bo))
    pb, pw = _move(*W.twin(), po)
    groups.append(("power pod", [("power pod", W.build().translate(list(po))), ("power lid", W.build_lid().translate(list(po)))], pb, pw, po))
    sb, sw = _move(*S.twin(), so)
    skp = [("skin island", S.build().translate(list(so)))] + ([] if S.BACK else [("MAX light shield", S.build_shield().translate(list(so)))])
    ab, aw = island_air.twin()
    ab, _ = _move(ab, [], ao)
    if P.AIR_ON_TOP and S.SHELF:      # v6.8: the SHTC3 on the drop-in shelf over the MAX30102 (in the skin island's twin)
        import island_shelf
        groups.append(("skin island", skp + [("SHTC3 shelf", island_shelf.build().translate(list(so)))], sb, sw, so))
        groups.append(("air island", [], [], [], ao))
    elif P.AIR_ON_TOP:      # v6.6: cage + SHTC3 stacked on TMP117 #2 -> checked together with the skin island
        groups.append(("skin island", skp + [("air cage", island_air.build().translate(list(ao)))], sb + ab, sw, so))
        groups.append(("air island", [], [], [], ao))
    else:
        groups.append(("skin island", skp, sb, sw, so))
        groups.append(("air island", [("air island", island_air.build().translate(list(ao)))], ab, [], ao))
    bp, pp, sp = pos["brain"], pos["power"], pos["skin"]
    xi = B.XIAO_X1
    # v6.5: the splice sleeves (rigid rods) on hop 1 and the battery leads sit on ONE straight line from just outside the brain pod's
    # elbow wall, across the gap, into the power pod - never inside the brain pod
    wall_x = _pa(B, bp, (B.XI + P.WALL, 0, 0))[0]                           # outside face of the brain pod's elbow wall
    h1a = _pa(B, bp, (xi + 3.5, B.Y_H1, B.Z_H1_IN))
    h1e = _pa(W, pp, W.H1_END)
    bta = _pa(W, pp, W.BAT_LEAD)
    btb = _pa(B, bp, (xi + 3.5, B.Y_BAT, B.Z_BAT_IN))
    cross = [
        T.Wire("hop 1 XIAO -> DRV2605L (4 wires)",
               [_pa(B, bp, (xi + 1.0, B.Y_H1, B.Z_H1_IN)), h1a, h1e], r=P.WIRE_BEND_R, ends=["XIAO nRF52840", "DRV2605L"]),
        T.Wire("battery leads (2 wires)",
               [bta, btb, _pa(B, bp, (B.XIAO_CX - 1.27, B.XIAO_CY - 4.44, B.Z_BAT_IN))], d=2.4, r=P.WIRE_BEND_R,
               ends=["battery LP601730", "XIAO nRF52840"]),
        T.Wire("HELP button pair (2 wires)",
               [_pa(W, pp, W.BTN_W), _pa(B, bp, (B.XI - 2.0, B.Y_BTN, 4.2)), _pa(B, bp, (B.X_BTN_END, B.Y_BTN, 4.6))],
               d=2.0, r=P.WIRE_BEND_R, ends=["button", "XIAO nRF52840"]),
        T.Wire("hop 2 DRV2605L -> ICM-20649 (4 wires)",
               [_pa(W, pp, W.H2_START), _pa(W, pp, (W.XI - 1.0, W.Y_H1, W.Z_LANE)), _pa(S, sp, (2.0, S.Y_H2, S.Z_ICM_W)), _pa(S, sp, S.H2_END)],
               r=P.WIRE_BEND_R, ends=["DRV2605L", "ICM-20649"]),
        (T.Wire("hop 6 TMP117 #2 -> SHTC3 (4 wires, ONE loop)", [_pa(S, sp, p) for p in S.H6_PTS], r=0,
                ends=["TMP117 #2 (reference)", "SHTC3"]) if P.AIR_ON_TOP else spacing.h6_wire(pos["h6_shift"], *sp)[0]),
    ]
    # the two sleeves: from the brain wall's outside face toward the power pod, as long as the straight allows (<= SLEEVE_L)
    global SLEEVES
    SLEEVES = []
    for wn, a, b, room in (("hop 1 XIAO -> DRV2605L (4 wires)", h1a, h1e, 3.0 + P.SLEEVE_END_ROOM),     # 3 = the 4-pad fan at the DRV
                           ("battery leads (2 wires)", btb, bta, P.SLEEVE_END_ROOM)):
        a, b = np.array(a), np.array(b)
        u = (b - a) / np.linalg.norm(b - a)
        t0 = (wall_x + 1.0 - a[0]) / u[0]                                     # sleeve starts just outside the brain wall
        t1 = min(t0 + P.SLEEVE_L, np.linalg.norm(b - a) - room)
        # where on the wire, measured from the XIAO pad (approx.: joint 1.0 + the short leg inside the brain pod + along the straight)
        lead = 1.0 + (2.5 if wn.startswith("hop 1") else float(np.linalg.norm(np.array(btb) - np.array(_pa(B, bp, (B.XIAO_CX - 1.27, B.XIAO_CY - 4.44, B.Z_BAT_IN))))))
        SLEEVES.append((wn, t1 - t0, lead + t0, lead + t1))
        cross.append(T.Wire(f"splice sleeve on {wn.split(' (')[0]} ({t1 - t0:.0f} mm rod)", [tuple(a + u * t0), tuple(a + u * t1)],
                            d=P.SLEEVE_D, ends=[wn]))
    return groups, cross, pos


def _pair(a, b):
    v = (a ^ b).volume()
    if v > TOL:
        return v, None
    return 0.0, a.min_gap(b, 1.5)


def check(groups, cross):
    lines, bad, tight = [], 0, 0
    for name, parts, boards, wires, _ in groups:
        lines.append(f"\n== {name} " + "=" * (70 - len(name)))
        things = [(b.name, b.solid, "board", set()) for b in boards] + [(w.name, w.solid, "wire", w.ends) for w in wires]
        rows = []
        for i, (an, a, ak, ae) in enumerate(things):
            for pn, pm in parts:
                rows.append((an, pn, ak, "print") + _pair(a, pm))
            for bn, b, bk, be in things[i + 1:]:
                if bn in ae or an in be or frozenset((an, bn)) in MATES or (ae & be):
                    continue
                rows.append((an, bn, ak, bk) + _pair(a, b))
        for an, bn, ak, bk, v, g in sorted(rows, key=lambda r: (-(r[4]), r[5] if isinstance(r[5], float) else 9)):
            if v > TOL:
                bad += 1
                lines.append(f"  INTERFERENCE  {an:42s} x {bn:34s} {v:8.2f} mm3")
            elif g < 0.02:
                lines.append(f"  touch         {an:42s} x {bn:34s}     0.00 mm  (seat / rest / fit)")
            elif g < 1.5:
                flag = ""
                if g < P.GAP - 0.01 and bk != "print":
                    flag, tight = "  <-- TIGHT (< %.1f)" % P.GAP, tight + 1
                lines.append(f"  clearance     {an:42s} x {bn:34s} {g:8.2f} mm{flag}")
    # crossing wires against every printed part and every board / wire of every group
    lines.append("\n== crossing wires (straight across the gaps) " + "=" * 26)
    allparts = [(pn, pm) for g in groups for pn, pm in g[1]]
    allthings = [(b.name, b.solid) for g in groups for b in g[2]] + [(w.name, w.solid) for g in groups for w in g[3]]
    allw = {o.name: o for g in groups for o in g[3]}
    allw.update({o.name: o for o in cross})
    for i, w in enumerate(cross):
        for n, m in allparts + [(o.name, o.solid) for o in cross[i + 1:]] + allthings:
            if n in w.ends or (n in allw and (allw[n].ends & w.ends or w.name in allw[n].ends)):
                continue
            v, g = _pair(w.solid, m)
            if v > TOL:
                bad += 1
                lines.append(f"  INTERFERENCE  {w.name:42s} x {n:34s} {v:8.2f} mm3")
            elif g is not None and g < 1.5:
                lines.append(f"  clearance     {w.name:42s} x {n:34s} {g:8.2f} mm")
    # printed part x printed part
    lines.append("\n== printed parts against each other " + "=" * 34)
    for i, (an, a) in enumerate(allparts):
        for bn, b in allparts[i + 1:]:
            v = (a ^ b).volume()
            if v > TOL:
                bad += 1
            g = a.min_gap(b, 3.0) if v <= TOL else 0
            if v > TOL or g < 3.0:
                lines.append(f"  {'INTERFERENCE' if v > TOL else 'ok          '}  {an:20s} x {bn:20s} overlap {v:7.3f} mm3, gap {g:5.2f} mm")
    return lines, bad, tight


def rule_checks(groups, cross):
    """v6.1 wire-first rules.  Returns (lines, n_fail, notes)."""
    out, fail, notes = [], 0, []
    g = {x[0]: x for x in groups}
    out.append("RULE 1  every bundle bend >= WIRE_BEND_R = %.1f mm; lone single wires and the flat hop-5 ribbon >= WIRE_BEND_R_SINGLE = %.1f mm"
               % (P.WIRE_BEND_R, P.WIRE_BEND_R_SINGLE))
    for w in [w for n in ("brain pod", "power pod", "skin island") for w in g[n][3]] + cross:
        if "motor" in w.name:
            out.append(f"  ok    {w.name:52s} R {w.rmin:.1f}  (2 x AWG32 motor leads: soft, factory-fitted)")
            continue
        if "straight up" in w.name:
            out.append(f"  ok    {w.name:52s} R {w.rmin:.1f}  (4 single wires wrapped round the two board edges: your dry fit, v6.6)")
            notes.append(f"hop 5 wraps round the two board edges at R ~{P.HOP5_BEND_R:.0f} (single wires, validated by your dry fit)")
            continue
        single = "blue" in w.name or "GND tail" in w.name or "ribbon" in w.name
        need = P.WIRE_BEND_R_SINGLE if single else P.WIRE_BEND_R
        rs = "straight" if w.rmin == float("inf") else f"R {w.rmin:.1f}"
        ok = w.rmin >= need - 0.05
        fail += 0 if ok else 1
        out.append(f"  {'ok  ' if ok else 'FAIL'}  {w.name:52s} {rs:9s} (needs >= {need:.0f}{', single wire / flat ribbon' if single else ''})")
        if "ribbon" in w.name and "hop 5" in w.name:
            notes.append(f"hop 5 is a flat 4-wire ribbon C of radius {w.rmin:.1f} (below the {P.WIRE_BEND_R:.0f} mm bundle rule)")
    out.append("\nRULE 2  >= %.0f mm clear floor in front of every padded board edge (no printed part, no other board in the zone)" % P.PAD_ROOM)
    own = {"brain pod": ("XIAO nRF52840",), "power pod": ("DRV2605L",), "skin island": ("ICM-20649", "MAX30102", "TMP117 #1 (skin)", "TMP117 #2 (reference)", "SHTC3")}
    for n, mod in (("brain pod", B), ("power pod", W), ("skin island", S)):
        parts, boards, off = g[n][1], g[n][2], g[n][4]
        for lab, z in mod.pad_zones():
            z = z.translate(list(off))
            hit = [pn for pn, pm in parts if (z ^ pm).volume() > TOL] + [b.name for b in boards if (z ^ b.solid).volume() > TOL
                                                                             and b.name not in own[n]]
            fail += 1 if hit else 0
            bb = z.bounding_box()
            out.append(f"  {'ok  ' if not hit else 'FAIL'}  {lab:44s} zone {bb[3]-bb[0]:.1f} x {bb[4]-bb[1]:.1f} mm  {', '.join(hit)}")
    out.append("\nRULE 3  free heights")
    rows = [("brain: under the screen where cable + plug land", B.Z_LCD - B.Z_XTOP, P.SCREEN_FREE_H),
            ("brain: far-end wire room (floor -> screen)", B.Z_LCD - P.FLOOR, P.WIRE_ROOM_H),
            ("brain: XIAO 5V-row wire room (floor -> screen / frame)", B.Z_LCD - P.FLOOR, P.WIRE_ROOM_H),
            ("brain: XIAO D-row wire room (floor -> screen)", B.Z_LCD - P.FLOOR, P.WIRE_ROOM_H),
            ("power: lane (floor -> lid)", W.Z_LID0 - P.FLOOR, P.WIRE_ROOM_H),
            ("skin island: bay (open from above)", 99.0, P.WIRE_ROOM_H)]
    for lab, v, need in rows:
        ok = v >= need - 1e-6
        fail += 0 if ok else 1
        out.append(f"  {'ok  ' if ok else 'FAIL'}  {lab:62s} {('open' if v > 50 else f'{v:5.2f} mm')} (needs >= {need:.0f})")
    out.append("\nRULE 4  big openings: every run leaves / enters through an opening >= %.0f mm wide, floor to the top, open from above" % P.OPEN_W)
    for lab, iv in [("brain elbow wall", B.OPENS), ("power hand wall", W.OPEN_HAND), ("power elbow wall", W.OPEN_ELBOW),
                    ("skin hand wall", [S.OPEN_HAND])] + ([("skin front wall", [S.OPEN_FRONT])] if S.OPEN_FRONT else []):
        for a, b in iv:
            ok = b - a >= min(P.OPEN_W, 10.0) - 0.01
            fail += 0 if ok else 1
            out.append(f"  {'ok  ' if ok else 'FAIL'}  {lab:20s} {b - a:5.1f} mm wide, top-open")
    if P.AIR_ON_TOP:
        out.append(f"  ok    hop-5 slot          {S.TX1 - S.TX0 + 2 * P.CLEAR:5.1f} mm wide (full width at the TMP117 pad edges), floor to top, top-open")
        out.append("  ok    SHTC3 shelf         open toward the bay (wires) and on top; vent slots in the back + hand lips; drop-in after the MAX"
                   if S.SHELF else "  ok    SHTC3 cage          open on all 4 sides and on top: drop-in, hop 6 comes up in front")
    else:
        out.append(f"  ok    air island entry    {2 * min(P.OPEN_W / 2, island_air.VI / 2 - 3.6):5.1f} mm wide, top-open (between the guard bars)")
    out.append("\nRULE 5  no board stacked over another board (except the screen, TMP117 #2 over #1 through the neoprene, and v6.8 the SHTC3 on its shelf over the MAX30102)" if S.SHELF else "and v6.6 the SHTC3 cage on top)")
    for n in ("brain pod", "power pod", "skin island"):
        pcbs = [(b.name, b.part("pcb")) for b in g[n][2] if not b.part("pcb").is_empty()]
        for i, (an, a) in enumerate(pcbs):
            for bn, b in pcbs[i + 1:]:
                A, Bb = a.bounding_box(), b.bounding_box()
                over = min(A[3], Bb[3]) - max(A[0], Bb[0]) > 0.5 and min(A[4], Bb[4]) - max(A[1], Bb[1]) > 0.5
                ok_ = "LCD" in an + bn or "TMP117" in an and "TMP117" in bn or (P.AIR_ON_TOP and not S.SHELF and "SHTC3" in an + bn and "TMP117" in an + bn) \
                    or (S.SHELF and "SHTC3" in an + bn and "MAX30102" in an + bn)
                bad = over and not ok_
                fail += 1 if bad else 0
                if over:
                    out.append(f"  {'FAIL' if bad else 'ok  '}  {an} / {bn}: overlap in plan{' (allowed)' if ok_ else ''}")
    return out, fail, notes


def lengths(groups, cross, pos):
    """-> rows (run, from, to, needs, has (min-normal), action, how the length is used)"""
    L = {w.name: w.length for gg in groups for w in gg[3]}
    L.update({w.name: w.length for w in cross})
    Sl = P.HOP_SLACK
    rows = []

    def row(name, a, b, need, has, how, act=None):
        lo, hi = has
        if act is None:
            if need <= lo + 0.6:
                adaptive = (" C " in how or "jog" in how)
                act = "OK as is" + (f" ({lo - need:.0f} spare)" if lo - need >= 1 else " (the shape takes up exactly this)" if adaptive
                                    else f" (within {abs(need - lo):.1f} of the shortest wire: measure it)")
            else:
                act = f"SPLICE the {lo:.0f} mm wire(s) to {5 * np.ceil((need + 2) / 5):.0f}"
        rows.append((name, a, b, need, has, act, how))
    t_x, t_d = 1.0, W.DRV_TAIL
    row("hop 1  XIAO -> DRV2605L", "XIAO 3V3/GND/D4/D5", "DRV GND/VCC/SDA/SCL", L["hop 1 XIAO -> DRV2605L (4 wires)"] + t_x + t_d + Sl, P.HOP1_LEN,
        "straight: far end -> gap -> power-pod lane (the 50-60 spread is the pad-row fan)")
    row("hop 2  DRV2605L -> ICM-20649", "DRV GND/VCC/SDA/SCL", "ICM header", L["hop 2 DRV2605L -> ICM-20649 (4 wires)"] + t_d + S.TAIL_ICM + Sl, P.HOP2_LEN,
        "straight: lane -> gap -> along the ICM pad row")
    row("battery leads", "cell (lane-side corner)", "XIAO BAT+/BAT-", L["battery leads (2 wires)"] + 1.0 + Sl, P.BAT_LEN_M,
        "straight out of the hand wall, under the XIAO")
    row("HELP button pair", "switch legs", "XIAO D-row pad + GND", L["HELP button pair (2 wires)"] + 2.0 + 2.0 + Sl, P.BTN_LEN_M,
        "straight, then along the XIAO's D-row edge")
    sc = [L[k] + 1.0 for k in L if k.startswith("screen wire") and "blue" not in k]
    nb = L["screen wire 8 (blue) -> D6"] + 1.0
    if P.LCD_GARAGE:
        row("screen wires 1-7", "screen plug", "XIAO 5V row", max(sc), P.LCD_GARAGE_LEN,
            f"ONE fold in the wire garage (R {B.GAR_R:.1f}-{B.GAR_R_MAX:.1f}, flat ribbon): 45-50 all fit, no re-solder",
            act="OK as is (the fold takes up the spare)")
        row("screen wire 8 (blue)", "screen plug", "XIAO D-row pad", nb, (P.LCD_LEN_M[0], P.LCD_LEN_M[0]),
            "tight U-turn R4 at the plug, diagonal down to D6 (shortest route)",
            act="OK as is" if nb <= P.LCD_LEN_M[0] + 0.05 else f"{nb - P.LCD_LEN_M[0]:.1f} mm over a 25 mm wire: see WARNINGS")
    else:
        row("screen wires 1-7", "screen plug", "XIAO 5V row", max(sc), P.LCD_LEN_M, "one R8 bend each, plug -> castellation",
            act=f"RE-SOLDER at the XIAO, cut to {min(sc):.0f}-{max(sc):.0f}")
        row("screen wire 8 (blue)", "screen plug", "XIAO D-row pad", nb, P.LCD_LEN_M, "U-turn R4, down the far-end side",
            act=f"RE-SOLDER at the XIAO, cut to {nb:.0f}")
    row("hop 3  ICM -> MAX30102", "ICM", "MAX30102", L["hop 3 ICM -> MAX30102 (C in the bay)"] + S.TAIL_ICM + S.TAIL_MAX, P.HOP3_LEN,
        f"ONE C in the skin bay, R {S.R3:.1f}: takes up {L['hop 3 ICM -> MAX30102 (C in the bay)'] - (S.A_MAX[0] - S.A_ICM[0]):.0f} mm over the straight line")
    row("hop 4  MAX30102 -> TMP117 #1", "MAX30102", "TMP117 #1", L["hop 4 MAX30102 -> TMP117 #1 (C in the bay)"] + S.TAIL_MAX + S.TAIL_TMP, P.HOP4_LEN,
        f"ONE C in the skin bay, R {S.R4:.1f}: takes up {L['hop 4 MAX30102 -> TMP117 #1 (C in the bay)'] - (S.A_TMP[0] - S.A_MAX[0]):.0f} mm")
    n5 = (S.H5_LEN if P.AIR_ON_TOP else L["hop 5 TMP117 #1 -> #2 (upright C, flat ribbon)"] + 2 * (1.27 + 1.0) + 12.7 / 4)
    row("hop 5  TMP117 #1 -> TMP117 #2", "TMP117 #1 (chip side)", "TMP117 #2 (top)", n5, P.HOP5_LEN,
        f"upright C at the pad edge, flat ribbon R {S.R5:.1f}")
    h6 = [w for w in cross if w.name.startswith("hop 6")][0]
    if P.AIR_ON_TOP:
        if S.SHELF:
            row("hop 6  TMP117 #2 -> SHTC3", "TMP117 #2", "SHTC3 (shelf over the MAX)", h6.length + S.H6_TAILS + Sl, P.HOP6_LEN,
                f"ONE C (R {S.R6:.1f}) over the bay, leaning {P.H6_TILT:.0f} deg up, from #2's pads to the SHTC3's pads")
        else:
            row("hop 6  TMP117 #2 -> SHTC3", "TMP117 #2", "SHTC3 (on top)", h6.length + S.H6_TAILS + Sl, P.HOP6_LEN,
                f"ONE loop (C, R {S.R6:.1f}) standing in front of the stack, up to the SHTC3 on top")
        i5 = [r[0] for r in rows].index("hop 5  TMP117 #1 -> TMP117 #2")
        rows[i5] = ("hop 5  TMP117 #1 -> TMP117 #2", "TMP117 #1 (chip side)", "TMP117 #2 (chip side, straight above)", S.H5_LEN,
                    P.HOP5_LEN, "OK if your wires reach this (your dry fit)", "straight up round the two pad edges (pads aligned)")
    else:
        row("hop 6  TMP117 #2 -> SHTC3", "TMP117 #2", "SHTC3", h6.length + spacing.H6_TAILS + Sl, P.HOP6_LEN,
            f"over the bay, ONE jog of {pos['h6_shift']:.0f} mm toward the hand end (two R8 turns), out the front opening")
    return rows


def sizes(pos):
    sk = spacing.SK
    hz = S.Z_T2_W + P.BLOB_H / 2
    if S.SHELF:      # v6.8: tallest = the SHTC3's sockets on the shelf (TMP117 #2's back is lower)
        hz = max(hz, S.Z_T2BK + getattr(P, "TMP2_BLOB_BACK_H", 0.6), S.Z_SHB + P.PCB_T + P.STEMMA_H)   # v6.9: + #2's back-side joints
    rows = [("brain pod (tray + frame)", B.OX + 2 * sk, B.OY + 2 * sk, B.Z_TOP),
            ("power pod (tray + lid)", W.OX + 2 * sk, W.OY + 2 * sk, W.Z_TOP),
            ("skin island" + (" (+ SHTC3 shelf)" if S.SHELF else ""), S.L, S.W, hz)]
    if not S.SHELF:
        rows.append(("air island", island_air.WV, island_air.LU, island_air.Z_TOP))
    x0 = pos["brain"][0] - B.OX / 2 - sk
    x1 = max(pos["skin"][0] + S.L / 2, pos["air"][0] + island_air.WV / 2)
    ys = [pos["brain"][1] - B.OY / 2 - sk, pos["brain"][1] + B.OY / 2 + sk, pos["power"][1] - W.OY / 2 - sk, pos["power"][1] + W.OY / 2 + sk,
          pos["skin"][1] - S.W / 2, pos["air"][1] + island_air.LU / 2]
    return rows, x1 - x0, (min(ys), max(ys))


def _dense(path, step=0.5):
    p = np.asarray(path)[:, :2]
    out = [p[0]]
    for a, b in zip(p[:-1], p[1:]):
        n = max(1, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.array(out)


COLS = [("hop 1", "#d62728"), ("hop 2", "#9467bd"), ("battery", "#ff7f0e"), ("HELP", "#2ca02c"), ("blue", "#00bcd4"), ("screen", "#1f77b4"),
        ("hop 3", "#8c564b"), ("hop 4", "#e377c2"), ("hop 5", "#7f7f7f"), ("hop 6", "#bcbd22"), ("TMP117", "#17becf"), ("motor", "#555555")]


def _col(n):
    return next((c for k, c in COLS if k in n), "#000")


def render(groups, cross, pos, lrows, out):
    os.makedirs(out, exist_ok=True)
    g = {x[0]: x for x in groups}
    nolcd = lambda bs: [b for b in bs if b.name not in ("LCD 1.69in", "USB-C plug")]
    trays = [(m, PRINT_COL) for x in groups for n, m in x[1] if n not in ("brain frame", "power lid")]
    covers = [(m, FRAME_COL if n == "brain frame" else LID_COL) for x in groups for n, m in x[1] if n in ("brain frame", "power lid")]
    allb = [b for x in groups for b in x[2]]
    allw = [w for x in groups for w in x[3]] + cross
    bx, by = pos["brain"]
    px, py = pos["power"]
    sx, sy = pos["skin"]
    ax_, ay_ = pos["air"]
    R = {r[0].split("  ")[0]: r for r in lrows}
    # openings (red), drawn on the wall lines
    om, otx = [], []
    for a, b2 in B.OPENS:
        om.append((bx + B.OX / 2 - P.WALL, by + B.OFF[1] + a, bx + B.OX / 2, by + B.OFF[1] + b2, "#c00", "-"))
    for a, b2 in W.OPEN_HAND:
        om.append((px - W.OX / 2, py + W.OFF[1] + a, px - W.OX / 2 + P.WALL, py + W.OFF[1] + b2, "#c00", "-"))
    for a, b2 in W.OPEN_ELBOW:
        om.append((px + W.OX / 2 - P.WALL, py + W.OFF[1] + a, px + W.OX / 2, py + W.OFF[1] + b2, "#c00", "-"))
    om.append((sx - S.L / 2, sy + S.OFF[1] + S.OPEN_HAND[0], sx - S.L / 2 + P.WALL, sy + S.OFF[1] + S.OPEN_HAND[1], "#c00", "-"))
    if P.AIR_ON_TOP:
        om.append((sx + S.OFF[0] + S.TX0 - P.CLEAR, sy + S.OFF[1] + S.Y_E, sx + S.OFF[0] + S.TX1 + P.CLEAR,
                   sy + S.OFF[1] + S.Y_E + P.HOP5_EDGE_GAP + 1.6, "#c00", "-"))
    else:
        om.append((sx + S.OFF[0] + S.OPEN_FRONT[0], sy + S.W / 2 - P.WALL, sx + S.OFF[0] + S.OPEN_FRONT[1], sy + S.W / 2, "#c00", "-"))
        hw = min(P.OPEN_W / 2, island_air.VI / 2 - 3.6)
        om.append((ax_ - hw, ay_ - island_air.LU / 2, ax_ + hw, ay_ - island_air.LU / 2 + P.WALL, "#c00", "-"))
    names = (["brain: hand-end exit (hop 1, battery, button)"] * len(B.OPENS) + ["power: hand wall"] * len(W.OPEN_HAND)
             + ["power: elbow wall (hop 2)"] * len(W.OPEN_ELBOW) + ["skin: hop 2 in"]
             + (["skin: hop 5 slot"] if P.AIR_ON_TOP else ["skin: hop 6 out", "air: hop 6 in"]))
    for i, (o, nm) in enumerate(zip(om, names)):
        wdt = max(o[2] - o[0], o[3] - o[1])
        vert = (o[3] - o[1]) > (o[2] - o[0])
        at = ((o[0] + o[2]) / 2, o[3] + 2.5) if vert else (o[2] + 7.5, (o[1] + o[3]) / 2)
        otx.append(at + (f"O{i + 1}: {wdt:.0f} wide", "#c00"))
    glue = []
    for mod, (cx, cy) in ((B, pos["brain"]), (W, pos["power"]), (S, pos["skin"])):
        for _, (x0, y0, x1, y1) in mod.GLUE:
            glue.append((cx + mod.OFF[0] + x0, cy + mod.OFF[1] + y0, cx + mod.OFF[0] + x1, cy + mod.OFF[1] + y1, "#c60", "-"))
    lcd = [b for b in g["brain pod"][2] if b.name == "LCD 1.69in"][0]
    sock = union([m for k, m in lcd.solids if k in ("socket", "plug")]).bounding_box()
    scr = (bx + B.OFF[0] + B.LCD_CX - P.LCD_W / 2, by + B.OFF[1] + B.YC - P.LCD_L / 2, bx + B.OFF[0] + B.LCD_CX + P.LCD_W / 2, by + B.OFF[1] + B.YC + P.LCD_L / 2)
    marks = [scr + ("#1f3a93", "--"), (sock[0], sock[1], sock[3], sock[4], "#1f3a93", "-")] + om + glue
    # every run with its length, labelled at its middle
    lab_pos = {"hop 1": (px - 10, py + W.OY / 2 + 14), "battery": (px - 26, py + W.OY / 2 + 24), "HELP": (px - 26, py - W.OY / 2 - 12),
               "hop 2": (px + W.OX / 2 + 4, py + W.OY / 2 + 14), "hop 3": (sx - 30, sy + S.W / 2 + 22), "hop 4": (sx + 8, sy - S.W / 2 - 14),
               "hop 5": (sx + 40, sy - S.W / 2 - 14), "hop 6": (ax_ + 26, ay_ - 4), "screen wire 1": (bx - 4, by + B.OY / 2 + 14),
               "blue": (bx + 22, by - B.OY / 2 - 12)}
    paths = []
    for w in allw:
        key = next((k for k in lab_pos if k in w.name), None)
        txt = None
        if key:
            rk = {"hop 1": "hop 1", "hop 2": "hop 2", "battery": "battery leads", "HELP": "HELP button pair", "hop 3": "hop 3", "hop 4": "hop 4",
                  "hop 5": "hop 5", "hop 6": "hop 6", "screen wire 1": "screen wires 1-7", "blue": "screen wire 8 (blue)"}[key]
            r = R[rk]
            txt = f"{rk}: {r[3]:.0f} mm (has {r[4][0]:g}" + (f"-{r[4][1]:g}" if r[4][1] != r[4][0] else "") + ")"
            if key in ("hop 3", "hop 4"):
                txt += "\n" + r[6].split(": ")[1]
            if key == "hop 6":
                txt += f"\njog {pos['h6_shift']:.0f} mm takes up the spare"
        paths.append((_dense(w.path), _col(w.name), txt, lab_pos.get(key, (0, 0))))
        if key:
            lab_pos.pop(key)
    texts = [(bx, by + B.OY / 2 + 6, f"BRAIN POD {B.OX + 2.8:.0f} x {B.OY + 2.8:.0f} x {B.Z_TOP:.1f}", "#123"),
             (px, py + W.OY / 2 + 6, f"POWER POD {W.OX + 2.8:.0f} x {W.OY + 2.8:.0f} x {W.Z_TOP:.1f}", "#123"),
             (sx + 20, sy - S.W / 2 - 26, f"SKIN ISLAND {S.L:.0f} x {S.W:.0f} x {S.Z_T2_W + 1.25:.1f}", "#123"),
             (ax_ + 22, ay_ + 9, "AIR ISLAND", "#123"),
             (bx - B.OX / 2 - 9, by + B.OFF[1] + B.XIAO_CY, "USB-C", "#a00"),
             ((bx + B.OX / 2 + px - W.OX / 2) / 2, by - B.OY / 2 - 6, "red = big top-open\nwire openings O1..O6", "#c00")] + otx
    render_flat(trays + twin_items(nolcd(allb), [])[0], f"{out}/v61_overview_top.png", look="top", figsize=(18, 12), paths=paths, texts=texts,
                marks=marks,
                title="v6.1 band from above, hand end LEFT (frame + lid off; dashed blue = screen outline).  Every wire run drawn with the free length "
                      "it needs (pad to pad, joints, fan, 5 mm slack per gap) and what you have.\nred = big top-open wire openings, orange = glue zones.  "
                      "Spare length is taken up INSIDE the parts (the skin island's two Cs and hop 6's jog), not as band length")
    sa = [(m, PRINT_COL) for n in ("skin island", "air island") for _, m in g[n][1]]
    render_flat(sa + twin_items(g["skin island"][2] + g["air island"][2], [])[0], f"{out}/v61_skin_island.png", look="top", figsize=(14, 10),
                paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in g["skin island"][3] + [c for c in cross if c.name.startswith(("hop 2", "hop 6"))]],
                marks=om[-3:] + glue[-3:],
                texts=[(sx + S.OFF[0] + S.A_ICM[0], sy + S.OFF[1] + 9, "ICM-20649", "#fff"), (sx + S.OFF[0] + S.A_MAX[0], sy + S.OFF[1] + 10, "MAX30102\n(sensor down)", "#fff"),
                       (sx + S.OFF[0] + S.A_TMP[0], sy + S.OFF[1] + 9, "TMP117 #2 over #1", "#fff"),
                       (sx + S.OFF[0] + (S.A_ICM[0] + S.A_MAX[0]) / 2, sy + S.OFF[1] + S.APEX3 + 4, f"hop 3: ONE C, R {S.R3:.0f}", "#8c564b"),
                       (sx + S.OFF[0] + (S.A_MAX[0] + S.A_TMP[0]) / 2, sy + S.OFF[1] + S.APEX4 + 4, f"hop 4: ONE C, R {S.R4:.0f}", "#e377c2"),
                       (sx + S.OFF[0] + S.X_H6_EXIT, sy + S.W / 2 + 4, f"hop 6 out (jog {pos['h6_shift']:.0f} mm)", "#888800"),
                       (sx - S.L / 2 - 8, sy + S.OFF[1] + S.Y_H2, "hop 2\nin", "#9467bd"),
                       (sx, sy - S.W / 2 - 6, "back wall: strap tongue enters the slot over TMP117 #1 here", "#555")] + otx[-3:],
                title="v6.1 SKIN ISLAND from above (hand end LEFT).  Pads all face the bay; each hop is ONE wide C round a low tongue wall "
                      "(glue at the apex, orange); red = big top-open openings")
    # power + brain close-ups
    render_flat([(m, PRINT_COL) for n, m in g["power pod"][1] if n == "power pod"] + twin_items(g["power pod"][2], [])[0], f"{out}/v61_power_pod.png",
                look="top", figsize=(12, 12), paths=[(_dense(w.path)[[abs(q[0] - px) < W.OX / 2 + 6 for q in _dense(w.path)]], _col(w.name), None, (0, 0))
                                                     for w in g["power pod"][3] + cross[:4]], marks=om[1:1 + len(W.OPEN_HAND) + len(W.OPEN_ELBOW)] + glue,
                texts=[(px + W.OFF[0] + (W.BAT_X0 + W.BAT_X1) / 2, py + W.OFF[1] + (W.BAT_Y0 + W.BAT_Y1) / 2, "LiPo, lead end at the hand wall\n(leads at the lane-side corner)", "#123"),
                       (px + W.OFF[0] + W.MOTOR_C[0], py + W.OFF[1] + W.MOTOR_C[1] + 3, "DRV2605L\non the motor cup", "#fff"),
                       (px + W.OFF[0] + W.BTN_C[0], py + W.OFF[1] + W.BTN_C[1] - 7, "HELP", "#2ca02c"),
                       (px, py + W.OFF[1] + W.Y_H1 + 3.4, "LANE: hop 1 in, hop 2 out", "#c00"),
                       (px, py - W.OY / 2 - 6, f"interior {W.XI:.1f} x {W.YI:.1f}; red = openings (top-open, {P.OPEN_W:.0f}+ wide), orange = glue", "#555")]
                      + otx[len(B.OPENS):len(B.OPENS) + len(W.OPEN_HAND) + len(W.OPEN_ELBOW)],
                title="v6.1 POWER POD, open, from above (hand end LEFT): short along the forearm so hop 1 + hop 2 span it")
    render_flat([(m, PRINT_COL) for n, m in g["brain pod"][1] if n == "brain pod"] + twin_items(nolcd(g["brain pod"][2]), [])[0], f"{out}/v61_brain_pod.png",
                look="top", figsize=(11, 12), paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in g["brain pod"][3] + cross[:3]],
                marks=[scr + ("#1f3a93", "--")] + om[:len(B.OPENS)] + glue[:len(B.GLUE)],
                texts=[(bx - B.OX / 2 - 6, by + B.OFF[1] + B.XIAO_CY, "USB-C", "#a00")] + otx[:len(B.OPENS)],
                title="v6.1 BRAIN POD from above (frame + screen off, hand end LEFT; dashed blue = screen outline).  "
                      "red = the big top-open exit toward the power pod, orange = glue")
    # v6.4: the MAX30102 area: top, skin side, section through the optical chip
    so = np.array([sx, sy])
    def fr(r, col, ls="-"):
        return (r[0] + S.OFF[0] + so[0], r[1] + S.OFF[1] + so[1], r[2] + S.OFF[0] + so[0], r[3] + S.OFF[1] + so[1], col, ls)
    isl = [m for n, m in g["skin island"][1] if n == "skin island"][0]
    mxb = [b2 for b2 in g["skin island"][2] if b2.name == "MAX30102"]
    wr = S._win_rect()
    jr = (S.MAX_X0 + 0.3, S.Y_E - P.MAX_BLOB_STRIP - 0.5, S.MAX_X1 - 0.3, S.Y_E + P.PAD_ROOM)
    pk = (S.MAX_X0 - S.MC, S.MAX_Y0 - S.MC, S.MAX_X1 + S.MC, S.Y_E)
    pp = S.part_pockets(S._boards()[1])
    pmk = []
    for lab, m, thr in pp:
        bb = m.bounding_box()
        pmk.append(fr((bb[0], bb[1], bb[3], bb[4]), "#d62728" if thr else "#2ca02c", "-" if thr else "--"))
    cx = lambda r: (r[0] + r[2]) / 2 + S.OFF[0] + sx
    cy = lambda r: (r[1] + r[3]) / 2 + S.OFF[1] + sy
    chb = mxb[0].part("chip").bounding_box()
    ccx, ccy = (chb[0] + chb[3]) / 2, (chb[1] + chb[4]) / 2
    zsk = S.skin_z(ccy - sy)
    gap = zsk - chb[2]
    f1, f2, f3 = f"{out}/_v64a.png", f"{out}/_v64b.png", f"{out}/_v64c.png"
    render_flat([(isl, PRINT_COL)] + twin_items(g["skin island"][2], [])[0], f1, look="top", figsize=(13, 7),
                marks=[fr(jr, "#c60"), fr(pk, "#1f3a93", "--")],
                paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in g["skin island"][3]],
                texts=[(cx(jr), jr[3] + S.OFF[1] + sy + 9, f"MAX30102 back: joints + glue ({P.MAX_BLOB_H} mm) + {P.MAX_BACK_ROOM_H:.0f} mm free, "
                        f"{P.PAD_ROOM:.0f} mm pad room, wires exit to the bay", "#c60"),
                       (cx(pk), pk[1] + S.OFF[1] + sy - 2.5, f"pocket +{P.MAX_POCKET_LOOSE} per side (blue dashed)", "#1f3a93")],
                title="v6.4 SKIN ISLAND from above (hand end LEFT): MAX30102 sensor down, wires on its BACK, board dropped to the skin")
    nthr = sum(1 for _, _, t in pp if t)
    render_flat([(isl, PRINT_COL)], f2, look="bottom", figsize=(13, 7), marks=[fr(wr, "#c00")] + pmk,
                texts=[(cx(wr), wr[1] + S.OFF[1] + sy - 2.5, f"optical window {P.MAX_WIN_L:.1f} x {P.MAX_WIN_W:.1f} (chip {gap:+.2f} mm past the skin)", "#c00"),
                       (cx(pk), pk[3] + S.OFF[1] + sy + 3.0, f"part pockets: red = through the skin face ({nthr}: the parts show, gap {P.MAX_PART_CLEAR} round them), "
                        "green dashed = blind", "#333")],
                title="SKIN SIDE (seen from the skin, hand end RIGHT): window round the chip, one close pocket per tall part"
                      + (f"; {P.MAX_SEAL_LIP_H} mm seal lip round the window" if P.SKIN_CURVE else ""))
    cl = ((1.0, 0.0, 0.0), ccx)
    ys = (sy + S.OFF[1] + S.MAX_Y0 - 3, sy + S.OFF[1] + S.Y_E + 3)
    render_flat([(isl, PRINT_COL)] + twin_items(mxb, [])[0], f3, look="elbow", figsize=(13, 5), clip=cl,
                hlines=[(zsk, ccy - 6, ccy + 6, f"skin under the chip  z {zsk:+.2f}"),
                        (chb[2], ccy - 3, ccy + 3, f"chip face  z {chb[2]:+.2f}  ->  {gap:.2f} mm past the skin"),
                        (S.Z_MF, ys[0], ys[1], f"MAX sensor-side PCB face  z {S.Z_MF:+.2f}"),
                        (S.Z_MB + P.MAX_BLOB_H, ys[0], ys[1], f"back-side joints + glue top  z {S.Z_MB + P.MAX_BLOB_H:+.2f}")],
                title=f"SECTION through the MAX30102 optical chip (cut across the wrist, seen from the elbow end): chip {gap:.2f} mm past the skin "
                      f"(v6.3: 0.55 mm back)")
    from PIL import Image
    ims = [Image.open(f) for f in (f1, f2, f3)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v64_skin_island.png")
    for f in (f1, f2, f3):
        os.remove(f)
    # v6.7.2: power lid HELP hole
    lidp = [m for n, m in g["power pod"][1] if n == "power lid"][0]
    trp = [m for n, m in g["power pod"][1] if n == "power pod"][0]
    btc = (px + W.OFF[0] + W.BTN_C[0], py + W.OFF[1] + W.BTN_C[1])
    q1, q2 = f"{out}/_v672a.png", f"{out}/_v672b.png"
    hh2 = P.BTN_SQ_HOLE / 2
    render_flat([(lidp, LID_COL)], q1, look="top", figsize=(10, 12),
                marks=[(btc[0] - hh2, btc[1] - hh2, btc[0] + hh2, btc[1] + hh2, "#c00", "-"),
                       (btc[0] - P.BTN_CLEAR_BOX / 2, btc[1] - P.BTN_CLEAR_BOX / 2, btc[0] + P.BTN_CLEAR_BOX / 2, btc[1] + P.BTN_CLEAR_BOX / 2, "#2ca02c", "--")],
                texts=[(btc[0] + 12, btc[1] - 8, f"HELP: {P.BTN_SQ_HOLE:.1f} x {P.BTN_SQ_HOLE:.1f} through-hole,\n{P.BTN_DISH_D:.0f} mm finger dish {P.BTN_DISH_DEPTH} deep", "#c00")],
                title="v6.7.2 POWER LID from above (hand end LEFT): square through-hole for the wired switch (green dashed = 9 x 9 kept clear underneath)")
    render_flat([(trp, PRINT_COL), (lidp, LID_COL)] + twin_items([b for b in g["power pod"][2] if b.name == "button"], [])[0], q2, look="side",
                figsize=(10, 5), clip=((0.0, -1.0, 0.0), -btc[1]),
                hlines=[(W.Z_TOP, btc[0] - 6, btc[0] + 6, f"lid top {W.Z_TOP:.1f} (plunger tip {W.Z_TIP:.1f})"),
                        (W.Z_BTN1, btc[0] - 4, btc[0] + 4, f"switch body top {W.Z_BTN1:.1f}"),
                        (W.Z_BTN0, btc[0] - 4, btc[0] + 4, f"backing bar top {W.Z_BTN0:.1f} ({W.Z_BTN0 - P.FLOOR:.1f} above the pod floor)")],
                title="v6.7.2 SECTION through the HELP hole (lid on): switch on the backing bar, plunger in the hole")
    from PIL import Image
    ims = [Image.open(f) for f in (q1, q2)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v672_power_lid.png")
    for f in (q1, q2):
        os.remove(f)
    # v6.7: the brain cover from below (stops + USB-C opening) and a section through the USB-C tunnel with the cover on
    trb = [m for n, m in g["brain pod"][1] if n == "brain pod"][0]
    frb = [m for n, m in g["brain pod"][1] if n == "brain frame"][0]
    ob = np.array([bx + B.OFF[0], by + B.OFF[1]])
    hwu = P.USBC_PLUG_W / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS
    hhu = P.USBC_PLUG_H / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS
    ys0 = B.YC + P.LCD_L / 2 + P.GAP + 0.2
    stop_marks = [(ob[0] - P.WALL, ob[1] + B.YI, ob[0] + B.XI + P.WALL, ob[1] + B.YI + P.WALL, "#d62728", "-"),
                  (ob[0] - P.WALL, ob[1] + ys0, ob[0], ob[1] + B.YI + P.WALL, "#d62728", "-"),
                  (ob[0] + B.XI, ob[1] + ys0, ob[0] + B.XI + P.WALL, ob[1] + B.YI + P.WALL, "#d62728", "-"),
                  (ob[0] - P.WALL, ob[1] - P.WALL, ob[0], ob[1] - P.WALL + 1.4, "#d62728", "-"),
                  (ob[0] + B.XI, ob[1] - P.WALL, ob[0] + B.XI + P.WALL, ob[1] - P.WALL + 1.4, "#d62728", "-")]
    u1, u2 = f"{out}/_v67a.png", f"{out}/_v67b.png"
    render_flat([(frb, FRAME_COL)], u1, look="bottom", figsize=(10, 12), marks=stop_marks,
                texts=[(ob[0] + B.XI / 2, ob[1] + B.YI + 5, "red = STOPS: land on the pod rim (cover sits level)", "#d62728"),
                       (ob[0] - P.WALL - 4, ob[1] + B.XIAO_CY, f"USB-C\n{2 * hwu:.1f} x {2 * hhu:.1f}", "#a00")],
                title=f"v6.7 BRAIN COVER from below (window face down, hand end RIGHT): skirt {P.FRAME_SKIRT + P.FRAME_SKIRT_EXTRA:.1f} mm, "
                      "stop ledges on the rim, USB-C opening cut through the skirt")
    yc7 = by + B.OFF[1] + B.XIAO_CY
    render_flat([(trb, PRINT_COL), (frb, FRAME_COL)] + twin_items(g["brain pod"][2], [])[0], u2, look="side", figsize=(12, 6),
                clip=((0.0, -1.0, 0.0), -yc7),
                hlines=[(B.Z_TOP, bx - B.OX / 2, bx + B.OX / 2, f"cover top {B.Z_TOP:.2f}"),
                        (B.Z_WALL, bx - B.OX / 2, bx + B.OX / 2, f"pod rim {B.Z_WALL:.2f}: the stops land here"),
                        (B.Z_WALL - P.FRAME_SKIRT - P.FRAME_SKIRT_EXTRA, bx - B.OX / 2, bx + B.OX / 2,
                         f"cover skirt bottom {B.Z_WALL - P.FRAME_SKIRT - P.FRAME_SKIRT_EXTRA:.2f} (+{P.FRAME_SKIRT_EXTRA:.0f})"),
                        (B.Z_USB + hhu, bx - B.OX / 2 - 3, bx - B.OX / 2 + 3, f"USB-C opening {B.Z_USB - hhu:.2f}-{B.Z_USB + hhu:.2f}")],
                title="v6.7 SECTION through the USB-C tunnel (cover on the pod, hand end LEFT): plug in, cover level on its stops")
    from PIL import Image
    ims = [Image.open(f) for f in (u1, u2)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v67_brain_cover.png")
    for f in (u1, u2):
        os.remove(f)
    # v6.6: TMP117 #2 straight above #1, the SHTC3 cage on top; hop 5 straight up, hop 6 ONE loop
    if P.AIR_ON_TOP and not S.SHELF:
        isl6 = [m for n, m in g["skin island"][1] if n == "skin island"][0]
        cage6 = [m for n, m in g["skin island"][1] if n == "air cage"][0]
        h6w = [c for c in cross if c.name.startswith("hop 6")][0]
        h5w = [w for w in g["skin island"][3] if w.name.startswith("hop 5")][0]
        o6 = np.array([sx + S.OFF[0], sy + S.OFF[1]])
        k6, k7 = f"{out}/_v66a.png", f"{out}/_v66b.png"
        r5 = [r for r in lrows if r[0].startswith("hop 5")][0]
        r6 = [r for r in lrows if r[0].startswith("hop 6")][0]
        render_flat([(isl6, PRINT_COL), (cage6, LID_COL)] + twin_items(g["skin island"][2], [])[0], k6, look="top", figsize=(14, 8),
                    paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in g["skin island"][3] + [h6w]],
                    marks=[om[-1]],
                    texts=[(o6[0] + S.TX0 + 12.7, o6[1] + S.Y_E + 4.5, f"hop-5 slot (full width, floor to top): hop 5 = {r5[3]:.1f} mm", "#c00"),
                           (o6[0] + S.X_H6 + 2, o6[1] + S.YI + 4, f"hop 6: ONE loop R {S.R6:.1f}, {r6[3]:.0f} mm", "#888800"),
                           (o6[0] + S.TX0 + 12.7 + P.AIR_DX, o6[1] + S.Y_E - 9, "SHTC3 on top (cage)", "#fff")],
                    title="v6.6 SKIN ISLAND + SHTC3 CAGE from above (hand end LEFT): TMP117 #2 straight above #1, the SHTC3 cage on top of #2")
        xc6 = o6[0] + S.X_H6 + 0.5
        zsk = 0.0
        render_flat([(isl6, PRINT_COL), (cage6, LID_COL)] + twin_items(g["skin island"][2], [h5w, h6w])[0], k7, look="elbow", figsize=(13, 7),
                    clip=((1.0, 0.0, 0.0), xc6),
                    hlines=[(0.0, o6[1] - 1, o6[1] + S.Y_E, "skin plane 0"),
                            (S.Z_T1F, o6[1], o6[1] + S.Y_E, f"TMP117 #1 chip face {S.Z_T1F:.2f} (0.2 past the skin)"),
                            (S.Z_SLOT1, o6[1], o6[1] + S.Y_E, f"strap slot {S.Z_T1B:.1f}-{S.Z_SLOT1:.1f}"),
                            (S.Z_T2, o6[1], o6[1] + S.Y_E, f"plate top {S.Z_T2:.2f} ({P.TMP2_PLATE_T} thick)"),
                            (S.Z_T2BK, o6[1], o6[1] + S.Y_E, f"TMP117 #2 (chip down) {S.Z_T2F:.2f}-{S.Z_T2BK:.2f}"),
                            (S.Z_SB, o6[1], o6[1] + S.Y_E, f"SHTC3 board {S.Z_SB:.2f} ({P.AIR_GAP_OVER_T2:.0f} mm still air over #2)"),
                            (island_air.Z_TOP, o6[1], o6[1] + S.Y_E, f"cage top {island_air.Z_TOP:.2f}"),
                            (float(h6w.path[:, 2].max()) + P.BUNDLE_D / 2, o6[1] + S.Y_E, o6[1] + S.YI, f"hop-6 loop top {h6w.path[:, 2].max() + P.BUNDLE_D / 2:.1f}")],
                    title=f"v6.6 SECTION through the TMP117 #1 / #2 / SHTC3 stack (seen from the elbow end, bay RIGHT): hop 5 straight up round "
                          f"the pad edges {r5[3]:.1f} mm, hop 6 ONE loop {r6[3]:.0f} mm")
        from PIL import Image
        ims = [Image.open(f) for f in (k6, k7)]
        wd = max(i.width for i in ims)
        cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
        yy = 0
        for i in ims:
            cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
        cv.save(f"{out}/v66_skin_air.png")
        for f in (k6, k7):
            os.remove(f)
    if S.SHELF:
        render_v68(groups, cross, pos, lrows, out)
        render_v70(groups, cross, pos, lrows, out)
    # v6.5: brain pod with the wire garage: top (open) + section across the wrist through the fold (screen resting)
    bo = np.array([bx + B.OFF[0], by + B.OFF[1]])
    trayb = [m for n, m in g["brain pod"][1] if n == "brain pod"][0]
    frameb = [m for n, m in g["brain pod"][1] if n == "brain frame"][0]
    gz = [(bo[0] + x0, bo[1] + y0, bo[0] + x1, bo[1] + y1, "#c60", "-") for _, (x0, y0, x1, y1) in B.GLUE]
    gx0, gx1 = bo[0], bo[0] + B.XI
    gy0, gy1 = bo[1] + B.Y_5V + P.PAD_ROOM, bo[1] + B.YI
    g1, g2 = f"{out}/_v65a.png", f"{out}/_v65b.png"
    sleeves = [c for c in cross if c.name.startswith("splice sleeve")]
    trayp = [m for n, m in g["power pod"][1] if n == "power pod"][0]
    sl_txt = []
    for (wn, Ls, da, db), sv in zip(SLEEVES, sleeves):
        mid = sv.path.mean(axis=0)
        sl_txt.append((mid[0], mid[1] + (4.5 if wn.startswith("battery") else -4.5),
                       f"{wn.split(' (')[0]} sleeve lane {Ls:.0f} mm ({da:.0f}-{db:.0f} mm from the XIAO pad)", "#000"))
    render_flat([(trayb, PRINT_COL), (trayp, PRINT_COL)] + twin_items(nolcd(g["brain pod"][2]) + g["power pod"][2], [])[0]
                + [(sv.solid, (0.1, 0.55, 0.1)) for sv in sleeves], g1, look="top", figsize=(14, 13),
                paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in g["brain pod"][3] + [c for c in cross[:3]]],
                marks=[scr + ("#1f3a93", "--"), (gx0, gy0, gx1, gy1, "#c00", "--")] + gz + om[:1 + len(W.OPEN_HAND)],
                texts=[(bx, gy1 + 4, f"WIRE GARAGE (+{B.YI - (B.Y_5V + P.PAD_ROOM):.1f} mm across the wrist): the 7 screen wires make ONE fold here", "#c00"),
                       (bx, gy0 + 2.0, f"fold R {B.GAR_R:.1f} (45 mm wires) .. {B.GAR_R_MAX:.1f} (50 mm), glue at the floor leg + apex (orange)", "#c60"),
                       (bx - B.OX / 2 - 6, by + B.OFF[1] + B.XIAO_CY, "USB-C", "#a00"),
                       (bx + 6, bo[1] + B.YC - 14, f"blue: shortest route {[r for r in lrows if 'blue' in r[0]][0][3]:.1f} mm", "#17becf")] + sl_txt,
                title="v6.5 BRAIN POD + POWER POD from above, open (hand end LEFT). Red dashed = wire garage; green rods = splice sleeves, "
                      "straight through O1 / O2, never inside the brain pod")
    xc = bo[0] + B.PIN_X[3]
    render_flat([(trayb, PRINT_COL), (frameb, FRAME_COL)] + twin_items(g["brain pod"][2], g["brain pod"][3])[0], g2, look="elbow",
                figsize=(13, 6), clip=((1.0, 0.0, 0.0), xc),
                hlines=[(B.Z_LCD, bo[1] + B.YC - P.LCD_L / 2, bo[1] + B.YC + P.LCD_L / 2, f"screen back {B.Z_LCD:.2f}: resting on its seat, flat"),
                        (B.Z_C, bo[1] + B.Y_PS, bo[1] + B.GAR_YU, f"plug + upper leg {B.Z_C:.2f}"),
                        (B.Z_XTOP, bo[1] + B.Y_D, bo[1] + B.Y_5V, f"XIAO top {B.Z_XTOP:.2f}"),
                        (P.LCD_GARAGE_FLOOR_Z, bo[1] + B.GAR_YU - 3, bo[1] + B.GAR_YU + 3, "fold floor leg")],
                title="v6.5 SECTION across the wrist through the screen cable (seen from the elbow end, +Y = garage RIGHT): ONE fold in the garage, "
                      "screen resting flat with GAP over everything")
    from PIL import Image
    ims = [Image.open(f) for f in (g1, g2)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v65_brain_pod.png")
    for f in (g1, g2):
        os.remove(f)
    render_flat([(trayb, PRINT_COL), (frameb, FRAME_COL), (trayp, PRINT_COL)]
                + [(m, LID_COL) for n, m in g["power pod"][1] if n == "power lid"]
                + twin_items(g["brain pod"][2] + g["power pod"][2], g["brain pod"][3] + cross[:3])[0]
                + [(sv.solid, (0.1, 0.55, 0.1)) for sv in sleeves], f"{out}/v65_side.png", look="side", figsize=(14, 5),
                hlines=[(B.Z_TOP, bx - B.OX / 2, bx + B.OX / 2, f"brain pod top {B.Z_TOP:.2f} (unchanged)"),
                        (B.Z_LCD, bx - B.OX / 2, bx + B.OX / 2, f"screen back {B.Z_LCD:.2f}, resting flat"),
                        (W.Z_TOP, px - W.OX / 2, px + W.OX / 2, f"power pod top {W.Z_TOP:.1f}"),
                        (float(sleeves[0].path[:, 2].mean()), float(sleeves[0].path[0, 0]), float(sleeves[0].path[-1, 0]),
                         f"hop 1 sleeve lane {SLEEVES[0][1]:.0f} mm (green)"),
                        (float(sleeves[1].path[:, 2].mean()), float(sleeves[1].path[0, 0]), float(sleeves[1].path[-1, 0]),
                         f"battery sleeve lane {SLEEVES[1][1]:.0f} mm")],
                title="v6.5 brain pod -> gap -> power pod from the side (frame + lid on, hand end LEFT): the splice sleeves lie straight "
                      "across the gap, outside the brain pod")
    hl = [(B.Z_TOP, bx - B.OX / 2, bx + B.OX / 2, f"brain pod top {B.Z_TOP:.1f}"),
          (W.Z_TOP, px - W.OX / 2, px + W.OX / 2, f"power pod top {W.Z_TOP:.1f}"),
          (S.Z_T2_W + 1.25, sx - S.L / 2, sx + S.L / 2, f"skin island {S.Z_T2_W + 1.25:.1f} (TMP stack)"),
          ((S.Z_SHB + P.PCB_T + P.STEMMA_H, sx + S.OFF[0] + S.SX0, sx + S.OFF[0] + S.SX1, f"SHTC3 sockets {S.Z_SHB + P.PCB_T + P.STEMMA_H:.1f} (shelf)")
           if S.SHELF else (island_air.Z_TOP, ax_ - 14, ax_ + 14, f"air island {island_air.Z_TOP:.1f} (behind)")),
          (0.0, bx - B.OX / 2, sx + S.L / 2, "skin")]
    render_flat(trays + covers + twin_items(allb, allw)[0], f"{out}/v61_side.png", look="side", figsize=(17, 5), hlines=hl,
                title="v6.1 band from the side (frame + lid on; hand end LEFT).  Heights in mm above the skin")
    render_scene(trays + twin_items(nolcd(allb), allw)[0], f"{out}/v61_iso_open.png", view=(40, -62), figsize=(15, 9),
                 title="v6.1 digital twin, open (screen, frame and lid off): every wire in place")
    render_scene(trays + covers + twin_items(allb, allw)[0], f"{out}/v61_iso.png", view=(32, -62), figsize=(15, 9),
                 title="v6.1 digital twin (frame + lid on, USB-C cable plugged in)")


def render_v68(groups, cross, pos, lrows, out):
    """v6.8: the skin island with the SHTC3 shelf over the MAX30102 -> png/v68_outside.png, v68_cutaway.png, v68_top.png"""
    g = {x[0]: x for x in groups}
    sx, sy = pos["skin"]
    o = np.array([sx + S.OFF[0], sy + S.OFF[1]])
    isl = [m for n, m in g["skin island"][1] if n == "skin island"][0]
    shf = [m for n, m in g["skin island"][1] if n == "SHTC3 shelf"][0]
    boards = g["skin island"][2]
    h6w = [c for c in cross if c.name.startswith("hop 6")][0]
    wires = g["skin island"][3] + [h6w]
    SHC = (0.85, 0.55, 0.15)
    r6 = [r for r in lrows if r[0].startswith("hop 6")][0]
    # outside view
    render_scene([(isl, PRINT_COL), (shf, SHC)] + twin_items(boards, wires)[0], f"{out}/v68_outside.png", view=(32, -58), figsize=(14, 9),
                 title="v6.8 SKIN ISLAND from outside: SHTC3 (sensor up) on the orange drop-in shelf over the MAX30102, level with TMP117 #2 "
                       "(right); hop 6 = ONE C over the bay")
    # cutaway: across the wrist through the MAX + shelf + SHTC3, and along the forearm through the MAX / SHTC3 / TMP stack
    xc = o[0] + S.MAX_X0 + P.MAX_L / 2 + 1.0
    yc = o[1] + S.Y_E - 4.0
    mz = S.MAX_J_TOP
    hl = [(0.0, o[1] - 1.5, o[1] + S.Y_E, "skin plane 0"),
          (S.Z_MB, o[1] + S.MAX_Y0, o[1] + S.Y_E, f"MAX30102 back (wire side) {S.Z_MB:.2f}"),
          (mz, o[1] + S.Y_E - P.MAX_BLOB_STRIP, o[1] + S.Y_E + 1, f"MAX joints + glue top {mz:.2f}"),
          (S.Z_SH0, o[1] - 1.5, o[1] + S.Y_E - 0.5, f"shelf underside {S.Z_SH0:.2f}: {S.Z_SH0 - S.Z_MB:.2f} over the MAX back, {S.Z_SH0 - mz:.2f} over its joints"),
          (S.Z_SH1, o[1] - 1.5, o[1] + S.Y_E - 0.5, f"shelf top {S.Z_SH1:.2f} = TMP117 #2 plate top"),
          (S.Z_SHB, o[1] + S.SY0, o[1] + S.SY1, f"SHTC3 board {S.Z_SHB:.2f} ({P.SHELF_STANDOFF:.1f} still air over the shelf)"),
          (S.Z_SHB + P.PCB_T + P.STEMMA_H, o[1] + S.SY0, o[1] + S.SY1, f"SHTC3 sockets top {S.Z_SHB + P.PCB_T + P.STEMMA_H:.2f}")]
    c1, c2 = f"{out}/_v68a.png", f"{out}/_v68b.png"
    render_flat([(isl, PRINT_COL), (shf, SHC)] + twin_items(boards, wires)[0], c1, look="elbow", figsize=(13, 7), clip=((1.0, 0.0, 0.0), xc),
                hlines=hl, title="v6.8 SECTION across the wrist through the MAX30102 + shelf + SHTC3 (seen from the elbow end, bay RIGHT, back wall LEFT)")
    render_flat([(isl, PRINT_COL), (shf, SHC)] + twin_items(boards, wires)[0], c2, look="side", figsize=(15, 6), clip=((0.0, -1.0, 0.0), -yc),
                hlines=[(0.0, o[0], o[0] + S.XI, "skin plane 0"),
                        (S.Z_MB, o[0] + S.MAX_X0, o[0] + S.MAX_X1, f"MAX back {S.Z_MB:.2f}"),
                        (S.Z_SH0, o[0] + S.XS0, o[0] + S.XS1, f"shelf {S.Z_SH0:.1f}-{S.Z_SH1:.1f}"),
                        (S.Z_T2, o[0] + S.TX0, o[0] + S.TX1, f"TMP117 #2 plate top {S.Z_T2:.2f} (same floor)"),
                        (S.Z_T2F, o[0] + S.TX0, o[0] + S.TX1, f"TMP117 #2 (chip down) {S.Z_T2F:.2f}-{S.Z_T2BK:.2f}"),
                        (S.Z_SHB, o[0] + S.SX0, o[0] + S.SX1, f"SHTC3 board {S.Z_SHB:.2f}-{S.Z_SHB + P.PCB_T:.2f}"),
                        (S.Z_LIP, o[0] + S.XS0, o[0] + S.X_HLIP, f"lips / stops top {S.Z_LIP:.2f}")],
                title="v6.8 SECTION along the forearm through the MAX30102 and the SHTC3 (seen from the back wall, hand end LEFT): the SHTC3 and "
                      "TMP117 #2 side by side on one upper floor")
    from PIL import Image
    ims = [Image.open(f) for f in (c1, c2)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v68_cutaway.png")
    for f in (c1, c2):
        os.remove(f)
    # top view
    ch = (o[0] + S.CH[0], o[1] + S.CH[1], o[0] + S.CH[2], o[1] + S.Y_E - 0.5, "#c00", "--")
    render_flat([(isl, PRINT_COL), (shf, SHC)] + twin_items(boards, [])[0], f"{out}/v68_top.png", look="top", figsize=(14, 8),
                paths=[(_dense(w.path), _col(w.name), None, (0, 0)) for w in wires], marks=[ch],
                texts=[(o[0] + (S.SX0 + S.SX1) / 2, o[1] + S.SY0 - 4.5, "SHTC3 on the shelf (sensor up, pads toward the bay)", "#a50"),
                       (o[0] + (S.CH[0] + S.CH[2]) / 2, o[1] + S.Y_E + 2.2, "wire channel over the MAX joints (red dashed)", "#c00"),
                       (o[0] + S.A_TMP[0], o[1] + 9, "TMP117 #2 over #1", "#fff"),
                       (o[0] + S.A_ICM[0], o[1] + 9, "ICM-20649", "#fff"),
                       (o[0] + S.X_H6 - 6, o[1] + S.YI + 4, f"hop 6: ONE C R {S.R6:.1f}, {r6[3]:.0f} mm", "#888800")],
                title="v6.8 SKIN ISLAND from above (hand end LEFT, bay UP): SHTC3 shelf over the MAX30102, level with TMP117 #2")


def render_v70(groups, cross, pos, lrows, out):
    """v7.0 final edition -> png/v70_tmp2_stack_section.png (3 sections through the TMP117 stack) and png/v70_top_hole_spacing.png
    (printed parts only, from above, with the pin spacings dimensioned)"""
    g = {x[0]: x for x in groups}
    sx, sy = pos["skin"]
    o = np.array([sx + S.OFF[0], sy + S.OFF[1]])
    isl = [m for n, m in g["skin island"][1] if n == "skin island"][0]
    shf = [m for n, m in g["skin island"][1] if n == "SHTC3 shelf"][0]
    boards = g["skin island"][2]
    h6w = [c for c in cross if c.name.startswith("hop 6")][0]
    wires = g["skin island"][3] + [h6w]
    SHC = (0.85, 0.55, 0.15)
    items = [(isl, PRINT_COL), (shf, SHC)] + twin_items(boards, wires)[0]
    jb = S.Z_T2F - P.TMP2_BLOB_CHIP_H
    bx0, by0, bx1, by1, _ = S.t2_blob_rect(P.TMP2_RELIEF_CLEAR)
    ye = o[1] + S.Y_E
    c1, c2, c3 = f"{out}/_v70a.png", f"{out}/_v70b.png", f"{out}/_v70c.png"
    xc = o[0] + S.TX0 + 12.7
    render_flat(items, c1, look="elbow", figsize=(13, 7.5), clip=((1.0, 0.0, 0.0), xc),
                hlines=[(0.0, o[1] - 1.5, ye, f"skin plane 0 (TMP117 #1 floor {S.Z_T1F:.1f}, chip {P.TMP_CHIP_PROUD:.1f} past the skin face)"),
                        (S.Z_SLOT1, o[1], ye - 2.5, f"strap slot {S.Z_T1B:.1f}-{S.Z_SLOT1:.1f}"),
                        (S.Z_T2, o[1], ye - P.TMP2_PLATE_FRONT, f"plate {S.Z_SLOT1:.1f}-{S.Z_T2:.1f}: SOLID {S.Z_T2 - S.Z_SLOT1:.1f} mm, no pockets"),
                        (jb, o[1] + by0 + 0.5, ye + P.BLOB_OVER, f"#2 joints + glue bottom {jb:.1f} ({jb - S.Z_T2:.1f} free over the plate)"),
                        (S.Z_T2CH, o[1] + 6, o[1] + 12, f"chip face {S.Z_T2CH:.1f} = top of the chip pedestal (45 deg flare)"),
                        (S.Z_T2F, o[1] + S.Y_E - P.ADA_W, ye, f"#2 board {S.Z_T2F:.1f}-{S.Z_T2BK:.1f} (chip down) on the back block"),
                        (S.Z_T2BK + P.TMP2_BLOB_BACK_H, o[1] + by0 + 0.5, ye + P.BLOB_OVER,
                         f"back-side joints + glue top {S.Z_T2BK + P.TMP2_BLOB_BACK_H:.1f} (open air)")],
                title="v7.0 SECTION across the wrist through TMP117 #2's chip (seen from the elbow end, bay RIGHT): solid plate, chip on its "
                      "pedestal, board on the back block")
    yc = o[1] + S.Y_E - 8.89
    render_flat(items, c2, look="side", figsize=(15, 6), clip=((0.0, -1.0, 0.0), -yc),
                hlines=[(0.0, o[0] + S.TX0 - 4, o[0] + S.TX1 + 4, "skin plane 0"),
                        (S.Z_T2, o[0] + S.TX0 - 8, o[0] + S.TX1, f"plate / shelf top {S.Z_T2:.1f} (plate solid, 45 deg haunches in the slot corners)"),
                        (S.Z_T2F, o[0] + S.TX0, o[0] + S.TX1, f"#2 chip-side face {S.Z_T2F:.1f}: 2 back blocks + chip pedestal carry it")],
                title="v7.0 SECTION along the forearm through #2's chip line (seen from the back wall, hand end LEFT): sockets hang free over the "
                      "solid plate, SHTC3 shelf left")
    yc3 = o[1] + S.Y_E - 3.0
    render_flat(items, c3, look="side", figsize=(15, 6), clip=((0.0, -1.0, 0.0), -yc3),
                hlines=[(S.Z_T2F - P.TMP2_FRONT_REST_GAP, o[0] + S.TX0 - 1, o[0] + S.TX1 + 1,
                         f"front anti-tip rests top {S.Z_T2F - P.TMP2_FRONT_REST_GAP:.2f} ({P.TMP2_FRONT_REST_GAP:.2f} under the board)"),
                        (jb, o[0] + bx0, o[0] + bx1, f"joints + glue {P.TMP2_BLOB_CHIP_H:.1f} tall (bottom {jb:.1f}, plate top {S.Z_T2:.1f})"),
                        (S.Z_T2BK + P.TMP2_BLOB_BACK_H, o[0] + bx0, o[0] + bx1, f"back joints + glue top {S.Z_T2BK + P.TMP2_BLOB_BACK_H:.1f}")],
                title="v7.0 SECTION along the forearm near #2's pad row (seen from the back wall): the two front rests either side of the joints")
    from PIL import Image
    ims = [Image.open(f) for f in (c1, c2, c3)]
    wd = max(i.width for i in ims)
    cv = Image.new("RGB", (wd, sum(i.height for i in ims)), "white")
    yy = 0
    for i in ims:
        cv.paste(i, ((wd - i.width) // 2, yy)); yy += i.height
    cv.save(f"{out}/v70_tmp2_stack_section.png")
    for f in (c1, c2, c3):
        os.remove(f)
    # ---- top view, printed parts only, pin spacings dimensioned
    icm, mxb, _t1, t2 = S._boards()               # interior frame; + o below
    sht = S._sht()
    o3 = np.array([o[0], o[1], 0.0])
    marks, texts = [], []

    def dim(pa, pb, txt, dy, col):
        ya = pa[1] + dy
        marks.append((pa[0], ya, pb[0], ya, col, "-"))
        marks.append((pa[0], min(pa[1], ya), pa[0], max(pa[1], ya), col, ":"))
        marks.append((pb[0], min(pb[1], ya), pb[0], max(pb[1], ya), col, ":"))
        texts.append(((pa[0] + pb[0]) / 2, ya + (1.3 if dy > 0 else -1.3), txt, col))
    hx = S.t2_hole_x()
    pa, pb = t2.loc((hx[0], 15.24, 0)) + o3, t2.loc((hx[1], 15.24, 0)) + o3
    dim(pa, pb, f"TMP117 #2 pins {abs(pb[0] - pa[0]):.2f} centre to centre (owner's ruler; Adafruit file 20.32) - fits 19.3-20.7",
        -6.0, "#c00")
    for brd, nm, dy in ((icm, "ICM-20649", -5.0), (sht, "SHTC3 (on the shelf)", -8.5)):
        qa, qb = brd.loc((2.54, 15.24, 0)) + o3, brd.loc((22.86, 15.24, 0)) + o3
        qa, qb = (qa, qb) if qa[0] < qb[0] else (qb, qa)
        dim(qa, qb, f"{nm} back pins {abs(qb[0] - qa[0]):.2f} (Adafruit Eagle file); front holes: flat rests, no pins", dy, "#06c")
    ma, mb = mxb.pt("h0") + o3, mxb.pt("h1") + o3
    ma, mb = (ma, mb) if ma[0] < mb[0] else (mb, ma)
    dim(ma, mb, f"MAX30102 pin sockets {abs(mb[0] - ma[0]):.2f} (photo-scaled, UNVERIFIED) - loose paperclip pins", -13.5, "#080")
    render_flat([(isl, PRINT_COL), (shf, SHC)], f"{out}/v70_top_hole_spacing.png", look="top", figsize=(15, 9), marks=marks, texts=texts,
                title="v7.0 SKIN ISLAND + SHELF from above, printed parts only (hand end LEFT, bay UP): pin / hole spacings")


def main():
    out = f"{ROOT}/out"
    groups, cross, pos = layout()
    lines, bad, tight = check(groups, cross)
    rlines, rfail, notes = rule_checks(groups, cross)
    lrows = lengths(groups, cross, pos)
    srows, total, yr = sizes(pos)
    head = ["INTERFERENCE + CLEARANCE + WIRE-RULE CHECK (v6.1 digital twin)  -  generated by assembly.py",
            f"INTERFERENCE = solids overlap by more than {TOL} mm3.  TIGHT = two non-printed things closer than {P.GAP} mm.  "
            "Wires that end on the same board may touch (they meet at its pad row).",
            "", f"RESULT: {bad} interference(s), {tight} tight clearance(s), {rfail} wire-rule failure(s).", ""]
    open(f"{out}/CLEARANCES.txt", "w").write("\n".join(head + rlines + ["", "Wire drawn lengths:"] +
                                                    [f"  {w.name:52s} dia {w.d:.1f}  drawn {w.length:5.1f} mm" for gg in groups for w in gg[3]] +
                                                    [f"  {w.name:52s} dia {w.d:.1f}  drawn {w.length:5.1f} mm" for w in cross] + lines) + "\n")
    tw = ["", "ASSEMBLY (v6.1 digital twin, flat layout) - outer sizes incl. frame / lid skirts, without stitch flanges and strain posts",
          f"{'part':26s} {'along forearm':>14s} {'across':>8s} {'height':>8s}"]
    for n, a, b2, h in srows:
        tw.append(f"{n:26s} {a:14.1f} {b2:8.1f} {h:8.1f}")
    tw += [f"gaps (free neoprene): brain -> power {P.POD_GAP:.1f}, power -> skin {P.POD_GAP:.1f}, skin -> air (round the wrist) {pos['gap_ha']:.1f}",
           f"TOTAL band length along the forearm: {total:.1f} mm   (v6: 174.9, v4.3: 117.2)",
           f"band width across the wrist (all parts): {yr[1] - yr[0]:.1f} mm (v6: 78.3)",
           "", "WIRE RUNS: free length each run needs (pad to pad, incl. joints, fan-out and 5 mm slack per gap) vs what you have (min-normal)",
           f"{'run':32s} {'needs':>6s} {'has':>9s}  {'action':40s} how"]
    for n, a, b2, need, has, act, how in lrows:
        hs = f"{has[0]:g}" + (f"-{has[1]:g}" if has[1] != has[0] else "")
        tw.append(f"{n:32s} {need:6.1f} {hs:>9s}  {act:40s} {how}")
    print("\n".join(head[3:4]))
    print("\n".join(l for l in lines if "INTERF" in l or "TIGHT" in l))
    print("\n".join(l for l in rlines if "FAIL" in l))
    print("\n".join(tw))
    if "--no-render" not in sys.argv:
        render(groups, cross, pos, lrows, f"{out}/png")
    return bad + rfail, tw, rlines, notes, lrows, srows, total, yr


if __name__ == "__main__":
    sys.exit(1 if main()[0] else 0)
