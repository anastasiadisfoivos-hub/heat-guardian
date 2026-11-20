"""T2-02 export attack. Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 HG2_HRAUG=1 python3 tests/t2/t02_export.py
 1. parse every array out of model/export/hg2_weights.c (my own regex parser, no builder code)
 2. bitwise compare with hg2_weights.json (hex) and runs/v4aug/members/member_k.npz (ft_*)
 3. CRC-32 (zlib) over the parsed arrays == HG2_NN_CRC32 in .h == train_log ensemble_crc32 == export_report
 4. SHA-256 of the frozen files
 5. builder host_test with the ARCH flags; my own C harness on 1,000 random SIM-DEV calibration rows (hg2_nn.c + hg2_weights.c)
    vs my float64 numpy forward from the parsed arrays (members, ensemble mean, between-member sd, M6 total sd, core in degC)
 6. golden_trace.parquet: recompute every NN out_* column from its x00..x31 columns with my forward + the M6 sd rule
"""
import hashlib, json, os, re, struct, subprocess, sys, zlib
import numpy as np
ROOT = "/home/claude/hg_ai"; EXP = ROOT + "/model/export"; OUT = ROOT + "/tests/t2/out"; T2 = ROOT + "/tests/t2"
F = np.float32
R = {}
src = open(EXP + "/hg2_weights.c").read()
arr = {}
for m in re.finditer(r"const float (\w+?)((?:\[\w+\])+) = (\{.*?\});", src, re.S):
    name, dims, body = m.group(1), m.group(2), m.group(3)
    vals = np.array([F(float(v)) for v in re.findall(r"[-+]?\d\.\d+e[-+]\d+", body)], F)
    arr[name] = vals
R["parsed_arrays"] = len(arr)
shapes = [(24, 32), (24,), (16, 24), (16,), (9, 16), (9,)]; NAMES = ["W1", "b1", "W2", "b2", "W3", "b3"]
Ms = [[arr["%s_%d" % (n, k)].reshape(sh) for n, sh in zip(NAMES, shapes)] for k in range(5)]
xm, xs = arr["HG2_X_MEAN"], arr["HG2_X_STD"]; ym, ys = arr["HG2_Y_MEAN"], arr["HG2_Y_STD"]
assert all(a.size == np.prod(sh) for m in Ms for a, sh in zip(m, shapes)) and xm.size == 32 and ym.size == 3
crc = 0
for m in Ms:
    for a in m: crc = zlib.crc32(np.ascontiguousarray(a, "<f4").tobytes(), crc)
h = open(EXP + "/hg2_weights.h").read()
hcrc = int(re.search(r"#define HG2_NN_CRC32 0x([0-9A-Fa-f]+)u", h).group(1), 16)
L = json.load(open(ROOT + "/model/runs/v4aug/train_log.json")); rep = json.load(open(EXP + "/export_report.json"))
J = json.load(open(EXP + "/hg2_weights.json"))
R["crc_from_c_arrays"] = "0x%08X" % crc; R["crc_header"] = "0x%08X" % hcrc; R["crc_train_log"] = L["ensemble_crc32"]
R["crc_export_report"] = rep["crc32"]; R["crc_weights_json"] = "0x%08X" % J["crc32"]
R["crc_all_equal"] = len({R[k] for k in ("crc_from_c_arrays", "crc_header", "crc_train_log", "crc_export_report", "crc_weights_json")}) == 1
# per-member CRC in train log
mc = []
for k in range(5):
    c = 0
    for a in Ms[k]: c = zlib.crc32(np.ascontiguousarray(a, "<f4").tobytes(), c)
    mc.append(("0x%08X" % c, L["members"][str(k + 1)]["crc32_member"]))
R["member_crc_c_vs_log"] = mc; R["member_crc_all_equal"] = all(a == b for a, b in mc)
# bitwise vs json and npz
bj = all(np.frombuffer(bytes.fromhex(J["members"][k][i]), "<f4").tobytes() == Ms[k][i].astype("<f4").tobytes() for k in range(5) for i in range(6))
bjn = all(np.frombuffer(bytes.fromhex(J[n]), "<f4").tobytes() == a.astype("<f4").tobytes() for n, a in (("xm", xm), ("xs", xs), ("ym", ym), ("ys", ys)))
bn = []
for k in range(5):
    d = np.load(ROOT + "/model/runs/v4aug/members/member_%d.npz" % (k + 1))
    bn.append(all(d["ft_%d" % i].astype("<f4").tobytes() == Ms[k][i].astype("<f4").tobytes() for i in range(6)))
