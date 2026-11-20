// node tools/test_parser.js  — runs the page's parser (from index.html when built, else tools/core.js) over the four transcripts
const fs = require('fs'), path = require('path'), vm = require('vm');
const dir = path.join(__dirname, '..');
let src; const html = path.join(dir, 'index.html');
if (fs.existsSync(html)) { src = /<script id="core">([\s\S]*?)<\/script>/.exec(fs.readFileSync(html, 'utf8'))[1]; console.log('parser: from index.html'); }
else { src = fs.readFileSync(path.join(__dirname, 'core.js'), 'utf8'); console.log('parser: from tools/core.js'); }
const ctx = { module: {} }; vm.createContext(ctx); vm.runInContext(src + ';this.HG=HG;', ctx); const HG = ctx.HG;
let fail = 0; const ok = (c, msg) => { console.log((c ? '  ok   ' : '  FAIL ') + msg); if (!c) fail++; };
const C = t => t ? t.clock : null;
function runLines(lines) { const s = HG.fresh(), kinds = {}; for (const l of lines) { if (!l) continue; const r = HG.parseLine(l); const k = r ? r.kind : 'null'; kinds[k] = (kinds[k] || 0) + 1; HG.applyRec(s, r); } return { s, kinds }; }
const read = f => fs.readFileSync(path.join(dir, f), 'utf8').split('\n');
function checkPress(s, label) {
  const R = s.rungs;
  ok(s.phase === 'end' && s.minutes.filter(Boolean).length === 110, label + 'phase end, 110 minutes');
  ok(C(R.water.lit) === '13:25' && C(R.water.pressed) === '13:31', label + 'water 13:25, she pressed 13:31 (' + C(R.water.lit) + ', ' + C(R.water.pressed) + ')');
  ok(C(R.still.lit) === '13:51' && C(R.cool.lit) === '13:51' && C(R.cool.repeat) === '14:01', label + 'still heating 13:51, go cool 13:51, again 14:01');
  ok(C(R.cool.pressed) === '14:10' && C(R.worked.lit) === '14:30', label + 'cool pressed 14:10, Μπράβο 14:30 (' + C(R.cool.pressed) + ', ' + C(R.worked.lit) + ')');
  ok(!R.family.lit && !R.seeme.lit && C(s.allClear) === '14:46', label + 'no family alert, all-clear 14:46 (' + C(s.allClear) + ')');
}
function checkNoresp(s, label) {
  const Q = s.rungs;
  ok(C(Q.water.lit) === '13:25' && C(Q.water.repeat) === '13:35' && !Q.water.pressed && C(Q.water.noResponse) === '13:45', label + 'water 13:25, again 13:35, no press, no response 13:45');
  ok(C(Q.family.lit) === '13:45' && Q.family.why === 'no response', label + 'family alerted 13:45 (no response)');
  ok(!Q.cool.lit && !Q.family.again && !Q.seeme.lit && C(s.allClear) === '14:46', label + 'b7t pid 90862: no go-cool step (no COOL alert), no second family note, all-clear 14:46');
  ok(!Q.worked.lit && !Q.water.pressed && !Q.cool.pressed, label + 'no press, no Μπράβο');
}
console.log('BLE (b7n #R/#E) transcript_ble_press.txt');
let { s, kinds } = runLines(read('transcript_ble_press.txt'));
console.log('  kinds', JSON.stringify(kinds)); ok(!kinds.other, 'every line recognised');
ok(s.el === 'velders-pid90862' && s.minutes[29].trueCore === 37.68 && s.minutes[29].f20 === 37.8 && s.minutes[29].level === 1, 'el=, sc= (true core), f=, lv= read');
ok(s.gauge.step === 'green' && s.gauge.dot != null && s.lines.w === 37.75, 'gauge step + dot from the line');
checkPress(s, 'BLE ');
console.log('BLE transcript_ble_noresp.txt');
({ s, kinds } = runLines(read('transcript_ble_noresp.txt'))); ok(!kinds.other, 'every line recognised'); ok(s.noresp, 'nr=1 seen');
checkNoresp(s, 'BLE ');
console.log('BLE thinned (only every 5th minute line + changes kept, all #E kept): the slow-link case');
const thin = []; let key = '';
for (const l of read('transcript_ble_noresp.txt')) { const m = /^#R k=(\d+) .*?st=(\S+) lv=(\S+) ld=(\S+) rm=(\S+) ga=(\S+)/.exec(l);
  if (!m) { thin.push(l); continue; } const kk = m.slice(2).join('|'); if (+m[1] % 5 === 0 || kk !== key || +m[1] === 109) thin.push(l); key = kk; }
