"""v6 brain frame (see parts/brain.py for the layout and the reasons)."""
import brain
PRINT_FLIP = True


def build():
    return brain.build_frame()


REPORT = dict(brain.REPORT) if "build_frame" == "build" else dict(note="print plate-down (top face on the bed), no supports")
