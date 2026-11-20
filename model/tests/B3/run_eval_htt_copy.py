"""T3: re-run the builder's eval_htt.py unchanged, but write outputs to a scratch dir (never into twin/)."""
import sys, runpy
sys.path.insert(0, "/home/claude/hg_ai/twin")
import eval_htt
eval_htt.OUT = sys.argv[1]
eval_htt.main()
