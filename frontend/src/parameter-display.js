/** Format converted receiver readings, leaving missing values visibly unknown. */
export function parameterLabel(reading) {
  if (!reading) return '—';
  if (reading.label) return reading.label;
  if (reading.value === null) return '—';
  if (reading.unit === 'dB') {
    return `${reading.value > 0 ? '+' : ''}${reading.value.toFixed(1)} dB`;
  }
  return `${reading.value}${reading.unit ? ` ${reading.unit}` : ''}`;
}
