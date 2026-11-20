"""v7-cover: see parts/screen_cover.py"""
import screen_cover


def build():
    return screen_cover.build_lid_plug()


REPORT = dict(note="print as exported, no supports")
