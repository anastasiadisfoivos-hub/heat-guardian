# tomorrow — Heat Guardian Tomorrow Engine (B4)

Physics-based planning of tomorrow's safe hours — **SIMULATION**, not a medical prediction.
Weather data by Open-Meteo.com.

    pip install --break-system-packages --no-deps -e /home/claude/hg_ai/tomorrow   # once (makes `python -I -m tomorrow` work)
    python -I -m tomorrow --demo --home-class B --out plan.json --ble-out frames.bin   # offline, CONSTRUCTED DEMO DAY
    python -I -m tomorrow --lat 37.98 --lon 23.73 --home-class B --twin twin.json --out plan.json   # nightly
    cd /home/claude/hg_ai/tomorrow && python -m pytest -q tests                      # ~5 min (velders physics)

Spec: ARCHITECTURE §6. Results, sources and open risks: REPORT_TOMORROW.md.
