"""Clearance test coupon (~15 min print). Count the dots: 2 dots = 0.2 mm ... 5 dots = 0.5 mm.
Row A (front): 4 board-edge slots for the 25.4 mm edge of an Adafruit board.
Row B: 4 locating pins for a 2.5 mm mounting hole (dia = hole - 2 x clearance).
Right: coin-motor pocket, 3.5 mm wire channel with tie post, MAX30102 window + light ring
(ring on top = skin side; the PCB pocket and blob relief are on the underside)."""
from geo import box, cbox, cyl, union, dots, rbox
import params as P


def build():
    T = 2.8                                   # plate thickness
    LX, LY = 74.0, 50.0
    plate = rbox(0, 0, 0, LX, LY, T, 2.0)
    add, cut = [], []

    # Row A: board-edge slots (25.4 x PCB_T) - push a board edge in, the snug one wins
    for i, c in enumerate(P.COUPON_CLEARS):
        y = 6 + i * 6.0
        cut.append(cbox(8 + 13.5, y, T - 2.0, P.ADA_L + 2 * c, P.PCB_T + 2 * c, T + 1))
        add.append(dots(2.0, y - 0.0, T, int(round(c * 10)), pitch=1.3, d=0.9))  # labels
    # Row B: locating pins
    for i, c in enumerate(P.COUPON_CLEARS):
        x = 10 + i * 8.0
        add.append(cyl(x, 36.0, T, T + P.PCB_T + 1.0, P.ADA_HOLE_D - 2 * c, seg=32))
        add.append(dots(x - (int(round(c * 10)) - 1) * 0.65, 42.5, T, int(round(c * 10)), pitch=1.3, d=0.9))

    # Motor pocket on a boss (floor 0.8 under the motor)
    mx, my = 50.0, 10.0
    boss_h = P.MOTOR_T + 0.2 + 0.8
    add.append(cyl(mx, my, 0, boss_h, P.MOTOR_D + 2 * P.CLEAR + 2 * 1.6))
    cut.append(cyl(mx, my, 0.8, boss_h + 1, P.MOTOR_D + 2 * P.CLEAR))
    cut.append(box(mx - P.MOTOR_LEAD_NOTCH_W / 2, my, boss_h - P.MOTOR_LEAD_NOTCH_D, mx + P.MOTOR_LEAD_NOTCH_W / 2,
                   my + 8, boss_h + 1))   # lead notch

    # Wire channel rib with strain-relief post
    add.append(box(62, 3, 0, 70, 30, T + 1.5))
    cut.append(box(66 - P.WIRE_CH_W / 2, 2, T + 1.5 - P.WIRE_CH_D, 66 + P.WIRE_CH_W / 2, 31, T + 3))
    add.append(cyl(66, 25, T + 1.5 - P.WIRE_CH_D, T + 1.5, P.TIE_POST_D, seg=24))

    # MAX30102 seat test = the exact seat used in the heart island, flipped (ring up, PCB pocket underneath)
    from common import max_seat
    madd, mcut, ring, info = max_seat(0, 0, +1)
    seat = (madd - mcut) + ring
    h = info["max_seat_top"]
    seat = seat.mirror([0, 0, 1]).translate([56.0, 38.0, h])
    sb = seat.bounding_box()
    cut.append(box(sb[0] - 0.01, sb[1] - 0.01, -1, sb[3] + 0.01, sb[4] + 0.01, T + 1))

    part = union([plate] + add) - union(cut)
    return part + seat
