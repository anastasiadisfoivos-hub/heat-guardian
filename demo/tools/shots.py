# python3 tools/shots.py  (with `python3 -m http.server 8765` running in /home/claude/sim_stage)
# Shots at 1920x1080: start / family alert / end of both recordings, a live preview run of each (checked every second for a
# bare dash or NaN), the Tomorrow view, the Tomorrow view with the file missing. `python3 tools/shots.py norepo` = shot 9 only.
import re
import sys
from playwright.sync_api import sync_playwright
B = 'http://localhost:8765/index.html'
OUT = '/home/claude/sim_stage/shots/'
WATCH = ['stEn', 'stGr', 'clock', 'roBand', 'aMae', 'aFcMae', 'sTxt']
BAD = re.compile(r'NaN|undefined|^\s*[-—]+\s*$|--')
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    if len(sys.argv) > 1 and sys.argv[1] == 'norepo':   # index.html built WITHOUT a REPO_URL: only this shot (no QR / source line)
        pg.goto(B + '?preview=1&seek=109'); pg.wait_for_timeout(1500); pg.screenshot(path=OUT + '9_no_repo_url.png')
        print('qr hidden:', pg.eval_on_selector('#eQr', 'e => e.hidden'), '| src hidden:', pg.eval_on_selector('#eSrc', 'e => e.hidden'), '| errors:', errs)
        br.close(); sys.exit(0)
    for name, q in [('1_start', 'seek=1'), ('2_escalation_middle', 'seek=53'), ('3_end', 'seek=109'),
                    ('4_noresp_family_alert_1345', 'seek=45&noresp=1'), ('4b_press_family_note_1351', 'seek=51'),
                    ('6_noresp_end', 'seek=109&noresp=1')]:
        pg.goto(B + '?preview=1&' + q); pg.wait_for_timeout(1800)
        pg.screenshot(path=OUT + name + '.png')
        print(name, '|', pg.inner_text('#stEn'), '|', pg.inner_text('#stGr').replace('\n', ' '), '|', pg.inner_text('.acc').replace('\n', ' / '))
    # live preview runs through the real buttons at 1 s per minute: every second, no bare dash / NaN in the watched fields
    for nr in (0, 1):
        pg.goto(B); pg.click('#btnPreview')
        if nr: pg.check('#noresp')
        pg.select_option('#speed', '1'); pg.click('#btnGo')
        bad = []
        for t in range(118):
            pg.wait_for_timeout(1000)
            for i in WATCH:
                v = pg.inner_text('#' + i)
                if BAD.search(v): bad.append((t, i, v))
            if t == 1: pg.screenshot(path=OUT + ('0_live_warm_noresp.png' if nr else '0_live_warm.png'))
            if nr and t == 52: pg.screenshot(path=OUT + '5_live_noresp_preview_t52s.png')
        print('live', 'noresp' if nr else 'press', '| end state:', pg.inner_text('#stEn'), '| bad values:', bad[:6], len(bad))
    pg.click('#btnStop'); pg.wait_for_timeout(500); print('after stop:', pg.inner_text('#stEn'))
    pg.goto(B + '?preview=1&seek=53&view=tomorrow'); pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT + '7_tomorrow.png')
    print('tomorrow verdict:', pg.inner_text('#tVerdict'), '|', pg.inner_text('#tBest'), '| step 3:', pg.inner_text('#tsPlan'))
    pg.route('**/tomorrow_plan.json', lambda r: r.fulfill(status=404, body='not found'))
    pg.goto(B + '?view=tomorrow'); pg.wait_for_timeout(1200)
    pg.screenshot(path=OUT + '8_tomorrow_missing.png')
    print('missing file line:', pg.inner_text('#tMiss'))
    errs = [e for e in errs if 'tomorrow_plan.json' not in e and '404' not in e]   # the 404 above is on purpose
    print('evidence:', pg.inner_text('#evi').replace('\n', ' | '))
    print('errors:', errs)
    br.close()
