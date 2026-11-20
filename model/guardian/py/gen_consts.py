#!/usr/bin/env python3
"""Dump every numeric #define / static const of the C headers as exact float32 bits (as the C compiler rounds them),
so the Python mirror never re-parses a decimal literal (decimal->double->float can double-round). Writes py/hg_consts.json."""
import json, os, re, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(HERE, "..", "c")
hdrs = ["hg_guardian_cfg.h", "heat_guardian_model_v12.h", "hg_tables.h"]
names, arrays = [], []
for h in hdrs:
    for line in open(os.path.join(C, h)):
        m = re.match(r"#define\s+(\w+)\s+\(?\s*(-?[0-9][0-9.eE+\-]*f?)\s*\)?", line)
        if m: names.append(m.group(1))
        m = re.match(r"static const float (\w+)\[(\w+)\]", line)
        if m: arrays.append((m.group(1), m.group(2)))
        m = re.match(r"static const float (\w+)\s*=", line)
        if m: names.append(m.group(1))
import sys
WDIR = os.path.join(C, "stub") if (len(sys.argv) > 1 and sys.argv[1] == "stub") else (
       "/home/claude/hg_ai/model/export" if os.path.exists("/home/claude/hg_ai/model/export/hg2_weights.h") else os.path.join(C, "stub"))
OUTF = "hg_consts_stub.json" if WDIR.endswith("stub") else "hg_consts.json"
names += ["HG_UNC_SD_SCALE_EFF", "HG_UNC_HALF_CAL_EFF", "HG_UNC_CONST_MODE", "HG_UNC_LOWER_CONST", "HG2_EPS_V_EFF", "HG_RANGE_HALF_REAL_EFF"]
src = ['#include <stdio.h>', '#include <string.h>', '#include "hg_guardian_cfg.h"', '#include "heat_guardian_model_v12.h"', '#include "hg_unc.h"',
       '#include "hg_tables.h"', 'static void pf(const char*n,float v){unsigned u;memcpy(&u,&v,4);printf("%s %08x\\n",n,u);}',
       'int main(void){']
for n in names: src.append('pf("%s",(float)(%s));' % (n, n))
for n, l in arrays: src.append('for(int i=0;i<(int)(%s);i++){char b[64];sprintf(b,"%s[%%d]",i);pf(b,%s[i]);}' % (l, n, n))
src.append('return 0;}')
with tempfile.TemporaryDirectory() as d:
    open(d + "/d.c", "w").write("\n".join(src))
    subprocess.check_call(["gcc", "-std=c99", "-fsingle-precision-constant", "-w", "-I" + C, "-I" + WDIR, d + "/d.c", "-o", d + "/d"])
    out = subprocess.check_output([d + "/d"]).decode().split("\n")
res = {}
for line in out:
    if line.strip():
        k, h = line.split(); res[k] = h
json.dump(res, open(os.path.join(HERE, OUTF), "w"), indent=0)
if OUTF == "hg_consts.json" and WDIR.endswith("stub"): json.dump(res, open(os.path.join(HERE, "hg_consts_stub.json"), "w"), indent=0)
print(len(res), "constants")
