"""T2-09 reproducibility: re-train member 1 (train.py --seed 1 recipe) into tests/t2/out (MEM/LOG/CACHE redirected), compare
with runs/v4aug/members/member_1.npz: pre_* bitwise; ft_* bitwise except the sd-head rows 6..8 of W3/b3 (refit later by --var).
Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 HG2_HRAUG=1 python3 tests/t2/t09_member_repro.py"""
import json, os, shutil, sys
sys.path.insert(0, "/home/claude/hg_ai"); os.environ["HG2_SIMVER"] = "v4"; os.environ["HG2_HRAUG"] = "1"
import numpy as np
from model.hg2 import train
D = "/home/claude/hg_ai/tests/t2/out/loso_cache"; MEMD = "/home/claude/hg_ai/tests/t2/out/members_repro"; os.makedirs(MEMD, exist_ok=True)
BUILDER = train.MEM
shutil.copy("/home/claude/hg_ai/model/runs/v4aug/train_log.json", D + "/train_log_m.json")
train.CACHE = D; train.LOG = D + "/train_log_m.json"; train.MEM = MEMD
train.main_member(1)
a = np.load(BUILDER + "/member_1.npz"); b = np.load(MEMD + "/member_1.npz")
res = dict(pre_bitwise=[bool(np.array_equal(a["pre_%d" % i], b["pre_%d" % i])) for i in range(6)],
           ft_bitwise_W1_b2=[bool(np.array_equal(a["ft_%d" % i], b["ft_%d" % i])) for i in range(4)],
           ft_W3_rows0_5=bool(np.array_equal(a["ft_4"][:6], b["ft_4"][:6])), ft_b3_0_5=bool(np.array_equal(a["ft_5"][:6], b["ft_5"][:6])),
           ft_maxabs=float(max(np.abs(a["ft_%d" % i] - b["ft_%d" % i]).max() for i in range(4))))
print(res); json.dump(res, open("/home/claude/hg_ai/tests/t2/out/t09_member_repro.json", "w"), indent=1)
