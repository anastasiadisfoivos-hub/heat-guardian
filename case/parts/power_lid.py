"""v6 power lid (see parts/power.py for the layout and the reasons)."""
import power
PRINT_FLIP = True


def build():
    return power.build_lid()


REPORT = dict(power.REPORT) if "build_lid" == "build" else dict(note="print plate-down (top face on the bed), no supports")
