import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parameterLabel } from './parameter-display.js';

test('speaker trims use signed dB and preserve half-decibel steps', () => {
  for (const [value, expected] of [[-12, '-12.0 dB'], [0, '0.0 dB'], [0.5, '+0.5 dB'], [12, '+12.0 dB']]) {
    assert.equal(parameterLabel({ value, unit: 'dB' }), expected);
  }
});

test('mode names, delay units, and missing replies are distinct', () => {
  assert.equal(parameterLabel({ value: 5, label: 'Stereo' }), 'Stereo');
  assert.equal(parameterLabel({ value: 0, unit: 'ms' }), '0 ms');
  assert.equal(parameterLabel({ value: 15, unit: 'ms' }), '15 ms');
  assert.equal(parameterLabel(null), '—');
  assert.equal(parameterLabel(undefined), '—');
  assert.equal(parameterLabel({ value: null }), '—');
});
