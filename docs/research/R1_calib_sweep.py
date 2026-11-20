import numpy as np, itertools
from pythermalcomfort.models import two_nodes_gagge_ji
from pythermalcomfort.utilities import body_surface_area
from pythermalcomfort.psychrometrics import p_sat_torr
w,h=72.0,1.68; bsa=body_surface_area(weight=w,height=h)
meas_core={22:0.0,26:0.2,31:0.7,36:0.9}
meas_skin={22:31.7,26:32.9,31:34.9,36:35.9}
print("clo  met   Tdb  dCore_model  dCore_meas  Tsk_model  Tsk_meas")
for clo,met in itertools.product([0.3,0.4,0.5],[1.0,1.1,1.2]):
    rows=[]
    for tdb in [22,26,31,36]:
        vp=45*p_sat_torr(tdb=tdb)/100
        r=two_nodes_gagge_ji(tdb=tdb,tr=tdb,v=0.1,met=met,clo=clo,vapor_pressure=vp,
            body_surface_area=bsa,position="sitting",acclimatized=False,body_weight=w,
            length_time_simulation=480,initial_core_temp=36.8,initial_skin_temp=33.5)
        tc=np.array(r.t_core);ts=np.array(r.t_skin)
        rows.append((tdb,tc[-1]-tc[0],ts[-1]))
    base=rows[0][1]
    for tdb,dc,ts in rows:
        print(f"{clo:4.1f} {met:4.1f} {tdb:5d} {dc-base:+11.2f} {meas_core[tdb]:+11.1f} {ts:10.2f} {meas_skin[tdb]:8.1f}")
    print()
