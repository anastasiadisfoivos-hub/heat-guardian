#!/bin/bash
# make_tomorrow.command : writes tomorrow_plan.json beside index.html (the "Tomorrow" view of the page).
# The Tomorrow Engine runs the simulated elder (Virtual Elder pid 90862, the demo elder, with the Body Twin learned over
# 7 simulated days of wear: tomorrow_engine/twin_learned_pid90862.json) through a hot city's REAL
# Open-Meteo forecast for tomorrow. SIMULATION, not a medical prediction. Weather data by Open-Meteo.com.
#
#   ./make_tomorrow.command                       Alice Springs (default)
#   ./make_tomorrow.command --city durban         also: asuncion, brisbane, perth, adelaide, cordoba
#   ./make_tomorrow.command --lat -25.26 --lon -57.58 --name "Asuncion" --country Paraguay
#   ./make_tomorrow.command --home-class B        A, B, C (default) or D
#   ./make_tomorrow.command --pid 90416           another Virtual Elder (needs tomorrow_engine/twin_pid<id>.json)
#
# First run: makes a Python environment in ~/.hgtomorrow and installs numpy, pandas, jsonschema (~1 min).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="${HG_TOMORROW_VENV:-$HOME/.hgtomorrow}"
PY="${HG_PYTHON:-python3}"

command -v "$PY" >/dev/null 2>&1 || { echo "FAILED: no python3. Install it with: xcode-select --install"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "FAILED: needs Python 3.9 or newer ($("$PY" -V 2>&1))"; exit 1; }

if [ ! -x "$VENV/bin/python" ]; then
  echo "Making the Python environment in $VENV (once)"
  "$PY" -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c 'import numpy, pandas, jsonschema' >/dev/null 2>&1; then
  echo "Installing numpy, pandas, jsonschema (once)"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -r "$HERE/tomorrow_engine/requirements.txt"
fi

"$VENV/bin/python" -I "$HERE/tomorrow_engine/run_city.py" --pid "${HG_PID:-90862}" --out "$HERE/tomorrow_plan.json" --cache-dir "$VENV/cache" "$@"
