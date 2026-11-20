#!/bin/bash
# Heat Guardian: flash the band over USB with NO reset-button taps (macOS). [FLASH-EASY]
#   bash flash_band.command <file.zip>   PRIMARY: serial DFU. adafruit-nrfutil does the 1200-baud "touch" (any build, also
#                                        0.9.17-demo-b7), the band reboots into its bootloader, the app is sent over USB serial.
#   bash flash_band.command <file.uf2>   FALLBACK: sends `uf2` (0.9.17-demo-b7u and later) so the XIAO-SENSE drive appears,
#                                        then copies the file onto it.
# Afterwards it waits for the band to come back and prints its "# STAT fw=" line. Close the Arduino Serial Monitor first.
# If a transfer stops halfway: just run the same command again (the bootloader stays in update mode when the app is incomplete).

FILE="$1"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: bash $0 <path-to-.zip-or-.uf2>"
  echo "  e.g. bash $0 ~/Downloads/09_guardian_v0917_demo_b7u.zip"
  exit 1
fi
case "$FILE" in /*) ;; *) FILE="$(pwd)/$FILE";; esac
VOL=/Volumes/XIAO-SENSE
port() { ls /dev/cu.usbmodem* 2>/dev/null | head -1; }

wait_port() {   # $1 = seconds; prints the port, returns 1 if none
  local i P
  for i in $(seq 1 $(( $1 * 5 ))); do P=$(port); [ -n "$P" ] && { echo "$P"; return 0; }; sleep 0.2; done
  return 1
}

send_word() {   # $1 = port, $2 = word
  stty -f "$1" 115200 raw -echo 2>/dev/null
  printf '%s\n' "$2" > "$1" 2>/dev/null
}

show_stat() {   # wait for the band, ask `stat` (every 1 s, up to 15 s), print the first "# STAT fw=" line
  echo "Waiting for the band to come back on USB (up to 20 s)..."
  local P; P=$(wait_port 20) || { echo "The band did not come back on USB within 20 s. Unplug and replug the cable, then run: bash band_cmd.command stat"; return 1; }
  sleep 1.5; P=$(port); [ -z "$P" ] && { echo "The port went away again. Unplug/replug and check with band_cmd.command stat."; return 1; }
  echo "Band is back on $P. Asking for its version..."
  local OUT; OUT=$(mktemp -t hgstat)
  stty -f "$P" 115200 raw -echo 2>/dev/null
  ( cat "$P" >> "$OUT" 2>/dev/null ) & local RPID=$!
  local t
  for t in $(seq 1 15); do
    printf 'stat\n' > "$P" 2>/dev/null
    sleep 1
    grep -a -q "# STAT fw=" "$OUT" && break
  done
  kill "$RPID" 2>/dev/null; wait "$RPID" 2>/dev/null
  local L; L=$(grep -a -m1 "# STAT fw=" "$OUT" | tr -d '\r')
  rm -f "$OUT"
  if [ -n "$L" ]; then echo "$L"; echo "Done. The band runs the new firmware (check the fw= above)."; return 0; fi
  echo "No '# STAT fw=' answer within 15 s. Try: bash band_cmd.command stat"; return 1
}

find_nrfutil() {
  local c
  c=$(command -v adafruit-nrfutil 2>/dev/null) && { echo "$c"; return 0; }
  for c in "$HOME"/Library/Python/*/bin/adafruit-nrfutil \
           "$HOME"/Library/Arduino15/packages/Seeeduino/hardware/nrf52/*/tools/adafruit-nrfutil/macos/adafruit-nrfutil \
           "$HOME"/Library/Arduino15/packages/adafruit/hardware/nrf52/*/tools/adafruit-nrfutil/macos/adafruit-nrfutil \
           /opt/homebrew/bin/adafruit-nrfutil /usr/local/bin/adafruit-nrfutil; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}

