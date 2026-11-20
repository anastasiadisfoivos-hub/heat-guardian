#!/usr/bin/env python3
"""Worst-case stack depth of a function from GCC -fcallgraph-info=su output (.ci files in a directory).
usage: stack_highwater.py <dir> <root_function>. Sums frame sizes along the deepest call path (no recursion exists)."""
import glob, re, sys
d, root = sys.argv[1], sys.argv[2]
frame, edges = {}, {}
for f in glob.glob(d + "/*.ci"):
    for line in open(f):
        m = re.search(r'node: \{ title: "([^"]+)" label: "[^"]*?\\n[^"]*?\\n(\d+) bytes \(([^)]*)\)', line)
        if m:
            name = m.group(1).split(":")[-1]
            frame[name] = max(frame.get(name, 0), int(m.group(2))); continue
        m = re.search(r'edge: \{ sourcename: "([^"]+)" targetname: "([^"]+)"', line)
        if m: edges.setdefault(m.group(1).split(":")[-1], set()).add(m.group(2).split(":")[-1])
memo = {}
def depth(fn, seen=()):
    if fn in seen: raise SystemExit("recursion through " + fn)
    if fn in memo: return memo[fn]
    best, path = 0, []
    for c in edges.get(fn, ()):
        dd, p = depth(c, seen + (fn,))
        if dd > best: best, path = dd, p
    memo[fn] = (frame.get(fn, 0) + best, [fn] + path)
    return memo[fn]
tot, path = depth(root)
print("stack high-water of %s: %d bytes" % (root, tot))
print("  deepest path: " + " -> ".join("%s(%d)" % (p, frame.get(p, 0)) for p in path))
unknown = sorted(set(c for cs in edges.values() for c in cs) - set(frame))
if unknown: print("  callees without frame info (libm/libc, counted 0): " + ", ".join(unknown))
