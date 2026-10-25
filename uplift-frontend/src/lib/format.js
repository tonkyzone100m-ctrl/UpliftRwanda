/** Weighted mean over panel rows; rows without the weight column count once. */
export function weightedMean(rows, key, weightKey = "population_weight") {
  let wTotal = 0;
  let vTotal = 0;
  for (const row of rows) {
    const v = row[key];
    if (v == null) continue;
    const w = row[weightKey] || 1;
    wTotal += w;
    vTotal += v * w;
  }
  return wTotal > 0 ? vTotal / wTotal : null;
}

export const percent = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);
export const thousands = (v) => (v == null ? "—" : v.toLocaleString("en-US"));