nj = json.load(open(ROOT + "/model/cache/v4aug/norm.json"))
R["c_eq_json_bitwise"] = bool(bj and bjn); R["c_eq_member_npz_bitwise"] = bn
R["norm_c_eq_cache_norm_json"] = bool(np.array_equal(np.array(nj["xm"], F), xm) and np.array_equal(np.array(nj["xs"], F), xs)
                                      and np.array_equal(np.array(nj["ym"], F), ym) and np.array_equal(np.array(nj["ys"], F), ys))
R["weight_bytes"] = int(sum(a.nbytes for m in Ms for a in m)); R["n_params_member"] = int(sum(a.size for a in Ms[0]))
R["sha256"] = {f: hashlib.sha256(open(EXP + "/" + f, "rb").read()).hexdigest() for f in ("hg2_weights.json", "hg2_weights.c", "hg2_weights.h", "test_vectors.json", "golden_trace.parquet")}
R["header_comment_lines"] = h.splitlines()[:3]
R["header_has_brief_names"] = {n: ("#define " + n) in h or (n + "[") in h for n in ("HG2_N_IN", "HG2_H1", "HG2_H2", "HG2_N_OUT", "HG2_N_ENS", "HG2_NN_CRC32", "HG2_NN_VERSION", "HG2_X_MEAN", "HG2_X_STD", "HG2_Y_MEAN", "HG2_Y_STD", "HG2_LOGIT_CUT_38", "HG2_LOGIT_CUT_385", "HG2_SIGMOID_LUT")}
R["grep_forbidden_in_export_c"] = {w: len(re.findall(r"\b%s\b" % w, open(EXP + "/hg2_weights.c").read() + open(EXP + "/host/hg2_nn.c").read())) for w in ("expf", "logf", "powf", "double", "malloc")}

FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-Wdouble-promotion", "-fsingle-precision-constant", "-O2", "-ffp-contract=off"]
r = subprocess.run(["gcc"] + FLAGS + ["-I" + EXP, "-I" + EXP + "/host", EXP + "/host/host_test.c", EXP + "/host/hg2_nn.c", EXP + "/hg2_weights.c", "-lm", "-o", OUT + "/host_test"], capture_output=True, text=True)
R["host_test_build"] = (r.returncode, r.stderr[-400:])
r = subprocess.run([OUT + "/host_test"], capture_output=True, text=True); R["host_test_run"] = (r.returncode, r.stdout.strip())

# my C harness
harness = r'''#include <stdio.h>
#include <stdlib.h>
#include "hg2_nn.h"
int main(int argc, char **argv) { (void)argc; FILE *fi = fopen(argv[1], "rb"), *fo = fopen(argv[2], "wb"); float z[32];
  if (!fi || !fo) return 2;
  if (!hg2_nn_check_crc()) return 3;
  while (fread(z, sizeof(float), 32, fi) == 32) { float y[9], mean[9], sd[9];
    for (int k = 0; k < HG2_NN_ENS; k++) { hg2_nn_forward(&HG2_MEMBERS[k], z, y); fwrite(y, sizeof(float), 9, fo); }
    hg2_nn_ensemble(z, mean, sd); fwrite(mean, sizeof(float), 9, fo); fwrite(sd, sizeof(float), 9, fo); }
  fclose(fi); fclose(fo); return 0; }
'''
open(T2 + "/t02_harness.c", "w").write(harness)
r = subprocess.run(["gcc"] + FLAGS + ["-I" + EXP, "-I" + EXP + "/host", T2 + "/t02_harness.c", EXP + "/host/hg2_nn.c", EXP + "/hg2_weights.c", "-lm", "-o", OUT + "/t02_harness"], capture_output=True, text=True)
R["harness_build"] = (r.returncode, r.stderr[-400:])
d = np.load(ROOT + "/model/cache/v4aug/sim_val.npz"); X = d["X"]
rng = np.random.default_rng(424242); idx = rng.choice(len(X), 1000, replace=False); Xr = X[idx].astype(F)
Z = np.where(np.isnan(Xr), F(0), ((Xr - xm).astype(F) / xs).astype(F)).astype(F)
Z.astype("<f4").tofile(OUT + "/t02_z.bin")
r = subprocess.run([OUT + "/t02_harness", OUT + "/t02_z.bin", OUT + "/t02_y.bin"], capture_output=True, text=True); R["harness_run_rc"] = r.returncode
Yc = np.fromfile(OUT + "/t02_y.bin", "<f4").reshape(1000, 7, 9)


def fwd64(m, z):
    W1, b1, W2, b2, W3, b3 = [a.astype(np.float64) for a in m]
    h1 = np.maximum(z @ W1.T + b1, 0); h2 = np.maximum(h1 @ W2.T + b2, 0); return h2 @ W3.T + b3