# ------------------------------------------------------------------ .zip: serial DFU (no taps, works from any build)
if [[ "$FILE" == *.zip ]]; then
  NRFU=$(find_nrfutil)
  if [ -z "$NRFU" ]; then
    echo "adafruit-nrfutil is not installed. Install it once with:"
    echo "    python3 -m pip install --user adafruit-nrfutil"
    echo "It lands in ~/Library/Python/3.X/bin/adafruit-nrfutil (3.X = your Python version); this script finds it there."
    echo "Then run this command again."
    exit 1
  fi
  echo "Using $NRFU"
  echo "Looking for the band on /dev/cu.usbmodem* (up to 15 s; plug it in)..."
  P=$(wait_port 15) || { echo "No band found on USB. Data cable (not charge-only)? Arduino Serial Monitor closed?"; exit 1; }
  echo "Found $P. Flashing $(basename "$FILE") over USB serial - do NOT unplug (about 30-60 s)..."
  if "$NRFU" --verbose dfu serial -pkg "$FILE" -p "$P" -b 115200 --singlebank --touch 1200; then
    echo "Transfer finished."
    show_stat; exit $?
  fi
  echo ""
  echo "The transfer did not finish. Nothing is broken: the band's bootloader stays in update mode when the app is incomplete."
  echo "Run the same command again:  bash $0 $FILE"
  echo "(If the XIAO-SENSE drive shows up in Finder, you can also run this script with the .uf2 instead.)"
  exit 1
fi

# ------------------------------------------------------------------ .uf2: the XIAO-SENSE drive
if [[ "$FILE" != *.uf2 ]]; then echo "The file must end in .zip (serial DFU) or .uf2 (drive copy): $FILE"; exit 1; fi
if [ -d "$VOL" ]; then
  echo "$VOL is already mounted - copying straight away."
else
  echo "Looking for the band on /dev/cu.usbmodem* (up to 15 s)..."
  P=$(wait_port 15) || { echo "No band found on USB. Data cable? Arduino Serial Monitor closed?"; exit 1; }
  echo "Found $P. Asking the band to open its update drive (uf2)..."
  send_word "$P" "uf2"
  echo "Waiting up to 15 s for $VOL..."
  for i in $(seq 1 75); do [ -d "$VOL" ] && break; sleep 0.2; done
  if [ ! -d "$VOL" ]; then
    echo "The drive did not appear. The firmware on the band probably doesn't have the uf2 command yet (0.9.17-demo-b7 and older)."
    echo "Easiest: use the .zip instead (no taps):  bash $0 ${FILE%.uf2}.zip"
    echo "Or double-tap reset once now if you can reach it; waiting another 30 s for $VOL..."
    for i in $(seq 1 150); do [ -d "$VOL" ] && break; sleep 0.2; done
    [ -d "$VOL" ] || { echo "Still no $VOL. Stopped; nothing was changed on the band."; exit 1; }
  fi
  sleep 1   # let Finder finish mounting
fi
echo "Copying $(basename "$FILE") onto $VOL ..."
cp -X "$FILE" "$VOL/" 2>/tmp/hg_flash_cp_err.$$; RC=$?
ERR=$(cat /tmp/hg_flash_cp_err.$$ 2>/dev/null); rm -f /tmp/hg_flash_cp_err.$$
# The bootloader reboots as soon as it has the last block, so the drive vanishes under cp: an "extended attributes" or
# I/O error right after the copy is normal. It counts as success when the drive then disappears.
for i in $(seq 1 50); do [ -d "$VOL" ] || break; sleep 0.2; done
if [ -d "$VOL" ]; then
  echo "The copy did not finish (the drive is still there). cp said: ${ERR:-nothing} (exit $RC). Try again."
  exit 1
fi
[ $RC -ne 0 ] && echo "(cp complained as the drive disappeared - that is the normal end of a UF2 copy.)"
echo "Copied; the band is restarting with the new firmware."
show_stat; exit $?
