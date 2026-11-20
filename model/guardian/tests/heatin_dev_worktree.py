#!/usr/bin/env python3
"""[B5-v7] HeatIN DEV-watch dry run of the WORKING-TREE Guardian (freeze-7 candidate, not tagged yet).
Runs tests/real_exam_heatin.py UNCHANGED in --dry-run-dev mode (DEV watches only; the script itself discards every sealed-watch
line before parsing it and never touches the DONE file), with one substitution: the guardian is imported from the working tree
guardian/py instead of `git archive <tag>` (the candidate has no tag yet). Output: guardian/tests/out/heatin_dev_<label>.json.
usage: python3 -I guardian/tests/heatin_dev_worktree.py LABEL [--max-watches N]"""
import importlib, json, os, shutil, sys
REPO = "/home/claude/hg_ai"
sys.path.insert(0, os.path.join(REPO, "tests"))
R = importlib.import_module("real_exam_heatin")
label = sys.argv[1]; extra = sys.argv[2:]


def load_worktree(tag, tmp):
    sys.path.insert(0, os.path.join(REPO, "guardian/py"))
    os.environ.pop("HG_WEIGHTS", None)
    hg = importlib.import_module("hg_guardian_py"); tio = importlib.import_module("trace_io")
    wpath = os.path.join(REPO, "model/export/hg2_weights.json")
    W = hg.Weights(wpath)
    assert not W.stub
    return hg, tio, W, dict(tag="WORKING TREE (B5-v7 candidate; --tag %s only satisfies the CLI)" % tag, tag_commit=None,
                            weights_sha256=R.sha256_file(wpath), weights_version=W.version, nn_crc=W.crc)


R.load_guardian_from_tag = load_worktree
out_dir = os.path.join(REPO, "guardian/tests/out/heatin_tmp_%s" % label); os.makedirs(out_dir, exist_ok=True)
R.OUT_DIR = out_dir
sys.argv = ["real_exam_heatin.py", "--tag", "hg2-freeze-6", "--dry-run-dev"] + extra
R.main()
shutil.move(os.path.join(out_dir, "real_exam_heatin_DEV.json"), os.path.join(REPO, "guardian/tests/out/heatin_dev_%s.json" % label))
os.rmdir(out_dir)
