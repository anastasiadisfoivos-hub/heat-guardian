# python3 tools/build.py  -> index.html (inlines tools/core.js, tools/qr.js, the build constants and the two transcripts)
import hashlib, json, os, re
d = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(d)

# ---- build constants (the EVIDENCE corner and the person / population lines). Only real values. ----
FW = '09-guardian-0.9.17-demo-b7g'   # HG_FW_VERSION of the release firmware; the host build of b7g emits the transcripts byte-identical to b7t
COMMIT = '9f9d483'                # git short hash of that firmware build (branch b17-demo-b7g in the firmware repo)
# frozen model hash = sha256 over `sha256sum` lines of every file in fw/09_guardian/frozen/ (sorted by name, C locale),
#   i.e.  cd fw/09_guardian/frozen && LC_ALL=C sha256sum $(LC_ALL=C ls) | sha256sum
# frozen/ is byte-identical to tag hg2-freeze-10 (FROZEN_SHA256.txt still lists hg2-freeze-6 for 10 of its 30 files: the known
# SYNC_FROZEN failure; the hash here is of the files actually compiled into the band).
FROZEN = 'baef78b19790ab310db992d53fdc959fe669fabab72931826202f22aa5a7da07'
PID = '90862'                      # the Virtual Elder of the embedded trace (hg_demo_trace.h header, HG_DEMO_ELDER)
WHO = 'Simulated person: a 74-year-old woman'   # velders draw_one pid 90862: female, age 74.2
# Population line. Source: wt_b15/model/runs/b2b_v5aug/eval_v5.json "sim_v5" -> "v5_AR" (= freeze-6 core path, the same
# hg2_step.c / hg2_weights.c / hg_kf.c the band runs), also model/REPORT_B2b.md section 3 table, row "SIM-DEV v5", column freeze-6:
# 100 SIM-DEV calibration persons (never trained on), now MAE 0.234 C, +20 min MAE 0.289 C, 650,339 minutes.
# No documented "within +-0.5 C" share and no number over all 500 persons exists, so neither is shown.
POP_TEXT = 'Across 100 other simulated elders the model never trained on: estimate 0.23 °C off on average, 20-minute prediction 0.29 °C.'
REPO_URL = 'https://github.com/anastasiadisfoivos-hub/heat-guardian'   # GitHub repo of the source code; empty = no QR / source line
if os.environ.get('HG_REPO_URL') is not None:
    REPO_URL = os.environ['HG_REPO_URL']   # shots only: a dummy URL to test the QR

FWREPO = os.environ.get('HG_FW_REPO', '/home/claude/wt_offfix')
fz = os.path.join(FWREPO, 'fw', '09_guardian', 'frozen')
if os.path.isdir(fz):   # check the constant against the firmware repo when it is there
    lines = ''.join('%s  %s\n' % (hashlib.sha256(open(os.path.join(fz, f), 'rb').read()).hexdigest(), f) for f in sorted(os.listdir(fz)))
    assert hashlib.sha256(lines.encode()).hexdigest() == FROZEN, 'FROZEN constant does not match ' + fz
assert re.match(r'^[0-9a-f]{7,12}$', COMMIT) and PID.isdigit(), 'set COMMIT / PID'
build = dict(FW=FW, COMMIT=COMMIT, FROZEN12=FROZEN[:12], PID=PID, WHO=WHO, POP_TEXT=POP_TEXT, REPO_URL=REPO_URL)

t = open(os.path.join(d, 'index.template.html'), encoding='utf-8').read()
t = t.replace('/*CORE*/', open(os.path.join(d, 'core.js'), encoding='utf-8').read())
t = t.replace('/*QR*/', open(os.path.join(d, 'qr.js'), encoding='utf-8').read())
t = t.replace('/*BUILD*/', 'var BUILD = ' + json.dumps(build, ensure_ascii=False) + ';')
tw = json.load(open(os.path.join(root, 'twin_week.json'), encoding='utf-8'))   # tools/make_twin_week.py (SIMULATION: 7 simulated days, real Body Twin code)
tw = {k: tw[k] for k in ('pid', 'days', 'defaults', 'nights', 'learned', 'truth', 'what')}
t = t.replace('/*TWIN_WEEK*/', 'window.TWIN_WEEK = ' + json.dumps(tw, ensure_ascii=False) + ';')
t = t.replace('/*TX_BLE_PRESS*/', open(os.path.join(root, 'transcript_ble_press.txt'), encoding='utf-8').read())
t = t.replace('/*TX_BLE_NORESP*/', open(os.path.join(root, 'transcript_ble_noresp.txt'), encoding='utf-8').read())
open(os.path.join(root, 'index.html'), 'w', encoding='utf-8').write(t)
print('index.html', len(t), 'bytes', '| REPO_URL', repr(REPO_URL))
