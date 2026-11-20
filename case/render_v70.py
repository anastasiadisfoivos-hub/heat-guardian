"""v7.0 overview pictures of the PRINT files (out/stl_flat/*.stl, as they lie on the bed): out/png/v70_<part>.png"""
import os, sys
import numpy as np, trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from render import _draw
ROOT = os.path.dirname(os.path.abspath(__file__))
NOTE = {"brain_pod": "skin side on the bed. XIAO corner blocks (2 tied into the hand wall), screen posts tied into the corners",
        "brain_frame": "window face on the bed. Skirt with lead-in chamfer, stops, reset notch",
        "power_pod": "skin side on the bed. Motor cup, 2 DRV posts with flared feet, battery cradle, button bar",
        "power_lid": "top face on the bed. 1.7 plate (1.2 under the finger dish), 5.6 x 5.6 switch hole",
        "island_skin": "skin side on the bed. ICM bosses, MAX pocket + shelf ledge with 2 keys, TMP stack: solid plate, back blocks, chip pedestal, front rests",
        "island_shelf": "plate on the bed. 1.2 plate, 4 bosses (2 with pins), lips with lead-in, 2 key holes"}


def main():
    for n, note in NOTE.items():
        tm = trimesh.load(f"{ROOT}/out/stl_flat/{n}.stl")
        d = tm.bounds[1] - tm.bounds[0]
        fig = plt.figure(figsize=(15, 7), dpi=120)
        for i, (el, az, lab, zs) in enumerate(((32, -58, "as printed, from the front-left", 0), (90, -90, "from above (print orientation)", 1))):
            ax = fig.add_subplot(1, 2, i + 1, projection="3d", proj_type="ortho")
            ax.view_init(elev=el, azim=az)
            _draw(ax, tm, lab, zsign=zs)
        fig.suptitle(f"v7.0 {n}.stl  -  {d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm on the bed, {tm.volume / 1000:.2f} cm3 (~{tm.volume / 1000 * 1.27:.1f} g PETG solid)\n{note}", fontsize=11)
        fig.savefig(f"{ROOT}/out/png/v70_{n}.png", bbox_inches="tight")
        plt.close(fig)
        print("wrote", f"out/png/v70_{n}.png")


if __name__ == "__main__":
    main()
