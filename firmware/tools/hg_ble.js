// Heat Guardian BLE frames for the Chrome dashboard (and node tests). Layout: guardian/c/hg_frames.h (frozen).
// CRC-8/SMBUS: poly 0x07, init 0, no reflection. All little-endian.
(function (root) {
  const UUID = (x) => `0c76${x}-038b-46d5-8532-954dd1c5e01d`;
  const HG = { SVC: UUID('0000'), STATUS: UUID('0001'), CMD: UUID('0002'), INFO: UUID('0003') };
  function crc8(bytes, n) { let c = 0; for (let i = 0; i < n; i++) { c ^= bytes[i]; for (let k = 0; k < 8; k++) c = (c & 0x80) ? ((c << 1) ^ 0x07) & 0xFF : (c << 1) & 0xFF; } return c; }
  const STATE = ['OK', 'DRINK', 'COOL', 'DANGER', 'IMOK', 'BATTERY', 'CHECK', 'HELP'];
  function decodeStatus(b) {   // b: Uint8Array(20) -> object with the same keys as guardian/py status_unpack()
    if (b.length !== 20 || crc8(b, 19) !== b[19]) throw new Error('bad STATUS crc');
    const u16 = (o) => b[o] | (b[o + 1] << 8), i16 = (o) => { const v = u16(o); return v >= 0x8000 ? v - 0x10000 : v; };
    const t = (o) => (i16(o) === -32768 ? null : i16(o) / 100);
    const fam = !!(b[0] & 0x10);
    const d = { version: b[0] & 0x0F, family_pending: fam, not_worn: !!(b[0] & 0x20), state_code: b[1] & 7, contact_ok: !!(b[1] & 8),
      time_synced: !!(b[1] & 16), charging: !!(b[1] & 32), home: !!(b[1] & 64), ppg_valid: !!(b[1] & 128),
      core_c: u16(2) / 100, half_range_c: b[4] / 100, hr_bpm: b[5], hr_q: b[6], t1_c: t(7), t2_c: t(9), tair_c: t(11),
      rh_pct: b[13] === 255 ? null : b[13], battery_pct: b[14], minute_counter: u16(17) };
    if (fam) d.alarm_id16 = u16(15); else { d.routine_score = b[15]; d.activity = b[16]; }
    d.state = STATE[d.state_code];
    return d;
  }
  function decodeInfo(b) {
    if (b.length !== 20 || crc8(b, 19) !== b[19]) throw new Error('bad INFO crc');
    const u16 = (o) => b[o] | (b[o + 1] << 8);
    return { fw_version: u16(1), nn_crc: ((b[3] | (b[4] << 8) | (b[5] << 16)) + b[6] * 16777216) >>> 0, boot_count: u16(7),
             reset_reason: b[9], twin_saves: u16(10), hg2_tag: String.fromCharCode(...b.slice(12, 19)).replace(/\0+$/, '') };
  }
  function seal(arr) { const b = Uint8Array.from(arr); const o = new Uint8Array(b.length + 1); o.set(b); o[b.length] = crc8(b, b.length); return o; }
  function cmdTime(unixS, tzQ) { const b = [0x10, unixS & 255, (unixS >>> 8) & 255, (unixS >>> 16) & 255, (unixS >>> 24) & 255, tzQ & 255]; return seal(b); }
  function cmdFamilyAck(type, alarmId) { return seal([0x12, type, alarmId & 255, (alarmId >>> 8) & 255, (alarmId >>> 16) & 255, (alarmId >>> 24) & 255]); }
  function cmdDebug(n) { return seal([0x1F, n & 255]); }
  function fromHex(h) { const o = new Uint8Array(h.length / 2); for (let i = 0; i < o.length; i++) o[i] = parseInt(h.substr(2 * i, 2), 16); return o; }
  function toHex(b) { return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join(''); }
  const api = { HG, crc8, decodeStatus, decodeInfo, cmdTime, cmdFamilyAck, cmdDebug, fromHex, toHex, STATE };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.HGBLE = api;
})(typeof self !== 'undefined' ? self : this);
