export function confidencePercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return null;
  }
  const percent = number <= 1 ? number * 100 : number;
  return Math.round(Math.max(0, Math.min(100, percent)));
}

export function formatConfidence(value, suffix = "%") {
  const percent = confidencePercent(value);
  return percent == null ? null : `${percent}${suffix}`;
}