Z64 = Z.astype(np.float64)
ym64 = np.stack([fwd64(m, Z64) for m in Ms])            # [5, n, 9]
mean64 = ym64.mean(0); btw64 = ym64.std(0)
R["c_vs_numpy64_members_maxabs"] = float(np.abs(Yc[:, :5, :].transpose(1, 0, 2) - ym64).max())
R["c_vs_numpy64_mean_maxabs"] = float(np.abs(Yc[:, 5] - mean64).max())
R["c_vs_numpy64_btwsd_maxabs"] = float(np.abs(Yc[:, 6] - btw64).max())
rel = np.abs(Yc[:, :5, :].transpose(1, 0, 2) - ym64) / np.maximum(1, np.abs(ym64)); R["c_vs_numpy64_members_max_rel"] = float(rel.max())
# M6 total sd and degC outputs (the hg2_step formula in the header comment)
ale = (ym64[:, :, 6:9] ** 2 + 1e-3).mean(0); tot = np.sqrt(ale + ym64[:, :, :3].var(0)) * ys
core = mean64[:, :3] * ys + ym
cC = Yc[:, 5, :3].astype(np.float64) * ys + ym
aleC = (Yc[:, :5, 6:9].astype(np.float64) ** 2 + 1e-3).mean(1); totC = np.sqrt(aleC + Yc[:, :5, :3].astype(np.float64).var(1)) * ys
R["core_degC_C_vs_numpy64_maxabs"] = float(np.abs(cC - core).max()); R["sd_degC_C_vs_numpy64_maxabs"] = float(np.abs(totC - tot).max())
# builder python (nn.predict, BLAS float32) vs mine
sys.path.insert(0, ROOT); os.environ.setdefault("HG2_SIMVER", "v4")
from model.hg2 import nn as BN
yb = np.stack([BN.predict(m, Z) for m in Ms]); R["builder_nn_predict_vs_numpy64_maxabs"] = float(np.abs(yb - ym64).max())
R["pass_1e-5_members_C_vs_mine"] = R["c_vs_numpy64_members_maxabs"] <= 1e-5

# golden trace re-derivation
G = __import__("pandas").read_parquet(EXP + "/golden_trace.parquet")
xc = [c for c in G.columns if re.match(r"x\d\d_", c)]; assert len(xc) == 32
Xg = G[xc].values.astype(F); Zg = np.where(np.isnan(Xg), F(0), ((Xg - xm).astype(F) / xs).astype(F)).astype(np.float64)
yg = np.stack([fwd64(m, Zg) for m in Ms]); mg = yg.mean(0)
coreg = mg[:, :3] * ys + ym; sdg = np.sqrt((yg[:, :, 6:9] ** 2 + 1e-3).mean(0) + yg[:, :, :3].var(0)) * ys
gd = {}
for j, n in enumerate(("core_now", "core_20", "core_30")):
    gd[n] = float(np.abs(G["out_" + n].values - coreg[:, j]).max()); gd["sd_" + n[5:]] = float(np.abs(G["out_sd_" + n[5:]].values - sdg[:, j]).max())
gd["logit_p38"] = float(np.abs(G.out_logit_p38.values - mg[:, 3]).max()); gd["logit_p385"] = float(np.abs(G.out_logit_p385.values - mg[:, 4]).max())
gd["strain"] = float(np.abs(G.out_strain.values - np.clip(mg[:, 5], 0, 10)).max())
gd["f20_eff_eq_core_20"] = bool(np.allclose(G.out_f20_eff.values, G.out_core_20.values))
R["golden_rows"] = len(G); R["golden_persons"] = sorted(G.person_id.unique().tolist())
R["golden_NN_outputs_vs_mine_maxabs"] = gd; R["golden_pass_1e-4"] = all(v <= 1e-4 for k, v in gd.items() if isinstance(v, float))
R["golden_valid_share"] = float(G.out_valid.mean()); R["golden_flux_valid_share"] = float(G.out_flux_valid.mean())
R["golden_truth_core_range"] = [float(G.truth_T_core.min()), float(G.truth_T_core.max())]
R["golden_mae_now_vs_truth"] = float(np.abs(G.out_core_now - G.truth_T_core).mean())
# test vectors: >= 20, not tuned on (spot check: same mean as mine)
TV = json.load(open(EXP + "/test_vectors.json"))
R["test_vectors_n"] = TV["n"]
mx = 0
for v in TV["vectors"]:
    z = np.frombuffer(bytes.fromhex(v["z_hex"]), "<f4").astype(np.float64)[None]
    ys_ = np.stack([fwd64(m, z) for m in Ms]); mx = max(mx, float(np.abs(ys_.mean(0)[0] - np.frombuffer(bytes.fromhex(v["mean_hex"]), "<f4")).max()))
R["test_vectors_mean_vs_mine_maxabs"] = mx
json.dump(R, open(OUT + "/t02_export.json", "w"), indent=1, default=str)
print(json.dumps(R, indent=1, default=str))
