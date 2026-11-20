/* SIM-STAGE core: parses the band's real output and folds it into one stage state.
 * Pure (no DOM): index.html inlines this file; tools/test_parser.js runs it in node against the transcripts.
 * Every value on the page comes from a line or frame the band sent. Line formats: see README.txt. */
var HG = (function () {
  'use strict';
  var STN = ['OK', 'DRINK', 'COOL', 'CHECK', 'DANGER', 'IMOK', 'NOT_WORN', 'BATTERY', 'HELP'];
  /* STATUS frame byte 1 bits 0-2 (frozen/hg_frames.h): 0 OK 1 DRINK 2 COOL 3 DANGER 4 IMOK 5 BATTERY 6 CHECK 7 HELP */
  var STATUS_CODE = ['OK', 'DRINK', 'COOL', 'DANGER', 'IMOK', 'BATTERY', 'CHECK', 'HELP'];
  var EVN = { 8: 'WARN_SHOWN', 12: 'ALL_CLEAR', 17: 'LD_REMIND', 18: 'LD_DONE', 19: 'LD_WORKED', 20: 'LD_ESCALATED', 21: 'LD_NOTE' };
  var GAUGE_STEPS = ['green', 'yellow-green', 'yellow', 'orange', 'red'];

  function num(s) { var v = parseFloat(s); return isFinite(v) ? v : null; }
  function hm(s) { var p = s.split(':'); return (+p[0]) * 60 + (+p[1]); }

  /* one text line -> a record (or null). Lines that do not start with '#' are not ours (hex records). */
  function parseLine(raw) {
    var line = String(raw).replace(/\r$/, '');
    if (line.charAt(0) !== '#') return null;
    if (/^#R /.test(line)) return parseR(line.slice(3));
    if (/^#E /.test(line)) return parseE(line.slice(3));
    var demo = /^# DEMO /.test(line);
    var b = demo ? line.slice(7) : line.slice(2);
    var m;
    if (demo && (m = /^(\d\d:\d\d) t=(\d+)s \| SIM input T1 (\S+) T2 (\S+) air (\S+) RH (\S+) HR (\S+) \| SIM true core (\S+) \| band core (\S+) f20 (\S+) -> (\w+) level (\d+)/.exec(b)))
      return { kind: 'minute', mod: hm(m[1]), clock: m[1], t: +m[2], t1: num(m[3]), t2: num(m[4]), air: num(m[5]), rh: num(m[6]), hr: num(m[7]),
               trueCore: num(m[8]), bandCore: num(m[9]), f20: num(m[10]), state: m[11], level: +m[12] };
    if ((m = /^REPLAY started \((\d+) s per simulated minute, (\d+) s in all\)/.exec(b))) return { kind: 'replayStarted', S: +m[1], total: +m[2] };
    if ((m = /^REPLAY start: .*?\((.+?) person, (\d+) min from (\d\d:\d\d)\), (\d+) s per simulated minute/.exec(b)))
      return { kind: 'replayStart', who: m[1], n: +m[2], startMod: hm(m[3]), S: +m[4] };
    if ((m = /^REPLAY warm-up done: state (\w+); showing (\d\d:\d\d)-(\d\d:\d\d)/.exec(b))) return { kind: 'warmDone', state: m[1], from: hm(m[2]), to: hm(m[3]) };
    if (/^REPLAY end of the episode/.test(b)) return { kind: 'replayEnd' };
    if ((m = /^REPLAY stop why=(.*?):/.exec(b))) return { kind: 'replayStop', why: m[1] };
    if ((m = /^REPLAY noresp: (.*)/.exec(b))) return { kind: 'replayNoresp', text: m[1], demo: demo };
    if (/^REPLAY (already running|refused|not running)/.test(b) || /^REPLAY: replay \[/.test(b)) return { kind: 'replayMsg', text: b };
    if ((m = /^STATE (\d+) screen (\d+) level (\d+) tiers (\d+) core (\S+) sd (\S+) f20 (\S+) why (\S+) worn (\d+) check (\d+) family (\d+)/.exec(b)))
      return { kind: 'state', state: STN[+m[1]] || '?', screen: +m[2], level: +m[3], core: num(m[5]), f20: num(m[7]), family: +m[11], demo: demo };
    if ((m = /^GAUGE (\S+) -> (\S+) f20 (\S+) dot (-?\d+) lines (\S+)\/(\S+)\/(\S+)/.exec(b)))
      return { kind: 'gauge', from: m[1], to: m[2], f20: num(m[3]), dot: +m[4], lineW: num(m[5]), lineC: num(m[6]), lineD: num(m[7]), demo: demo };
    if ((m = /^ALERT (DRINK|COOL) shown( soft)?.*?f20 (\S+)\)/.exec(b))) return { kind: 'alert', what: m[1], soft: !!m[2], f20: num(m[3]), demo: demo };
    if ((m = /^ALERT (\S+) (held|audit|hold limit)/.exec(b))) return { kind: 'held', what: m[1], demo: demo };
    if ((m = /^ALERT all-clear peak=(\d+) minutes=(\d+)/.exec(b))) return { kind: 'allClear', peak: +m[1], minutes: +m[2], demo: demo };
    if ((m = /^EVT seq=(\d+) type=(\d+) (\S+) arg=(\d+)/.exec(b))) return { kind: 'evt', seq: +m[1], type: +m[2], name: m[3], arg: +m[4], demo: demo };
    if ((m = /^LADDER (\S+) arg=(\d+) state=(\S+)/.exec(b))) return { kind: 'ladder', name: m[1], arg: +m[2], state: m[3], demo: demo };
    if ((m = /^BUTTON press -> ladder (\w+) \((\S+)\)/.exec(b))) return { kind: 'button', meaning: m[1], ladder: m[2], demo: demo };
    if ((m = /^STAT fw=(\S+)/.exec(b))) return { kind: 'fw', version: m[1] };
    if ((m = /^STAT gauge: (\S+) dot=(-?\d+) lines water=(\S+) cool=(\S+) danger=(\S+)/.exec(b)))
      return { kind: 'gaugeStat', step: m[1], dot: +m[2], lineW: num(m[3]), lineC: num(m[4]), lineD: num(m[5]) };
    return { kind: 'other', text: b, demo: demo };
  }

  /* b7n (0.9.17-demo-b7n, 8947e2c) compact BLE lines, 09_guardian.ino demoStart()/demoLine()/demoService():
   *   #R start el=velders-pid90416 nr=0 s=2 n=110 t0=13:00      #R warm done st=OK      #R end      #R stop why=command
   *   #R k=29 t=13:29 c=37.42 f=37.70 sc=37.75 st=DRINK lv=1 ld=remind rm=water ga=yellow dot=4 fam=0 nr=0 b=0
   *   #E k=29 fam=0 ev=WARN_SHOWN.1,LD_REMIND.1      (right after a minute line; never skipped; holds presses since the last line) */
  var EVT_TYPE = { NUDGE_SHOWN: 1, NUDGE_DONE: 2, NUDGE_MISSED: 3, IM_OK: 4, HELP: 5, HELP_CANCEL: 6, WARN_SHOWN: 8, ALL_CLEAR: 12,
                   LD_REMIND: 17, LD_DONE: 18, LD_WORKED: 19, LD_ESCALATED: 20, LD_NOTE: 21 };
  function kvOf(b) { var kv = {}; b.split(' ').forEach(function (p) { var i = p.indexOf('='); if (i > 0) kv[p.slice(0, i)] = p.slice(i + 1); }); return kv; }
  function evList(v) { return (v && v !== '-') ? v.split(',').map(function (e) { var q = e.split('.'); return { kind: 'evt', type: EVT_TYPE[q[0]] || 0, name: q[0], arg: +q[1] }; }) : []; }
  function parseR(b) {
    var m;
    if ((m = /^start (.*)/.exec(b))) { var a = kvOf(m[1]);
      return { kind: 'replayStart', el: a.el || null, noresp: +a.nr || 0, S: +a.s || 2, n: +a.n || 110, startMod: a.t0 ? hm(a.t0) : 780, who: a.el || 'sim/velders', r: true }; }
    if (/^warm done/.test(b)) return { kind: 'warmDone', r: true };
    if (/^end\b/.test(b)) return { kind: 'replayEnd' };
    if ((m = /^stop why=(.*)/.exec(b))) return { kind: 'replayStop', why: m[1] };
    if (/^k=/.test(b)) {
      var kv = kvOf(b), pick = function (a, c) { return kv[a] != null ? kv[a] : kv[c]; };   // final names, then the earlier b7n draft names
      return { kind: 'rmin', k: +kv.k, clock: kv.t, mod: hm(kv.t || '0:0'), bandCore: num(pick('c', 'core')), f20: num(pick('f', 'f20')), trueCore: num(kv.sc),
               state: kv.st, level: kv.lv != null ? +kv.lv : null, ladder: kv.ld, rm: kv.rm, ga: kv.ga, dot: kv.dot != null ? +kv.dot : null,
               fam: kv.fam === '1', noresp: kv.nr === '1', btnIgnored: +pick('b', 'btn') || 0, evs: evList(kv.ev) };
    }
    return { kind: 'other', text: '#R ' + b };
  }
  function parseE(b) { var kv = kvOf(b); return { kind: 'emin', k: +kv.k, fam: kv.fam === '1', evs: evList(kv.ev) }; }

  function crc8(p, n) { var c = 0; for (var i = 0; i < n; i++) { c ^= p[i]; for (var k = 0; k < 8; k++) c = (c & 0x80) ? ((c << 1) ^ 0x07) & 0xFF : (c << 1) & 0xFF; } return c; }
  /* STATUS (HG service 0001, 20 bytes, frozen/hg_frames.c hg_status_pack) */
  function parseStatus(u8) {
    if (!u8 || u8.length !== 20 || (u8[0] & 0x0F) !== 0x01 || crc8(u8, 19) !== u8[19]) return null;
    var core = u8[2] | (u8[3] << 8);
    return { kind: 'status', state: STATUS_CODE[u8[1] & 7], family: !!(u8[0] & 0x10), core: core ? core / 100 : null,
             minuteCounter: u8[17] | (u8[18] << 8) };
  }
  /* EVENTS (HG service 0004, 20 bytes, ECOSYSTEM_SPEC.md §5): [0]=0x03 [1-2] seq [9] type [10] arg [19] crc8 */
  function parseEventFrame(u8) {
    if (!u8 || u8.length !== 20 || u8[0] !== 0x03 || crc8(u8, 19) !== u8[19]) return null;
    var t = u8[9];
    return { kind: 'evt', seq: u8[1] | (u8[2] << 8), type: t, name: EVN[t] || ('type' + t), arg: u8[10], frame: true };
  }

  function fresh() {
    return {
      phase: 'idle',            // idle | warm | run | end | stopped
      S: 2, n: 110, startMod: 780, who: null,
      minutes: [],              // by simulated minute k: { k, mod, trueCore, bandCore, f20, state, level }
      k: -1, clock: null,
      state: null, level: 0, family: false,
      f20: null, f20k: null,    // the latest forecast the band printed, and at which minute
      lines: { w: 37.75, c: 38.15, d: 38.50, fromBand: false },   // source defaults (hg_ga_lines with no learned base); replaced by the band's GAUGE line
      gauge: { step: null, dot: null },
      alert: null, allClear: null,
      rungs: {
        water: { lit: null, repeat: null, pressed: null, noResponse: null },
        still: { lit: null },
        cool: { lit: null, repeat: null, pressed: null, noResponse: null },
        seeme: { lit: null, pressed: null, why: null },
        family: { lit: null, why: null, again: null },
        worked: { lit: null }
      },
      ladderState: 'idle', active: null,
      presses: [], seen: {}, pending: [], minuteLines: false, rLines: false, rm: null, btnIgnored: 0, el: null, noresp: false,
      statusBase: null, fw: null, msg: null, lastLine: null, nLines: 0
    };
  }

  function clockOf(s, k) { var mod = s.startMod + Math.max(0, k); return pad(Math.floor(mod / 60) % 24) + ':' + pad(mod % 60); }
  function pad(x) { return (x < 10 ? '0' : '') + x; }

  function applyEvt(s, r, k) {
    if (r.seq != null) { if (s.seen[r.seq]) return; s.seen[r.seq] = 1; }
    var t = { k: k, clock: clockOf(s, k) };
    var R = s.rungs, step = r.arg;
    switch (r.type) {
      case 17: { var g = step === 2 ? R.cool : R.water;      // LD_REMIND
        if (!g.lit || g.pressed) { g.lit = t; g.pressed = null; g.repeat = null; g.noResponse = null; } else g.repeat = t;
        s.active = step === 2 ? 'cool' : 'water'; s.ladderState = 'remind'; break; }
      case 18: { var g2 = step === 2 ? R.cool : R.water; g2.pressed = t; s.ladderState = 'check20'; s.presses.push(t); break; }   // LD_DONE
      case 19: R.worked.lit = t; s.active = 'worked'; s.ladderState = 'done'; break;                                            // LD_WORKED
      case 20: R.seeme.lit = t; R.seeme.why = step === 1 ? 'danger line' : 'still heating'; R.family.lit = R.family.lit || t;  // LD_ESCALATED (+ family alert)
        R.family.why = R.family.why || 'escalation'; s.active = 'seeme'; s.ladderState = 'escalated'; break;
      case 21:                                                                                                                 // LD_NOTE
        if (step === 1) { R.still.lit = t; }
        else if (step === 2) { var g3 = s.active === 'cool' ? R.cool : R.water; g3.noResponse = t; if (R.family.lit) R.family.again = t; else { R.family.lit = t; R.family.why = 'no response'; } s.active = 'family'; }
        else if (step === 3) { R.seeme.pressed = t; s.presses.push(t); }
        break;
      case 12: s.allClear = t; break;
      default: break;
    }
  }

  function flushPending(s) { var p = s.pending; s.pending = []; for (var i = 0; i < p.length; i++) applyRec(s, p[i], true); }

  /* fold one record into the state. now=true: attribute to the current minute without queueing */
  function applyRec(s, r, now) {
    if (!r) return s;
    s.nLines++;
    var k = s.k < 0 ? 0 : s.k;
    // events printed by guardianMinute() come just BEFORE that minute's "# DEMO hh:mm" line: hold them for it (USB);
    // press-driven lines (LD_DONE, LD_NOTE 3, BUTTON) come after the minute line: they belong to the current minute.
    if (!now && s.minuteLines && s.phase === 'run' && r.demo &&
        (r.kind === 'state' || r.kind === 'gauge' || r.kind === 'alert' || r.kind === 'allClear' ||
         (r.kind === 'evt' && r.type !== 18 && !(r.type === 21 && r.arg === 3)))) { s.pending.push(r); return s; }
    if (!now && s.minuteLines && s.phase === 'run' && s.pending.length && r.kind === 'minute') { /* flushed below with k+1 */ }
    switch (r.kind) {
      case 'replayStarted': { var keepFw = s.fw; var keepStatus = s.statusBase; Object.assign(s, fresh()); s.fw = keepFw; s.phase = 'warm'; s.S = r.S; s.n = Math.round(r.total / r.S) || s.n; s.statusBase = null; break; }
      case 'replayStart': if (s.phase === 'idle' || s.phase === 'end' || s.phase === 'stopped') { var f = s.fw; Object.assign(s, fresh()); s.fw = f; }
        s.phase = 'warm'; s.n = r.n; s.startMod = r.startMod; s.S = r.S; s.who = r.who; if (r.el) s.el = r.el; if (r.r) s.noresp = !!r.noresp; break;
      case 'warmDone': s.phase = 'run'; if (r.from != null) { s.startMod = r.from; s.n = r.to - r.from + 1; } break;
      case 'emin': {   // b7n `#E`: the EVENTS since the last line. A press can only happen between two minute lines,
        s.rLines = true; // so the press events (LD_DONE, LD_NOTE 3) belong to the minute before this line; the rest to this minute.
        if (r.fam) s.family = true;
        for (var j = 0; j < r.evs.length; j++) { var ev = r.evs[j], press = ev.type === 18 || (ev.type === 21 && ev.arg === 3);
          applyEvt(s, ev, press ? Math.max(0, r.k - 1) : r.k); }
        break; }
      case 'replayNoresp': s.noresp = true; break;
      case 'rmin': {   // BLE compact minute: band estimate, forecast, state, gauge, ladder and this minute's EVENTS
        s.rLines = true; if (s.phase === 'warm' || s.phase === 'idle') s.phase = 'run';
        if (s.minuteLines) break;   // USB long lines win when both arrive
        s.k = r.k; s.clock = r.clock;
        var pv = s.minutes[r.k] || {};
        s.minutes[r.k] = { k: r.k, mod: r.mod, trueCore: r.trueCore != null ? r.trueCore : (pv.trueCore != null ? pv.trueCore : null), bandCore: r.bandCore, f20: r.f20, state: r.state, level: r.level != null ? r.level : (pv.level || 0) };
        s.state = r.state; s.f20 = r.f20; s.f20k = r.k; if (r.level != null) s.level = r.level;
        if (r.ga) s.gauge = { step: r.ga, dot: r.dot != null ? r.dot : s.gauge.dot };
        s.noresp = r.noresp;
        if (r.fam) s.family = true;
        s.rm = r.rm; s.btnIgnored = r.btnIgnored;
        for (var e = 0; e < r.evs.length; e++) applyEvt(s, r.evs[e], r.k);
        if (r.ladder) s.ladderState = r.ladder;
        if (r.k >= s.n - 1) s.phase = 'end';
        break; }
      case 'minute': {
        s.minuteLines = true; if (s.phase === 'warm' || s.phase === 'idle') s.phase = 'run';
        var kk = r.mod - s.startMod; if (kk < 0) kk += 1440;
        s.k = kk; s.clock = r.clock;
        flushPending(s);
        s.minutes[kk] = { k: kk, mod: r.mod, trueCore: r.trueCore, bandCore: r.bandCore, f20: r.f20, state: r.state, level: r.level };
        s.state = r.state; s.level = r.level; s.f20 = r.f20; s.f20k = kk;
        break; }
      case 'status': {   // BLE: one STATUS per simulated minute while a replay runs
        if (s.phase !== 'warm' && s.phase !== 'run') break;
        if (s.minuteLines || s.rLines) break;   // USB minute lines / BLE #R lines are richer: they win
        if (s.statusBase == null) { s.statusBase = r.minuteCounter; s.phase = 'run'; }
        var k2 = r.minuteCounter - s.statusBase; if (k2 < 0) k2 += 65536; if (k2 <= s.k) k2 = s.k + 1;
        s.k = k2; s.clock = clockOf(s, k2);
        var prev = s.minutes[k2] || {};
        s.minutes[k2] = { k: k2, mod: s.startMod + k2, trueCore: null, bandCore: r.core, f20: prev.f20 != null ? prev.f20 : null, state: r.state, level: prev.level || 0 };
        s.state = r.state; s.family = r.family || s.family;
        if (k2 >= s.n - 1) s.phase = 'end';
        break; }
      case 'state': s.state = r.state; s.level = r.level; if (r.f20 != null) { s.f20 = r.f20; s.f20k = k; if (s.minutes[k]) s.minutes[k].f20 = s.minutes[k].f20 != null ? s.minutes[k].f20 : r.f20; } if (r.family) s.family = true; break;
      case 'gauge': s.gauge = { step: r.to, dot: r.dot }; s.lines = { w: r.lineW, c: r.lineC, d: r.lineD, fromBand: true };
        if (r.f20 != null) { s.f20 = r.f20; s.f20k = k; } break;
      case 'gaugeStat': s.lines = { w: r.lineW, c: r.lineC, d: r.lineD, fromBand: true }; break;
      case 'alert': s.alert = { what: r.what, k: k, clock: clockOf(s, k), soft: r.soft }; break;
      case 'allClear': s.allClear = { k: k, clock: clockOf(s, k) }; break;
      case 'evt': if (r.frame && s.rLines) break; applyEvt(s, r, k); break;
      case 'button': s.ladderState = r.ladder; break;
      case 'replayEnd': flushPending(s); s.phase = 'end'; break;
      case 'replayStop': s.phase = 'stopped'; break;
      case 'replayMsg': s.msg = r.text; break;
      case 'fw': s.fw = r.version; break;
      default: break;
    }
    return s;
  }

  /* gauge dot from a forecast, the band's own formula (hg_fw_ladder.c hg_ga_step): pos = (f20 - centre)/(line_d - centre)*10 */
  function dotFor(lines, f20) {
    if (f20 == null) return null;
    var centre = lines.w - 0.50, p = (f20 - centre) / (lines.d - centre) * 10;
    return Math.round(Math.max(-10, Math.min(10, p)));
  }

  /* model accuracy, ONLY from minutes the band printed with both values (b7n `#R ... c= f= sc=`, or the USB `# DEMO` line):
   *   estimate error  = |c(k) - sc(k)|                      (the band's estimate now vs the simulation's true core now)
   *   forecast error  = f(j) - sc(k), j = k - 20             (the forecast printed 20 simulated minutes earlier vs the truth now;
   *                     if minute k-20 was thinned away on a slow link, the nearest printed minute within k-22..k-18, its age shown) */
  var TOL = 0.3, TOL5 = 0.5;
  function accuracy(s) {
    var M = s.minutes, est = [], fc = [], last = null, lastF = null;
    for (var k = 0; k < M.length; k++) {
      var m = M[k]; if (!m || m.trueCore == null) continue;
      if (m.bandCore != null) { var e = Math.abs(m.bandCore - m.trueCore); est.push({ k: k, err: e }); last = { k: k, err: e }; }
      var j = -1; for (var d = 0; d <= 2 && j < 0 && k >= 20; d++) { if (M[k - 20 - d] && M[k - 20 - d].f20 != null) j = k - 20 - d; else if (d && M[k - 20 + d] && M[k - 20 + d].f20 != null) j = k - 20 + d; }
      if (j >= 0) { var fe = M[j].f20 - m.trueCore; fc.push({ k: k, from: j, err: fe }); lastF = { k: k, from: j, err: fe }; }
    }
    function mean(a, f) { if (!a.length) return null; var t = 0; for (var i = 0; i < a.length; i++) t += f(a[i]); return t / a.length; }
    return {
      tol: TOL, now: last, nEst: est.length,
      mae: mean(est, function (x) { return x.err; }),
      within: est.length ? est.filter(function (x) { return x.err <= TOL + 1e-9; }).length / est.length : null,
      fcNow: lastF, nFc: fc.length,
      fcMae: mean(fc, function (x) { return Math.abs(x.err); }),
      fcWithin: fc.length ? fc.filter(function (x) { return Math.abs(x.err) <= TOL + 1e-9; }).length / fc.length : null,
      tol5: TOL5,   // the page's plain lines: share of minutes within +-0.5 C
      within5: est.length ? est.filter(function (x) { return x.err <= TOL5 + 1e-9; }).length / est.length : null,
      fcWithin5: fc.length ? fc.filter(function (x) { return Math.abs(x.err) <= TOL5 + 1e-9; }).length / fc.length : null,
      est: est, fc: fc
    };
  }

  /* Tomorrow: plain-language summary of a Tomorrow Engine plan (tomorrow_plan.json, made by make_tomorrow.command).
   * Every number comes from the plan. Risky hours = the engine's AVOID hours; best time to go out = the engine's own
   * first run of safe hours (the same run its «Έξοδος hh:00-hh:00» line names). The English under each Greek band line
   * is a translation of that engine string, keyed by its id. */
  var TMR_EN = {
    HEAT_DAY: 'Heat wave tomorrow', SAFE_HOURS_T: 'Go out {t}', NO_SAFE_HOURS: 'Do not go out tomorrow',
    DRINK_PLENTY: 'Drink plenty of fluids', DRINK_NOW: 'Drink water now', MOVE_ERRAND_T: 'Do not go out at {t}',
    NIGHT_HEAT_T: 'Open the windows at {t}', NIGHT_CLOSED: 'Keep the windows closed', OPEN_AT_BEDTIME: 'Open the windows',
    CLOSE_MORNING: 'Close the windows', GO_COOL: 'Go somewhere cool', SHOWER: 'Lukewarm shower', STALE_FORECAST: "Yesterday's forecast"
  };
  function hh(h) { return pad(h % 24) + ':00'; }
  function runsOf(flags) { var out = [], s = -1; for (var h = 0; h <= flags.length; h++) { var f = h < flags.length && flags[h]; if (f && s < 0) s = h; if (!f && s >= 0) { out.push([s, h]); s = -1; } } return out; }
  function tomorrow(plan) {
    var H = plan && plan.hours;
    if (!H || H.length !== 24 || !H.every(function (x, i) { return x.h === i && typeof x.t_out === 'number' && typeof x.core_indoor === 'number' && x.advice; }))
      return { ok: false, why: 'tomorrow_plan.json is not a Tomorrow Engine plan (needs 24 hours)' };
    var D = plan.display || {}, risky = runsOf(H.map(function (x) { return x.advice === 'AVOID'; }));
    var best = runsOf(H.map(function (x) { return !!x.safe; }))[0] || null;
    var verdict = risky.length ? 'Too hot for her to go out from ' + hh(risky[0][0]) + ' to ' + hh(risky[risky.length - 1][1]) + '.'
                               : 'No risky hours for her tomorrow.';
    var ids = (plan.details && plan.details.advice_ids) || [], gr = plan.advice_gr || [];
    var band = gr.slice(0, 3).map(function (g, i) {
      var t = /(\d\d:\d\d(?:-\d\d:\d\d)?)/.exec(g), en = TMR_EN[ids[i]] || '';
      return { gr: g, en: en.replace('{t}', t ? t[1].replace('-', '\u2013') : '') };
    });
    var tmax = typeof D.forecast_tmax === 'number' ? D.forecast_tmax : Math.max.apply(null, H.map(function (x) { return x.t_out; }));
    return {
      ok: true, date: plan.date, city: D.city || null, country: D.country || '', tmax: tmax,
      risky: risky, best: best, verdict: verdict,
      bestText: best ? 'Best time to go out: ' + hh(best[0]) + '\u2013' + hh(best[1]) : 'No good time to go out tomorrow',
      band: band, out: H.map(function (x) { return x.t_out; }), body: H.map(function (x) { return x.core_indoor; }),
      fetchedAt: D.fetched_at || (plan.details && plan.details.fetched_at) || null, attribution: plan.attribution || 'Weather data by Open-Meteo.com',
      source: plan.source, homeClass: plan.home_class || null, fan: !!D.fan
    };
  }

  return { accuracy: accuracy, parseLine: parseLine, parseStatus: parseStatus, parseEventFrame: parseEventFrame, crc8: crc8, fresh: fresh, applyRec: applyRec,
           clockOf: clockOf, dotFor: dotFor, GAUGE_STEPS: GAUGE_STEPS, tomorrow: tomorrow, runsOf: runsOf };
})();
if (typeof module !== 'undefined') module.exports = HG;
