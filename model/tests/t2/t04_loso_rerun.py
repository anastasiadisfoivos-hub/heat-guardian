"""T2-04a re-run the builder's HTT LOSO (65 folds x 5 members, fine-tune + sd heads) WITHOUT touching model/: CACHE and LOG
are redirected to tests/t2/out/loso_cache (symlinks to the read-only SIM caches, a COPY of train_log.json).
Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 HG2_HRAUG=1 nice python3 tests/t2/t04_loso_rerun.py
Then compares the re-run htt_oof.npz bitwise / numerically with the builder's."""
import json, os, shutil, sys, time
sys.path.insert(0, "/home/claude/hg_ai")
os.environ["HG2_SIMVER"] = "v4"; os.environ["HG2_HRAUG"] = "1"
import numpy as np
from model.hg2 import train, common
SRC = common.CACHE; DST = "/home/claude/hg_ai/tests/t2/out/loso_cache"
os.makedirs(DST, exist_ok=True)
for f in os.listdir(SRC):
    if f.startswith("htt_"): continue                  # outputs: never linked, re-created here
    p = os.path.join(DST, f)
    if not os.path.exists(p): os.symlink(os.path.join(SRC, f), p)
shutil.copy(train.LOG, os.path.join(DST, "train_log_copy.json"))
train.CACHE = DST; train.LOG = os.path.join(DST, "train_log_copy.json")
t0 = time.time(); train.main_loso(); print("loso rerun minutes", (time.time() - t0) / 60)
a = np.load(os.path.join(SRC, "htt_oof.npz"), allow_pickle=True); b = np.load(os.path.join(DST, "htt_oof.npz"), allow_pickle=True)
res = dict(minutes=(time.time() - t0) / 60, raw_bitwise_equal=bool(np.array_equal(a["raw"], b["raw"], equal_nan=True)),
           raw_max_abs_diff=float(np.nanmax(np.abs(a["raw"] - b["raw"]))), Y_equal=bool(np.array_equal(a["Y"], b["Y"], equal_nan=True)),
           X_equal=bool(np.array_equal(a["X"], b["X"], equal_nan=True)))
json.dump(res, open("/home/claude/hg_ai/tests/t2/out/t04_loso_rerun.json", "w"), indent=1); print(res)
