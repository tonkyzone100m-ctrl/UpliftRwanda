import { entryMatches, formatMetricValue, METRIC_DEFS, metricStatus } from "./metrics";

const defLookup = new Map(METRIC_DEFS.map((d) => [d.key, d]));

/**
 * Groups flat metric rows into region objects.
 * Returns an array of { province, district, areaType, years, metrics, metricMap }
 * where each entry in `metrics` is tagged with the canonical metric def key.
 */
export function buildRegions(rows) {
  const byRegion = new Map();
  for (const row of rows) {
    if (row?.district == null || row?.value == null || Number.isNaN(Number(row.value))) continue;
    const key = `${row.province ?? "Unknown"}||${row.district}`;
    let region = byRegion.get(key);
    if (!region) {
      region = {
        province: row.province ?? "Unknown",
        district: row.district,
        areaType: row.area_type ?? "unknown",
        years: new Set(),
        metrics: [],
        metricMap: {},
      };
      byRegion.set(key, region);
    }
    const entry = {
      ...row,
      value: Number(row.value),
      defKey: METRIC_DEFS.find((def) => entryMatches(row, def))?.key ?? null,
    };
    region.years.add(row.survey_year);
    region.metrics.push(entry);
    if (entry.defKey && !region.metricMap[entry.defKey]) region.metricMap[entry.defKey] = entry;
  }
  const regions = [...byRegion.values()].map((r) => ({
    ...r,
    years: [...r.years].filter((y) => y != null).sort((a, b) => a - b),
  }));
  return regions.sort(
    (a, b) => a.province.localeCompare(b.province) || a.district.localeCompare(b.district),
  );
}

/** Aggregates canonical metrics across all districts and computes national stats. */
export function computeNationalStats(regions) {
  if (!regions?.length) return null;
  const stats = {
    regionCount: regions.length,
    entryCount: regions.reduce((acc, r) => acc + r.metrics.length, 0),
    categories: new Set(),
    provinces: new Set(),
    perMetric: {},
    years: new Set(),
  };

  for (const region of regions) {
    stats.provinces.add(region.province);
    for (const entry of region.metrics) {
      if (entry.category) stats.categories.add(entry.category);
      if (entry.survey_year != null) stats.years.add(entry.survey_year);
      if (!entry.defKey) continue;
      let bucket = stats.perMetric[entry.defKey];
      if (!bucket) {
        bucket = stats.perMetric[entry.defKey] = {
          values: [],
          mean: null,
          extreme: null,
        };
      }
      bucket.values.push(entry);
    }
  }

  for (const bucket of Object.values(stats.perMetric)) {
    bucket.mean = bucket.values.reduce((acc, e) => acc + e.value, 0) / bucket.values.length;
  }
  stats.years = [...stats.years].sort((a, b) => a - b);
  return stats;
}

/** The best/worst performing district for one metric, respecting its direction. */
export function extremeMetricEntry(stats, defKey, kind = "good") {
  const bucket = stats?.perMetric?.[defKey];
  const def = defLookup.get(defKey);
  if (!bucket || !def) return null;
  const sorted = [...bucket.values].sort((a, b) =>
    def.direction === "higher" ? a.value - b.value : b.value - a.value,
  );
  const entry = kind === "good" ? sorted[sorted.length - 1] : sorted[0];
  return {
    entry,
    value: entry.value,
    formatted: formatMetricValue(entry, { compact: true }),
    descent: kind === "good" ? "best" : "worst",
  };
}

export function nationalEntries(stats, defKey) {
  const bucket = stats?.perMetric?.[defKey];
  if (!bucket) return null;
  return {
    value: bucket.mean,
    unit: bucket.values[0]?.unit ?? "",
    sample: bucket.values.length,
  };
}

/** Resolves one canonical metric for a region with national context attached. */
export function resolveRegionMetric(region, defKey, stats) {
  const entry = region?.metricMap?.[defKey];
  if (!entry) return null;
  const national = nationalEntries(stats, defKey);
  return {
    defKey,
    entry,
    national,
    formatted: formatMetricValue(entry, { compact: true }),
    nationalFormatted: national ? formatMetricValue(national, { compact: true }) : "—",
    status: metricStatus(defLookup.get(defKey), entry, national ? { metrics: { [defKey]: national } } : null),
  };
}
