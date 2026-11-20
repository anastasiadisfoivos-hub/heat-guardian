"""v6.2 MAX30102 light shield: a 0.6 mm plate that drops into the flush recess on the skin island's skin side, under the MAX30102.
It closes the relief for the MAX's sensor-side joints + glue, so the skin side is smooth and light-tight except the optical window.
Print in BLACK (or opaque) PETG, flat on the bed; glue its edge in the recess ledge (or use black electrical tape instead)."""
import island_skin as S
import params as P


def build():
    return S.build_shield(in_place=False)


REPORT = dict(note=f"{P.MAX_SHIELD_T} mm plate, only the optical window open ({P.MAX_WIN_L:.1f} x {P.MAX_WIN_W:.1f}); print black, flat, no supports")
