#!/usr/bin/env python3
"""[B5-v7] Why ev385 "family" fell f6 -> f7 on the SIM-DEV v5 check set: the eval counts a family alert only in [-45, +16) min of the
core-38.5 onset; freeze-7 often alerts the family EARLIER and the Danger stays on until the event. Counts both. usage: b5v7_family_window.py <eval_b5v7 --dump dir>"""
import numpy as np, glob, os, sys
S=sys.argv[1]
for hk in ('hr_raw','hr_scaled'):
  tot={'f6':[0,0,0],'f7':[0,0,0]}; n=0
  for f6 in sorted(glob.glob(S+'/p*_f6_%s.npz'%hk)):
    o={'f6':np.load(f6),'f7':np.load(f6.replace('_f6_','_f7_'))}
    tc=o['f6']['T_core']; dt=o['f6']['dtype']
    s=np.where((tc>=38.5)&(np.concatenate([[0],tc[:-1]])<38.5))[0]
    for x in s:
      if not str(dt[x]).startswith('S2'): continue
      n+=1
      for k,a in o.items():
        aid=a['alarm_id']; cm=a['check_min']; lv=a['level']
        f=np.where((aid!=np.concatenate([[aid[0]],aid[:-1]]))&(cm!=255))[0]
        inwin=any(x-45<=i<x+16 for i in f)
        # covered: a family alert at i <= x+16 and level>=3 on every minute from i to min(x, ...) (alert still standing at the event)
        cov=inwin or any(i<x-45 and i>=x-480 and (lv[i:x+1]>=3).all() for i in f)
        tot[k][0]+=inwin; tot[k][1]+=cov
  print(hk,'S2 core-38.5 events',n, {k:'in-window %d, standing-or-in-window %d'%(v[0],v[1]) for k,v in tot.items()})
