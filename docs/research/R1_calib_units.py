import numpy as np
from pythermalcomfort.models import two_nodes_gagge_ji, two_nodes_gagge
from pythermalcomfort.utilities import body_surface_area
from pythermalcomfort.psychrometrics import p_sat_torr

w,h = 72.0, 1.68
bsa = body_surface_area(weight=w, height=h)
print("BSA (DuBois) =", round(bsa,3), "m2")
# ASHRAE met conversions
for met in [0.8,1.0,1.2,1.5,2.0,2.7]:
    Wm2 = met*58.2
    Wtot = Wm2*bsa
    vo2 = Wtot/20.9*60/1000  # L/min  (20.9 kJ/L)
    print(f"met={met}: {Wm2:.1f} W/m2, {Wtot:.0f} W total, VO2={vo2*1000:.0f} mL/min = {vo2*1000/w:.2f} mL/kg/min")

print()
print("8 h seated, 45% RH, v=0.1, clo=0.4  (Ji older model)")
for tdb in [22,26,31,36]:
    vp = 45*p_sat_torr(tdb=tdb)/100
    r = two_nodes_gagge_ji(tdb=tdb, tr=tdb, v=0.1, met=1.0, clo=0.4, vapor_pressure=vp,
        body_surface_area=bsa, position="sitting", acclimatized=False,
        body_weight=w, length_time_simulation=480, initial_core_temp=36.8, initial_skin_temp=33.5)
    tc=np.array(r.t_core); ts=np.array(r.t_skin)
    print(f"  Tdb={tdb}: core {tc[0]:.2f}->{tc[-1]:.2f} (d={tc[-1]-tc[0]:+.2f}), skin {ts[0]:.2f}->{ts[-1]:.2f}")
print()
print("Same with the YOUNG Gagge model (2h max useful; run 480 min):")
for tdb in [22,26,31,36]:
    vp = 45*p_sat_torr(tdb=tdb)/100
    r = two_nodes_gagge(tdb=tdb, tr=tdb, v=0.1, met=1.0, clo=0.4, vapor_pressure=vp,
        body_surface_area=bsa, round_output=False)
    print(f"  Tdb={tdb}: core {r.t_core:.2f}, skin {r.t_skin:.2f}, w={r.w:.2f}, m_bl={r.m_bl:.1f}")
