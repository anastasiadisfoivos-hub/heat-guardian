#!/bin/bash
# Heat Guardian emergency format over USB (0.9.11+). Double-click on the Mac, or:
#   bash band_fsformat.command            -> "fsformat"  : re-format the LOG area (QSPI); logs are lost
#   bash band_fsformat.command ifsformat  -> "ifsformat" : 0.9.13+: re-format InternalFS (profile kept)
# Waits for /dev/cu.usbmodem*, sends the word every 0.2 s (re-finding the port, so a band that resets still gets it in its
# 3-s boot window), STOPS SENDING as soon as the band answers "# FS_HEAL formatted" / "# FS_HEAL ifs formatted",
# gives up sending after 8 s, then listens until 20 s after the answer. Output: fsformat_out.txt next to this script.
cd "$(dirname "$0")" || exit 1
WORD="${1:-fsformat}"
case "$WORD" in fsformat) DONE="FS_HEAL formatted";; ifsformat) DONE="FS_HEAL ifs formatted";; *) echo "usage: $0 [fsformat|ifsformat]"; exit 1;; esac
OUT="fsformat_out.txt"; : > "$OUT"
port() { ls /dev/cu.usbmodem* 2>/dev/null | head -1; }
echo "Waiting up to 60 s for the band on /dev/cu.usbmodem* (plug it in, or press reset)..."
P=""; for i in $(seq 1 600); do P=$(port); [ -n "$P" ] && break; sleep 0.1; done
[ -z "$P" ] && { echo "No /dev/cu.usbmodem* found. Data cable? Arduino Serial Monitor closed?"; exit 1; }
echo "Found $P. Sending '$WORD' until the band confirms (max 8 s)..."
START=$SECONDS; RPID=""; SENDING=1; DONE_AT=""
while :; do
  T=$((SECONDS - START))
  if [ -z "$DONE_AT" ] && grep -a -q "$DONE" "$OUT"; then DONE_AT=$T; SENDING=0; echo ">>> band confirmed at ${T} s - stopped sending, listening 20 s"; fi
  [ $SENDING = 1 ] && [ $T -ge 8 ] && { SENDING=0; echo "No confirmation after 8 s - stopped sending, listening 20 s"; DONE_AT=$T; }
  [ -n "$DONE_AT" ] && [ $((T - DONE_AT)) -ge 20 ] && break
  P=$(port)
  if [ -n "$P" ]; then
    if [ -z "$RPID" ] || ! kill -0 "$RPID" 2>/dev/null; then
      stty -f "$P" 115200 raw -echo 2>/dev/null
      ( cat "$P" >> "$OUT" 2>/dev/null ) & RPID=$!
    fi
    [ $SENDING = 1 ] && printf '%s\n' "$WORD" > "$P" 2>/dev/null
  fi
  sleep 0.2
done
[ -n "$RPID" ] && kill "$RPID" 2>/dev/null
echo "----- saved $(wc -l < "$OUT" | tr -d ' ') lines to $(pwd)/$OUT; the FS_HEAL / WDT / BOOT lines: -----"
grep -a -E "Heat Guardian|FS_HEAL|# WDT|# BOOT|storage=" "$OUT" | head -40
N=$(grep -a -c "$DONE" "$OUT"); echo ">>> '$DONE' seen $N time(s) (1 = right)."
