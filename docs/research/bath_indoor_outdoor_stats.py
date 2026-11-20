import pandas as pd, numpy as np, sys
d="/home/claude/hgdata/raw/22_bath_elderly_homes/"
br=pd.read_csv(d+"Phase 2 and 4 BR.csv",encoding="utf-8-sig"); lr=pd.read_csv(d+"Phase 2 and 4 LR.csv",encoding="utf-8-sig")
for df in (br,lr):
    df["t"]=pd.to_datetime(df["Timestamp"],dayfirst=True,errors="coerce"); df.set_index("t",inplace=True); df.drop(columns="Timestamp",inplace=True)
ext=pd.read_csv(d+"ExternalWeatherSummer.csv",header=None,encoding="utf-8-sig",names=["t","Tout"]); ext["t"]=pd.to_datetime(ext["t"],utc=True).dt.tz_convert("Europe/London").dt.tz_localize(None); ext=ext.set_index("t")["Tout"].sort_index()
print("ext range",ext.index.min(),ext.index.max(),"n",len(ext), "max",ext.max())
print("BR range",br.index.min(),br.index.max(),br.shape)
# hourly interpolate indoor to hourly grid
grid=pd.date_range(ext.index.min(),ext.index.max(),freq="h")
def tohour(df):
    return df.apply(pd.to_numeric,errors="coerce").resample("30min").mean().interpolate(limit=4).reindex(grid)
BR=tohour(br); LR=tohour(lr)
out=ext.reindex(grid).interpolate(limit=3)
# daily stats
daily=pd.DataFrame({"Tout_max":out.resample("D").max(),"Tout_min":out.resample("D").min(),"Tout_mean":out.resample("D").mean()})
# hot days
hot=daily[daily.Tout_max>=25]
print("days with Tout_max>=25:",len(hot)); print(hot.sort_values("Tout_max",ascending=False).head(8))
# per-house: regression Tin_daily_mean = a + b*Tout_daily_mean (running mean), lag by cross-correlation, night min, amplitude ratio
rows=[]
for name,IN in (("BR",BR),("LR",LR)):
    for c in IN.columns:
        s=IN[c].dropna()
        if len(s)<24*20: continue
        j=pd.concat([s,out],axis=1,keys=["Tin","Tout"]).dropna()
        if len(j)<24*20: continue
        # cross-corr lag on anomalies (remove daily means)
        a=j.Tin-j.Tin.rolling(24,center=True).mean(); b=j.Tout-j.Tout.rolling(24,center=True).mean(); ab=pd.concat([a,b],axis=1).dropna()
        lags=range(0,13); cc=[ab.iloc[:,0].corr(ab.iloc[:,1].shift(l)) for l in lags]; lag=int(np.nanargmax(cc))
        dm=j.resample("D").mean().dropna(); dmax=j.resample("D").max().dropna(); dmin=j.resample("D").min().dropna()
        # Tin daily mean vs running mean outdoor (CIBSE-style 7-day exp weighted)
        trm=j.Tout.resample("D").mean().ewm(alpha=0.2).mean()
        X=np.vstack([np.ones(len(dm)),trm.reindex(dm.index)]).T; beta=np.linalg.lstsq(X,dm.Tin,rcond=None)[0]
        amp=(dmax.Tin-dmin.Tin).mean()/(dmax.Tout-dmin.Tout).mean()
        hd=dmax[dmax.Tout>=25]
        rows.append(dict(room=name,house=c,n_days=len(dm),lag_h=lag,ccmax=max(cc),a=beta[0],b=beta[1],amp_ratio=amp,
            mean_Tin=dm.Tin.mean(),mean_Tout=dm.Tout.mean(),
            hot_Tin_max=hd.Tin.mean() if len(hd) else np.nan, hot_Tout_max=hd.Tout.mean() if len(hd) else np.nan,
            hot_Tin_min=dmin.loc[hd.index].Tin.mean() if len(hd) else np.nan, hot_Tout_min=dmin.loc[hd.index].Tout.mean() if len(hd) else np.nan,
            frac_h_gt24=(s>24).mean(), frac_h_gt26=(s>26).mean(), frac_night_gt24=(s[(s.index.hour>=23)|(s.index.hour<7)]>24).mean()))
R=pd.DataFrame(rows); R.round(3).to_csv("/home/claude/hg_ai/research/bath_indoor_outdoor_stats.csv",index=False); pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
print(R.round(2).to_string())
print("\nMEDIANS by room:"); print(R.groupby("room").median(numeric_only=True).round(2).to_string())
print("\nIQR lag:",R.lag_h.quantile([.25,.5,.75]).tolist(),"amp ratio q:",R.amp_ratio.quantile([.1,.5,.9]).round(2).tolist())
# hot-day hourly peak timing
for name,IN in (("BR",BR),("LR",LR)):
    m=IN.mean(axis=1); j=pd.concat([m,out],axis=1,keys=["Tin","Tout"]).dropna()
    hd=j[j.Tout.resample("D").transform("max")>=25]
    prof=hd.groupby(hd.index.hour).mean()
    print(name,"hot-day mean profile: Tin peak hour",prof.Tin.idxmax(),"=%.1f"%prof.Tin.max()," Tout peak hour",prof.Tout.idxmax(),"=%.1f"%prof.Tout.max(),
          " Tin min hour",prof.Tin.idxmin(),"=%.1f"%prof.Tin.min()," Tout min %.1f"%prof.Tout.min())
    print(prof.round(1).T.to_string())
