"""v6.1 hardware actions (re-solders, splices, checks) and design warnings, computed from params.py and the twin.
-> out/WARNINGS.txt"""
import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "parts")]
import numpy as np
import params as P
import brain as B, power as W, island_skin as S, island_air
import spacing


def collect():
    import assembly
    groups, cross, pos = assembly.layout()
    lrows = assembly.lengths(groups, cross, pos)
    rlines, rfail, notes = assembly.rule_checks(groups, cross)
    srows, total, yr = assembly.sizes(pos)
    R = {r[0].split("  ")[0].split(" (")[0].strip(): r for r in lrows}
    out = []
    a = out.append
    n = [0]

    def act(t):
        n[0] += 1
        a(f"{n[0]:2d}. {t}")
    a("HARDWARE ACTIONS (do these before you assemble) - Heat Guardian stage 1, v7.0 FINAL EDITION (two pods + skin island + SHTC3 shelf)")
    a("")
    act("MEASURE THE BEND RADIUS (everything is laid out for it). Bend a spare 4-wire bundle with a joint + glue blob at one end "
        "around round things (pencil = 8 mm dia, marker = 15 mm dia). The smallest RADIUS it takes without forcing is WIRE_BEND_R "
        f"(now {P.WIRE_BEND_R:.0f} mm, a guess); one loose wire / a flat ribbon -> WIRE_BEND_R_SINGLE (now {P.WIRE_BEND_R_SINGLE:.0f} mm). "
        "Put both in params.py and run python3 build.py.")
    a("")
    a("    WIRE TABLE - needs = free length pad to pad in the twin; has = what you measured (shortest, normal).")
    a(f"    {'run':34s} {'needs':>6s} {'has':>11s}  action / how it is laid")
    for r in lrows:
        h = f"{r[4][0]:g}" if r[4][0] == r[4][1] else f"{r[4][0]:g}-{r[4][1]:g}"
        a(f"    {r[0]:34s} {r[3]:6.1f} {h:>11s}  {r[5]}  [{r[6]}]")
    a("")
    sc = [r for r in lrows if r[0].startswith("screen wires")][0]
    rb = [r for r in lrows if "blue" in r[0]][0]
    if P.LCD_GARAGE:
        act(f"SCREEN CABLE (v6.5): NO re-solder. The 7 wires to the 5V/GND/3V3/D10/D9/D8/D7 row keep their 45-50 mm. The brain pod has a "
            f"WIRE GARAGE on the 5V-row side ({B.YI - (B.Y_5V + P.PAD_ROOM):.1f} mm more across the wrist). Lay the 7 wires side by side like "
            f"a flat ribbon: from the castellations they go OUT (away from the XIAO) and down to the garage floor, make ONE fold "
            f"(radius ~{B.GAR_R:.1f} for 45 mm wires, ~{B.GAR_R_MAX:.1f} for 50 mm: the fold just stands a little taller), and come back "
            "at plug height, straight over the XIAO into the plug. Nothing bunches under the screen. Glue the floor leg to the garage floor "
            "(one dot, mid-floor) and the fold's far end against the end wall. Do not crease the fold.")
        act(f"SCREEN BLUE WIRE (to the D row): its shortest route (tight U-turn R{P.WIRE_BEND_R_SINGLE:.0f} right at the plug, then diagonal "
            f"down to D6) needs {rb[3]:.1f} mm incl. 1 mm into the joint. If the blue is the 25 mm wire it is {rb[3] - 25:.1f} mm short of "
            "that: make its first U-turn a little tighter (~R3.5) or tuck 0.3 mm less into the joint - no splice. Modelled on D6; each pad "
            "further toward the USB end costs 2.5 mm more.")
    else:
        act("SCREEN CABLE (8 wires) - RE-SOLDER AT THE XIAO END ONLY (unavoidable: with an 8 mm bend the 45-50 mm wires would need a "
            "~28 mm tall pod or a ~58 mm wide one - there is nowhere to put 35 mm of spare per wire over the XIAO). Leave the plug in the "
            "screen. Unsolder one wire at a time, note its pad, put it back on the SAME pad. The 7 wires to the 5V/GND/3V3/D10/D9/D8/D7 row "
            f"are cut to about {sc[3]:.0f} mm (11-13), each with ONE gentle bend; strip 1.5 mm and solder it rising at ~{P.SCREEN_WIRE_ANGLE:.0f} deg, "
            "pointing inward over the board. Best: fit the XIAO and screen in the printed pod and cut to fit.")
        rb = [r for r in lrows if "blue" in r[0]][0]
        act(f"SCREEN BLUE WIRE: re-solder too, {rb[3]:.0f} mm free, ONE U-turn (radius {P.WIRE_BEND_R_SINGLE:.0f}) down the far-end side to its "
            "D pad (modelled on D6). If the 25 mm 'shortest' wire is the blue one, it is 3 mm short: splice it, or move it to a 45-50 mm wire.")
    if assembly.SLEEVES:
        (n1, l1, a1, b1), (n2, l2, a2, b2) = assembly.SLEEVES
        act(f"SPLICE SLEEVES (v6.5, your photo): no sleeve may sit inside the brain pod, and they cannot bend. Each lies straight from "
            f"just outside the brain pod's elbow opening, across the gap, into the power pod. HOP 1: the straight lane is {l1:.0f} mm "
            f"long, {a1:.0f}-{b1:.0f} mm from the XIAO pad (along the wire). BATTERY LEADS: only {l2:.0f} mm, {a2:.0f}-{b2:.0f} mm from the "
            "XIAO pad (the cell fills the power pod right behind the hand wall). Check where your sleeves are: a sleeve that is longer, "
            "or sits elsewhere, does not fit. Fix without soldering: slit the long heat-shrink off and put a short piece (8-10 mm) over "
            "just the joint, inside its lane. Glue each wire just inside both openings (floor, 3 mm in from the wall), not on the sleeve. A sleeve "
            "across the gap stiffens that hinge a little.")
    if P.AIR_ON_TOP:
        act(f"HOP 5 + THE SHTC3 (v6.6, your dry fit): TMP117 #2 now sits STRAIGHT ABOVE #1, chip DOWN like #1, pad edges aligned - each "
            f"of the 4 wires goes from its pad on #1 out past the edge, straight up and onto the same pad on #2 (no crossing, no lateral "
            f"run). Needed: {S.H5_LEN:.1f} mm per wire incl. 1 mm into each joint (v6.9: 16.7; your shortest is 20). "
            "If your #2 must stay chip UP, its pads mirror and the outer wires need ~6 mm more. "
            + (f"v6.8: the SHTC3 sits on the drop-in SHELF (island_shelf.stl) over the MAX30102, on the same upper floor as #2 (shelf top "
               f"{S.Z_SH1:.1f} = #2's plate top), sensor UP, pads toward the bay, on 4 flat bosses, pins in the 2 back holes only ({P.SHELF_STANDOFF:.1f} mm still air "
               f"under it). Hop 6 (60 mm) makes ONE C (radius ~{S.R6:.0f}) over the bay, leaning {P.H6_TILT:.0f} deg up, from #2's pads to the "
               "SHTC3's pads. The old cage on #2 (island_air.stl) is not used. "
               + (f"v7.0: NO RE-SOLDER on #2 - fit it with its wires as they are. The plate under it is now SOLID "
                  f"({S.Z_T2 - S.Z_SLOT1:.1f} mm, no pockets: the v6.9 0.3-0.4 mm pocket floors broke). #2 stands 0.8 mm higher: its chip-side "
                  f"joints + glue (up to {P.TMP2_BLOB_CHIP_H:.1f} mm) and its two sockets hang free {S.Z_T2F - P.TMP2_BLOB_CHIP_H - S.Z_T2:.1f} mm over the plate; "
                  f"back-side joints + glue (up to {P.TMP2_BLOB_BACK_H:.1f} mm) are in open air. The board sits on two BACK BLOCKS (one 1.8 mm pin "
                  f"each, {P.TMP2_HOLE_DX:.1f} mm apart = your measurement) and its chip lies flat on a chip pedestal; two front rests "
                  f"{P.TMP2_FRONT_REST_GAP:.2f} mm under the front corners stop it tipping when you press the pad edge. If a chip-side joint + glue blob "
                  f"is taller than {P.TMP2_BLOB_CHIP_H:.1f} mm the board rocks on it: trim the glue, not the joint."
                  if getattr(P, "TMP2_BLOB_CHIP_H", 0) else "") if S.SHELF else
               f"The SHTC3 rides on top in a vented cage (glue its 4 keyed feet onto #2's plate): {P.AIR_GAP_OVER_T2:.0f} mm still air over #2, "
               f"open on all sides and on top; its pocket is the board + {P.AIR_POCKET_CLEAR} mm per side with {P.AIR_PAD_ROOM} mm extra at the "
               "pad edge for the joints + glue, and it drops straight in from the top. Hop 6 (60 mm) makes ONE loop "
               f"(radius ~{S.R6:.0f}) standing in front of the stack, up to the SHTC3's pads."))
    else:
        act("HOP 5 (TMP117 #1 -> #2 through the 3 mm neoprene): it fits in 20 mm only as a FLAT ribbon C at the pad edge. The twin needs "
            f"{R['hop 5'][3]:.1f} mm with a {P.WIRE_BEND_R_SINGLE:.0f}-4.6 mm ribbon bend - 2.2 mm more than your shortest wire. Splice each 20 mm "
            "wire to 25 mm (+5, joint heat-shrunk, joints staggered); the 30 mm wires are fine as they are (the C just gets rounder). "
            "As a round R8 bundle it would need ~40 mm and an ~18 mm tall loop over the stack - do not do that.")
    act("HOP 2 and the BUTTON PAIR are within 0.4 / 0.8 mm of your shortest wire (after the 5 mm slack each gap gets): measure those two exact wires again. If one is "
        "shorter than the table, splice it +5 mm.")
    act("All other runs (hop 1, battery, hops 3/4/6) are used AS THEY ARE: the spare is taken up inside the parts - hops 3 and 4 as "
        "ONE wide C each in the skin island's open bay (glue points at each C), hop 6 as one 25 mm jog (two R8 turns) over the bay, "
        "hop 1 / battery as straight runs with the 5 mm spare in the gap. Lay each wire in from above; glue only at the points listed in ASSEMBLY.md.")
    act("BATTERY: cell in the power pod, lead end at the hand wall, leads at the LANE-SIDE corner (turn the cell over if they come out "
        "of the other corner). Leads go straight out through the hand-wall opening under the XIAO. Do not glue the cell.")
    rb = R["HELP button pair"]
    act("HELP BUTTON: the switch sits in the power pod (glued in the lid's 5.6 x 5.6 through-hole); its pair runs straight into the "
        "brain pod and along the XIAO's D-row edge. It is wired D2 -> GND (D5 is SCL, never the button). NOTE: the brain-pod twin "
        f"still draws the pair's end at D5 ({rb[3]:.1f} mm needed there); D2 is 3 pads (7.6 mm) further toward the USB end, so the run "
        f"to D2 needs about {rb[3] + 3 * 2.54:.1f} mm vs your {P.BTN_LEN_M[0]:g} mm - if your pair is already soldered to D2 and reaches "
        "in the dry fit, ignore this; if not, splice +10 mm.")
    act("XIAO: parts up, USB-C toward the plug tunnel, dropped straight down between its 4 corner blocks (0.4 mm per side). Try your USB-C "
        "cable BEFORE gluing. Glue ONLY at the two far-end corners (away from the USB-C): never at the USB end, never near the reset button.")
    act("DRV2605L: open its 'I2C PU' jumper; motor in its cup, leads through the notch.")
    if S.BACK:
        act(f"MAX30102 (v6.3): RE-SOLDER ITS 7 WIRES ON THE BACK (the side away from the skin). Unsolder each wire from the sensor side, "
            "clean the pads there flat with wick (nothing may stand more than 0.5 mm on the sensor side besides the factory parts), and "
            f"solder it from the back, pointing toward the pad edge (the bay). Joints + glue on the back may stand up to {P.MAX_BLOB_H} mm and "
            f"reach {P.MAX_BLOB_STRIP} mm in from the pad edge: the island leaves {P.MAX_BACK_ROOM_H:.0f} mm free there and {P.PAD_ROOM:.0f} mm "
            f"pad room toward the bay. v6.4: the board drops so the optical chip stands {P.MAX_CHIP_PROUD} mm PAST the skin surface "
            f"(v6.3: 0.55 mm back). Its taller factory parts sit in their own pockets; {sum(1 for _, _, t in S.part_pockets(S._boards()[1]) if t)} "
            f"of them go through the skin face (the tantalum caps are 1.6 mm, taller than the 1.55 mm chip, so they stand ~0.1 mm past the "
            f"skin too). LIGHT: those pockets have a {P.MAX_PART_CLEAR} mm gap round each part (the part positions come from photos). If the "
            "PPG reading is noisy in daylight, put one strip of black electrical tape over the MAX area on the skin side with only the "
            "optical window cut out, or fill the gaps with black nail varnish after the board is in. "
            f"The pocket is +{P.MAX_POCKET_LOOSE} mm per side looser than v6.1. Before gluing, drop the board in and check it sits flat "
            "on its three pads: if a part hits a pocket edge, tell me which (positions are from photos). v7.0: glue the MAX ONLY in the two "
            "glue wells at its back corners (notches in the back ledge, over its two pin holes) - never on the pad edge side of the window.")
    else:
        act(f"MAX30102 (v6.2 option): no re-solder; joints + glue on the sensor side sit in a relief closed by max_shield.stl "
            f"(print black); the sensor face then sits {S.Z_MF:.2f} mm above the skin.")
    act("SKIN ISLAND - the v4 board jobs still apply: TMP117 #1 sits chip DOWN in a floor window - flatten its chip-side joints to "
        f"<= {S.Z_T1F:.1f} mm; nail varnish over its ripped GND pad; TMP117 #2 ADDR jumper closed (0x49). TMP117 #1's two GND tails are single wires in the side channels (radius 4): their length was not measured - "
        "allow ~15 mm each.")
    a("")
    a("DESIGN WARNINGS")
    a("")
    for nt in notes:
        a(f" - BEND BELOW THE BUNDLE RULE (single-wire rule used): {nt}.")
    a(f" - BAND LENGTH: {total:.1f} mm along the forearm (v6: 174.9, v4.3: 117.2). The spare wire is NOT spent as band length - it "
      "sits in the C bays and the hop 6 jog inside the skin island. The band is long because nothing is stacked any more: the ICM, "
      "MAX30102 and TMP117 stack lie side by side in one row in the skin island, each with 5 mm pad room. Getting back to ~117 would "
      "need the ICM stacked over another board again (the v4 problem).")
    a(f" - BAND WIDTH: {yr[1] - yr[0]:.1f} mm across (the air island sits beside the skin island, toward the outer side).")
    a(f" - POWER POD is short ({W.OX:.1f} mm) on purpose: hop 1 + hop 2 together must span it, and your hop 2 shortest is 45.")
    a(" - WIRE OPENINGS: every exit is >= 10 mm wide (most 16), full height, open from the top, R2 edges; the lid/frame bridges each "
      "opening. They are red in the renders.")
    if getattr(P, "BOARD_FIT_PLUS", 0):
        a(f" - BOARD SEATS LOOSER (v6.9, your v6.8 print: 'the columns were a tiny bit too close, the sensor couldn't sit'): every wall, lip, "
          f"stop and socket pocket that locates a board in the skin island and the SHTC3 shelf is {P.BOARD_FIT_PLUS:.1f} mm per side wider than "
          f"v6.8, and every printed pin into a board hole is {P.PIN_SHRINK_ISLAND:.1f} mm thinner ({P.ADA_HOLE_D - P.PIN_UNDERSIZE:.1f} -> "
          f"{P.ADA_HOLE_D - P.PIN_UNDERSIZE - P.PIN_SHRINK_ISLAND:.1f} mm). The boards can now move ~0.35 mm on their pins: press each one to its "
          "pad-edge side (toward the bay) before the glue dot sets. Brain pod, power pod and lids are unchanged.")
    a(" - SCREEN PIN ORDER and the blue wire's D pad are assumptions; lengths cover +/- 3 mm. The button is on D2 (owner, v6.8).")
    a("")
    a("v7.0 FINAL EDITION - CHECK THESE WITH A DRY FIT BEFORE ANY GLUE")
    a("")
    a(f" - NOTHING THIN ANY MORE: every wall, floor, web, rib and lip is >= {P.MIN_T} mm (build.py now fails otherwise: out/FRAGILITY.txt). "
      f"Floors 1.0 / 0.8 / 0.6 -> 1.2 everywhere; the 0.4 mm glue recesses in the floors are gone (glue points are listed in ASSEMBLY.md). "
      f"The ONLY features under {P.MIN_T}: (1) the floor under TMP117 #1, {S.Z_T1F:.1f} mm - its chip is 0.8 mm tall and must stand "
      f"{P.TMP_CHIP_PROUD} mm past the skin face; it is printed on the bed and now welded to two pillars at its front corners. Do not lever on it: "
      f"slide TMP117 #1 in flat from the bay. (2) the floor under the MAX30102, 0.8-1.05 mm - its optical chip must stand {P.MAX_CHIP_PROUD} mm past the skin.")
    a(f" - TMP117 #2 HOLE SPACING: the two pins are {P.TMP2_HOLE_DX:.1f} mm apart (your ruler measurement). Adafruit's own board file says 20.32 mm. "
      "The pins are 1.8 mm in 2.5 mm holes with a FLAT seat (the old centring cones are gone), so any spacing from 19.3 to 20.7 mm drops on. "
      "If it still does not drop on, do not force it: tell me the measured spacing and which side binds.")
    a(f" - TMP117 #2 STANDS 0.8 mm HIGHER (board {S.Z_T2F:.1f}-{S.Z_T2BK:.1f} mm above the skin): hop 5 now needs {S.H5_LEN:.1f} mm per wire (v6.9: 16.7). "
      "Your shortest hop-5 wire is 20 mm, so 2.5 mm spare - check in the dry fit that all four reach WITHOUT pulling on a pad.")
    a(f" - MAX30102 BACK-SIDE JOINTS: the shelf is 1.2 mm thick now (was 1.0), so joints + glue on the MAX back may stand at most {P.MAX_BLOB_H} mm "
      f"({P.MAX_BACK_ROOM_H - P.MAX_BLOB_H:.1f} mm spare under the shelf at the hand end, was 0.6). If the shelf rocks, trim that glue.")
    _pk = S.part_pockets(S._boards()[1])
    a(f" - MAX30102 PART POCKETS: {sum(1 for _, _, t in _pk if t)} of the {len(_pk)} part pockets now go right through the skin face (v6.9: 4). The three "
      "that kept a 0.45 mm skin were too thin to keep. More small openings round the optical window: if the pulse signal is noisy in daylight, cover the MAX area on the "
      "skin side with black tape with only the window cut out (as before).")
    a(f" - COVER + LID FIT: 0.3 mm per side now (was 0.2) with a lead-in chamfer on the skirt edge: they slide on and are glued, not pressed. "
      f"The power lid plate is {P.LID_T} mm (was 1.2) so {P.LID_T - P.BTN_DISH_DEPTH:.1f} mm stays under the finger dish; the pod walls are 0.5 mm lower, the "
      "lid top is 0.2 mm higher. The switch position has not changed.")
    a(" - XIAO SEAT: four solid corner blocks (two run into the hand wall) replace the thin rest columns. The XIAO must drop straight down "
      "between them with its wires on. UNVERIFIED on real hardware: if heat-shrink or a glue blob sits within 1.3 mm of a short end on the long edges (or under a corner), it "
      "will sit on a block - trim the glue, or tell me which corner.")
    a(" - SCREEN POSTS are tied into the pod corners now (solid corner gussets). If a wire was routed through that corner, route it beside the gusset.")
    a(" - SHELF: drops onto the back ledge over two keys (3 x 1.5 mm) that show through two holes in the shelf; 0.4 mm play per side. "
      "It goes in AFTER the MAX30102 and its wires.")
    if S.SHELF:
        a(f" - SHTC3 SELF-HEATING / WRONG-AIR RISK (v6.8 shelf over the MAX30102): the SHTC3 now sits {S.Z_SHB:.1f} mm above the skin "
          f"(v6.6 cage: {S.Z_SB:.1f}) and right over the MAX30102. The shelf is a solid {P.SHELF_T:.1f} mm PETG plate (a thermal + sweat barrier) on "
          f"thin seats at the walls, with {P.SHELF_STANDOFF:.1f} mm still air under the board, vent slots in the back and hand lips and the "
          "bay side open, the sensor face up in free air. Expect it to read WARM in still air: skin heat (~33-34 C) rises through 6 mm of "
          "PETG + air, the MAX30102's LEDs add a little while they pulse, and the SHTC3's own heating is tiny at a 1 reading/s duty. A "
          "rough guess is +0.5 to +2 C over room air when the wrist is still, less with any air movement; humidity reads LOW by the same "
          "temperature offset (~3 %RH per 1 C). Calibrate against a reference thermometer with the band worn (and read the SHTC3 at "
          "most once every few seconds); if the offset is large or drifts with the PPG duty, moving the SHTC3 off the skin island again "
          "(a separate side island, as in v6.1) is the fallback.")
    return out


if __name__ == "__main__":
    print("\n".join(collect()))
