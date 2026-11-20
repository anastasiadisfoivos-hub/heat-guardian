"""Round-4 V19-dry experiments (SIMULATION). Small batch: healthy tercile of the first 200 DEV persons.
Usage: python3 -I tools/r4_v19dry.py HR_PLATEAU=pre_ramp,HR_AMB_SPAN=14,HR_AMB_TAU=5,LOC_GAIN=0
All knobs default to the v3 behaviour (LOC_GAIN 0, HR_AMB_SPAN 1e9, HR_AMB_TAU 30, HR_PLATEAU ramp30_40)."""
import sys, numpy as np
import velders.body as B
import velders.protocols as PR
from velders.protocols import load_persons, psu, meade
from velders.validate import healthy, thirst_policy_factory, section_rest, section_limits
P=healthy(load_persons(idx=slice(0,200)))   # small batch: healthy tercile of first 200 DEV persons
def v19(P):
    x=psu(P,'humid',36,'adl'); lead=(x['inflection_min']-x['hr_onset_min'])*0.2*100/np.exp(18.6686-4030.183/(36+235.0))
    y=psu(P,'dry',12,'adl'); lt=(y['inflection_min']-y['hr_onset_min'])*0.2
    return np.mean((lead>=2)&(lead<=6)), np.nanmedian(lead), np.mean(lt>0), np.nanmedian(lt), np.nanmean(y['T_crit'])
for spec in sys.argv[1:]:
    for kv in spec.split(','):
        k,v=kv.split('='); (setattr(PR,k,v) if k=='HR_PLATEAU' else setattr(B,k,float(v)))
    h=v19(P)
    R={T:meade(P,T,drink_policy=thirst_policy_factory(P)) for T in (22,36)}
    hr=(R[36]['HR'][-60:].mean()-R[22]['HR'][-60:].mean())+60; d=(R[36]['dcore']-R[22]['dcore']).mean()
    print(spec, 'V19hum %.0f%% med %.1f | V19dry HRfirst %.0f%% med %+.1f Tcrit %.1f | V4@36 %.1f | V2@36 %+.2f'%(100*h[0],h[1],100*h[2],h[3],h[4],hr,d), flush=True)
