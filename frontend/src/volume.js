/** Series I Appendix A, Note 1: zero is mute; other values are raw - 96 dB. */
export function volumeLabel(raw, offset = -96) {
  if (raw === 0) return 'Mute';
  const db = raw + offset;
  return `${db > 0 ? '+' : ''}${db} dB`;
}

/** Relative rotation avoids a volume jump on touch-down or the ±180° seam. */
export function rotateVolume(raw, previousAngle, angle, remainder = 0, maximum = 111) {
  const delta = ((angle - previousAngle + 540) % 360) - 180;
  const travel = remainder + delta;
  const steps = Math.trunc(travel / 4);
  const next = Math.max(0, Math.min(maximum, raw + steps));
  return { raw: next, remainder: next === raw + steps ? travel - steps * 4 : 0 };
}
