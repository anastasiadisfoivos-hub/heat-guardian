"""v6 brain pod (see parts/brain.py for the layout and the reasons)."""
import brain



def build():
    return brain.build()


REPORT = dict(brain.REPORT) if "build" == "build" else dict(note="print plate-down (top face on the bed), no supports")
