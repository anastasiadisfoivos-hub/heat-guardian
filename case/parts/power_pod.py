"""v6 power pod (see parts/power.py for the layout and the reasons)."""
import power



def build():
    return power.build()


REPORT = dict(power.REPORT) if "build" == "build" else dict(note="print plate-down (top face on the bed), no supports")
