"""Cable-guide fit test (~10 min): one groove with a 90 deg arc at CABLE_BEND_R, snap lips at
CABLE_LIP_PITCH, a flared + filleted exit through a wall, and the outside strain-relief post.
Press the real 4-wire bundle in: it should click under the lips and lie in the curve without kinking."""
from geo import box, rbox, union
import params as P
from guides import guide, flared_exit, exit_post

T = 1.2
WALL_X0, WALL_X1 = 26.0, 26.0 + P.WALL


def build():
    plate = rbox(0, 0, 0, 30.0, 24.0, T, 2.0)
    wall = box(WALL_X0, 6.0, 0, WALL_X1, 24.0, T + P.CABLE_CH_D + 1.0)
    ga, gc = guide("test: arc + lips + exit", [(2.0, 3.5), (12.0, 3.5), (12.0, 15.0), (WALL_X1 + 0.5, 15.0)], T)
    col, ec, xo = flared_exit(WALL_X0, WALL_X1, 15.0, T)
    body = union([plate, wall, col, ga, exit_post(xo, 15.0, T, +1)])
    return body - gc - ec
