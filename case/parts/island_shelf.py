"""v6.8 SHTC3 SHELF: separate drop-in part for the skin island (see island_skin.build_shelf).  Sits over the MAX30102 at the level of
TMP117 #2's plate; the SHTC3 rides on it, sensor up.  Prints plate-down as modelled (lips, posts and pins grow up): no supports."""
import island_skin as S

REPORT = {}


def build():
    m = S.build_shelf().translate(list(S.OFF))
    REPORT.clear()
    REPORT.update(shelf_top=round(S.Z_SH1, 2), underside=round(S.Z_SH0, 2), shtc3_bottom=round(S.Z_SHB, 2),
                  lip_top=round(S.Z_LIP, 2), seat=f"{S.SX1 - S.SX0 + 2 * S.P.SHTC3_FIT:.1f} x {S.SY1 - S.SY0 + S.cb:.2f} (+{S.P.SHTC3_FIT:.1f} fit)",
                  pin_d=round(S.P.ADA_HOLE_D - S.P.PIN_UNDERSIZE - S.PSH, 2))
    return m


SECTION_Y = S.Y_E - 8.89 + S.OFF[1]