({ s } = runLines(thin)); ok(s.minutes.filter(Boolean).length < 60, 'thinned: ' + s.minutes.filter(Boolean).length + ' minute lines'); checkNoresp(s, 'thinned ');
console.log('USB (# DEMO) transcript_press.txt / transcript_noresp.txt (b7n, fallback)');
({ s, kinds } = runLines(read('transcript_press.txt'))); ok(!kinds.other, 'every line recognised'); checkPress(s, 'USB ');
({ s, kinds } = runLines(read('transcript_noresp.txt'))); ok(!kinds.other, 'every line recognised'); checkNoresp(s, 'USB ');
console.log('accuracy (from the band\'s own c / f / sc only)');
({ s } = runLines(read('transcript_ble_press.txt'))); let A = HG.accuracy(s);
const m29 = s.minutes[29], m9 = s.minutes[9];
ok(A.nEst === 110 && Math.abs(A.est[29].err - Math.abs(m29.bandCore - m29.trueCore)) < 1e-9, 'estimate error = |c - sc| per minute, 110 minutes');
ok(A.nFc === 90 && A.fc[0].k === 20 && A.fc[0].from === 0 && Math.abs(A.fc[0].err - (s.minutes[0].f20 - s.minutes[20].trueCore)) < 1e-9, 'forecast check: f printed at k-20 vs sc at k, first at 13:20');
console.log('  press run: estimate MAE ' + A.mae.toFixed(3) + ' C, within 0.3: ' + Math.round(A.within * 100) + '%, within 0.5: ' + Math.round(A.within5 * 100) + '%; forecast MAE ' + A.fcMae.toFixed(3) + ' C, within 0.3: ' + Math.round(A.fcWithin * 100) + '%, within 0.5: ' + Math.round(A.fcWithin5 * 100) + '%');
ok(A.within5 === A.est.filter(x => x.err <= 0.5 + 1e-9).length / A.est.length && A.fcWithin5 === A.fc.filter(x => Math.abs(x.err) <= 0.5 + 1e-9).length / A.fc.length, 'within +-0.5 C shares (the page\'s plain lines)');
({ s } = runLines(read('transcript_ble_press.txt').slice(0, 10))); A = HG.accuracy(s);
ok(A.nFc === 0 && A.fcMae === null && A.nEst > 0, 'no forecast check before 20 simulated minutes (shown as a dash)');
ok(HG.accuracy(HG.fresh()).mae === null, 'nothing received: every number is null (a dash)');
console.log('binary frames');
const st = new Uint8Array(20); st[0] = 0x01; st[1] = 1; st[2] = 3742 & 255; st[3] = 3742 >> 8; st[17] = 5; st[19] = HG.crc8(st, 19);
const ps = HG.parseStatus(st); ok(ps && ps.state === 'DRINK' && ps.core === 37.42 && ps.minuteCounter === 5, 'STATUS frame decode');
const ev = new Uint8Array(20); ev[0] = 3; ev[1] = 7; ev[9] = 17; ev[10] = 1; ev[19] = HG.crc8(ev, 19);
const pe = HG.parseEventFrame(ev); ok(pe && pe.name === 'LD_REMIND' && pe.seq === 7 && pe.arg === 1, 'EVENTS frame decode');
ok(HG.crc8(Uint8Array.from(Buffer.from('123456789')), 9) === 0xF4, 'crc8 check value 0xF4');
({ s } = runLines(read('transcript_ble_noresp.txt').slice(0, 40))); const w0 = s.rungs.water.repeat;
HG.applyRec(s, pe, true); ok(s.rungs.water.repeat === w0, 'an EVENTS frame is ignored while #E lines flow (no double count)');
const b = HG.fresh(); HG.applyRec(b, HG.parseLine('# REPLAY started (2 s per simulated minute, 220 s in all); `replay stop` = back to live now'));
for (let i = 0; i < 3; i++) { const f = new Uint8Array(20); f[0] = 1; f[2] = 3730 & 255; f[3] = 3730 >> 8; f[17] = 40 + i; f[19] = HG.crc8(f, 19); HG.applyRec(b, HG.parseStatus(f)); }
ok(b.k === 2 && b.clock === '13:02' && b.minutes[2].bandCore === 37.3, 'b7u fallback: STATUS frames drive the clock and band core');
console.log('tomorrow (plain summary of a Tomorrow Engine plan)');
const mk = adv => ({ date: '2026-11-22', attribution: 'Weather data by Open-Meteo.com', advice_gr: ['Αύριο καύσωνας', 'Έξοδος 06:00-07:00', 'Πίνετε άφθονα υγρά', 'Χλιαρό ντους'],
  details: { advice_ids: ['HEAT_DAY', 'SAFE_HOURS_T', 'DRINK_PLENTY', 'SHOWER'] }, display: { city: 'X', forecast_tmax: 38.8 },
  hours: adv.split('').map((c, h) => ({ h, t_out: 20 + h / 2, core_indoor: 36.5, advice: { o: 'OK', s: 'SHORT', X: 'AVOID' }[c], safe: c === 'o' && h >= 6 && h < 20 })) });
