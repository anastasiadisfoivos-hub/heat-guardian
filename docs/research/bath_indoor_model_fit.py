import pandas as pd, numpy as np, warnings; warnings.filterwarnings("ignore")
d="/home/claude/hgdata/raw/22_bath_elderly_homes/"
def load(f):
    df=pd.read_csv(d+f,encoding="utf-8-sig"); df["t"]=pd.to_datetime(df["Timestamp"],dayfirst=True,errors="coerce"); return df.set_index("t").drop(columns="Timestamp").apply(pd.to_numeric,errors="coerce")
br=load("Phase 2 and 4 BR.csv"); lr=load("Phase 2 and 4 LR.csv")
ext=pd.read_csv(d+"ExternalWeatherSummer.csv",header=None,encoding="utf-8-sig",names=["t","Tout"]); ext["t"]=pd.to_datetime(ext["t"],utc=True).dt.tz_convert("Europe/London").dt.tz_localize(None); ext=ext.set_index("t")["Tout"].sort_index()
grid=pd.date_range(ext.index.min(),ext.index.max(),freq="h"); out=ext.reindex(grid).interpolate(limit=3)
def sim1(Tout, tau, off, gain=1.0):
    y=np.empty(len(Tout)); y[0]=Tout[0]+off; a=1.0/tau
    for i in range(1,len(Tout)):
        eq=off+gain*Tout[i]; y[i]=y[i-1]+a*(eq-y[i-1]) if not np.isnan(Tout[i]) else y[i-1]
    return y
def sim2(Tout, tau_f, tau_s, gf, off):
    # slow node tracks outdoor mean with tau_s; fast node adds gf*(Tout - slow) with tau_f
    n=len(Tout); s=np.empty(n); f=np.zeros(n); s[0]=np.nanmean(Tout[:24])+off
    for i in range(1,n):
        To=Tout[i] if not np.isnan(Tout[i]) else Tout[i-1]
        s[i]=s[i-1]+(To+off-s[i-1])/tau_s
        f[i]=f[i-1]+(gf*(To-(s[i]-off))-f[i-1])/tau_f
    return s+f
res=[]
for name,IN in (("BR",br),("LR",lr)):
    H=IN.resample("30min").mean().interpolate(limit=4).reindex(grid)
    for c in H.columns:
        j=pd.concat([H[c],out],axis=1,keys=["Tin","Tout"]).dropna()
        if len(j)<24*20: continue
        # use longest contiguous hourly run
        idx=j.index; breaks=np.where(np.diff(idx.values).astype('timedelta64[h]').astype(int)!=1)[0]
        segs=np.split(np.arange(len(j)),breaks+1); seg=max(segs,key=len)
        if len(seg)<24*15: continue
        Tin=j.Tin.values[seg]; To=j.Tout.values[seg]; warm=seg[48:]-seg[0]  # skip 2-day warmup
        best=None
        for tau in [1,2,3,4,6,8,12,16,24,36,48,72]:
            for gain in [0.6,0.8,1.0]:
                off0=np.mean(Tin[48:])-gain*np.mean(To[48:])
                y=sim1(To,tau,off0,gain); r=np.sqrt(np.mean((y[48:]-Tin[48:])**2))
                if best is None or r<best[0]: best=(r,tau,gain,off0)
        best2=None
        for tf in [1,2,3,4,6]:
            for ts in [12,24,48,72,120]:
                for gf in [0.1,0.15,0.2,0.3,0.4]:
                    off0=np.mean(Tin[48:])-np.mean(To[48:])
                    y=sim2(To,tf,ts,gf,off0); r=np.sqrt(np.mean((y[48:]-Tin[48:])**2))
                    if best2 is None or r<best2[0]: best2=(r,tf,ts,gf,off0)
        res.append(dict(room=name,house=c,hours=len(seg),rmse1=best[0],tau1=best[1],gain1=best[2],off1=best[3],rmse2=best2[0],tau_f=best2[1],tau_s=best2[2],g_f=best2[3],off2=best2[4],persist_rmse=np.sqrt(np.mean((Tin[49:]-Tin[48:-1])**2))))
R=pd.DataFrame(res); pd.set_option("display.width",220)
R.round(3).to_csv("/home/claude/hg_ai/research/bath_indoor_model_fit.csv",index=False); print(R.round(2).to_string())
print("\nMEDIAN/IQR"); print(R.describe(percentiles=[.25,.5,.75]).round(2).loc[["25%","50%","75%"]].to_string())
print("\ntau1 counts:",R.tau1.value_counts().sort_index().to_dict()); print("tau_s counts:",R.tau_s.value_counts().sort_index().to_dict()); print("tau_f counts:",R.tau_f.value_counts().sort_index().to_dict()); print("g_f counts:",R.g_f.value_counts().sort_index().to_dict())
print("mean rmse1 %.2f rmse2 %.2f"%(R.rmse1.mean(),R.rmse2.mean()))
