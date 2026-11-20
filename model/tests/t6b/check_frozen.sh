#!/bin/sh
# T6b: independent check that fw/09_guardian/frozen/* == tag $TAG blobs (default hg2-freeze-6), and FROZEN.txt sha.
R=/home/claude/hg_ai; TAG=${HG_FREEZE_TAG:-hg2-freeze-6}; cd $R
echo "tag commit: $(git rev-list -n1 $TAG)"
echo "FROZEN.txt@tag sha256: $(git show $TAG:guardian/FROZEN.txt | sha256sum | cut -d' ' -f1)"
n=0; bad=0
for f in fw/09_guardian/frozen/*; do
  b=$(basename $f)
  src=$(git ls-tree -r --name-only $TAG guardian/c model/export twin/c | grep -v stub/ | grep "/$b\$")
  c=$(echo "$src" | wc -l)
  [ "$c" = 1 ] || { echo "AMBIGUOUS/MISSING $b -> [$src]"; bad=$((bad+1)); continue; }
  if git show "$TAG:$src" | cmp -s - "$f"; then n=$((n+1)); else echo "DIFF $b vs $src"; bad=$((bad+1)); fi
done
echo "identical=$n bad=$bad"
# files in the tag's source dirs NOT copied
for s in $(git ls-tree -r --name-only $TAG guardian/c model/export twin/c | grep -E '\.(c|h)$' | grep -v stub/); do
  [ -f fw/09_guardian/frozen/$(basename $s) ] || echo "not copied: $s"; done
# FROZEN.txt listed hashes vs copies
git show $TAG:guardian/FROZEN.txt | grep -E '^sha256 ' | while read k name h rest; do
  if [ -f fw/09_guardian/frozen/$name ]; then hv=$(sha256sum fw/09_guardian/frozen/$name|cut -d' ' -f1); [ "$hv" = "$h" ] && echo "FROZEN.txt OK $name" || echo "FROZEN.txt BAD $name"; else echo "FROZEN.txt lists $name (not in frozen/)"; fi; done
# working tree vs tag
git diff --stat $TAG -- guardian/c model/export twin/c | tail -3
git status --short fw/09_guardian | head
