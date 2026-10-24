import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rotateVolume, volumeLabel } from './volume.js';

test('Note 1 labels mute and the full dB range', () => {
  assert.equal(volumeLabel(0), 'Mute');
  assert.equal(volumeLabel(1), '-95 dB');
  assert.equal(volumeLabel(96), '0 dB');
  assert.equal(volumeLabel(111), '+15 dB');
});

test('rotation crosses the angle seam in either direction without a jump', () => {
  assert.equal(rotateVolume(40, 178, -178).raw, 41);
  assert.equal(rotateVolume(40, -178, 178).raw, 39);
  assert.equal(rotateVolume(40, 10, 10).raw, 40);
});

test('small motions accumulate into 1 dB steps and limits clamp', () => {
  let result = rotateVolume(40, 0, 2);
  assert.equal(result.raw, 40);
  result = rotateVolume(result.raw, 2, 4, result.remainder);
  assert.equal(result.raw, 41);
  assert.equal(rotateVolume(110, 0, 40).raw, 111);
  assert.equal(rotateVolume(1, 0, -40).raw, 0);
  assert.equal(rotateVolume(111, 0, 40).remainder, 0);
});
