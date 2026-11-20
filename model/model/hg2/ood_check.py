"""B5 ask (c): crafted trace T1 held flat 36.4 C at HR 150 for 2 h -> NN core_20 far below v1.2. Real or OOD?
Runs the crafted trace through FeatureState + the ensemble, and measures how much SIM-DEV training data looks like it."""
import json, os, sys
import numpy as np
from .common import CACHE, RUNS
from . import features as FT, nn
from .train import norm, load_view
from .eval import members, ens_predict


def crafted(T=180, hr_hi=150, t1=36.4, tair=30.0, rh=45.0, age=75.0, flags=0, astd=0.03):
    hr = np.where(np.arange(T) >= 30, hr_hi, 75.0).astype(np.float32)
    cols = dict(t1=np.full((T, 1), t1, np.float32), t2=np.full((T, 1), t1 - 1.0, np.float32), tair=np.full((T, 1), tair, np.float32),
                rh=np.full((T, 1), rh, np.float32), hr=hr[:, None], hrq=np.full((T, 1), 4), pi=np.full((T, 1), 1.0, np.float32),
                astd=np.full((T, 1), astd, np.float32), worn=np.full((T, 1), 2), mod=(600 + np.arange(T))[:, None] % 1440)
    prof = dict(age=np.array([age]), sex_m=np.array([1.0]), bmi=np.array([26.0]), med_flags=np.array([flags]))
    tw = dict(rest_hr=np.array([70.0]), k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=np.full((1, 24), np.nan))
    X, aux, idx = FT.run_lanes(cols, prof, tw)
    return X, aux


def main():
    N = norm(); Ps = members(); out = {}
    for name, kw in (("crafted HR150 T1 36.4 (B5)", {}), ("same, T1 rises to 36.9", dict(t1=36.9)), ("same, HR 120", dict(hr_hi=120))):
        X, aux = crafted(**kw); E, _ = ens_predict(Ps, nn.normalise_x(X, N["xm"], N["xs"]), N)
        out[name] = dict(nn_core20_at_150min=float(E["core_20"][150]), v12_f20_at_150min=float(aux["v12_f20"][150]),
                         nn_sd20=float(E["sd_20"][150]), hr_reserve=float(X[150, 14]))
    # training-data support: rows with hr >= 140 and t1 <= 36.6 in a training view
    Xv, Yv, Mv = load_view("v0")
    hi = Xv[:, 10] >= 140; both = hi & (Xv[:, 0] <= 36.6)
    out["training_support_view_v0"] = dict(rows=int(len(Xv)), share_hr_ge_140=float(hi.mean() * 100), rows_hr_ge_140=int(hi.sum()),
                                           rows_hr_ge_140_and_t1_le_36_6=int(both.sum()),
                                           sim_core_when_hr_ge_140_median=float(np.median(Yv[hi, 0])) if hi.any() else None,
                                           sim_t1_when_hr_ge_140_median=float(np.median(Xv[hi, 0])) if hi.any() else None,
                                           hr_reserve_p99=float(np.percentile(Xv[:, 14], 99)), hr_p99=float(np.percentile(Xv[:, 10], 99)))
    json.dump(out, open(os.path.join(RUNS, "results_ood_hr150.json"), "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