let T = HG.tomorrow(mk('ooooooossXXXXXXsXXssssoo'));
ok(T.ok && JSON.stringify(T.risky) === '[[9,15],[16,18]]' && T.verdict === 'Too hot for her to go out from 09:00 to 18:00.', 'risky = AVOID hours, verdict spans first..last: ' + T.verdict);
ok(JSON.stringify(T.best) === '[6,7]' && T.bestText === 'Best time to go out: 06:00–07:00', 'best time = first run of safe hours: ' + T.bestText);
ok(T.band.length === 3 && T.band[1].en === 'Go out 06:00–07:00' && T.band[0].en === 'Heat wave tomorrow', 'band lines: first 3 engine strings, English by id');
ok(T.tmax === 38.8 && T.out.length === 24 && T.body.length === 24, 'forecast max from the plan display block, 24 hourly values');
T = HG.tomorrow(mk('oooooooooooooooooooooooo')); ok(T.risky.length === 0 && T.verdict === 'No risky hours for her tomorrow.' && T.best[0] === 6, 'calm day: no risky hours');
T = HG.tomorrow(mk('XXXXXXXXXXXXXXXXXXXXXXXX')); ok(!T.best && T.bestText === 'No good time to go out tomorrow', 'no safe hour: says so');
ok(!HG.tomorrow({ hours: [] }).ok && !HG.tomorrow(null).ok, 'not a plan: refused');
const real = path.join(dir, 'tomorrow_plan.json');
if (fs.existsSync(real)) {
  const P = JSON.parse(fs.readFileSync(real, 'utf8')); T = HG.tomorrow(P);
  ok(T.ok && T.out.every((v, i) => v === P.hours[i].t_out) && T.body.every((v, i) => v === P.hours[i].core_indoor), 'tomorrow_plan.json (' + T.city + ' ' + T.date + '): chart values are the plan\'s own');
  console.log('  ' + T.verdict + ' ' + T.bestText + '; max ' + T.tmax + ' C');
}
console.log(fail ? fail + ' FAILED' : 'ALL PASS'); process.exit(fail ? 1 : 0);
