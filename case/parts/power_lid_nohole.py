"""v7-cover: see parts/screen_cover.py"""
import screen_cover
PRINT_FLIP = True

def build():
    return screen_cover.build_lid_nohole()


REPORT = dict(note="print top face down, no supports")
