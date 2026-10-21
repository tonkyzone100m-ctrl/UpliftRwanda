import { useMemo } from "react";
import { Sprout, Utensils, Wheat, HeartPulse, PackageX } from "lucide-react";
import { formatMetricValue, METRIC_DEFS } from "../lib/metrics";

const CFSVA_TILES = [
  { key: "fiesModerateSevere", label: "Food Insecurity (moderate+severe)", icon: PackageX },
  { key: "foodConsumptionScore", label: "Food Consumption Score", icon: Wheat },
  { key: "hdds", label: "Dietary Diversity (HDDS 0–12)", icon: Utensils },
  { key: "stunting", label: "Child Stunting (% under-5)", icon: HeartPulse },
];

/**
 * Modular CFSVA 2024 strip. Renders NOTHING until the dedicated Food Security
 * layer is seeded — the existing FinScope/EICV dashboard stays untouched.
 */
export default function CFSVAPanel({ rows = [], stats = null }) {
  const tiles = useMemo(
    () =>
      CFSVA_TILES.map((tile) => {
        const def = METRIC_DEFS.find((d) => d.key === tile.key);
        const bucket = stats?.perMetric?.[tile.key];
        const mean = bucket?.mean ?? null;
        const status =
          mean == null || !def
            ? null
            : def.direction === "higher"
              ? mean < def.criticalLow
                ? "needs attention"
                : "on national track"
              : mean > def.criticalHigh
                ? "needs attention"
                : "on national track";
        return { ...tile, mean, status, target: def?.target ?? "" };
      }),
    [stats],
  );

  const ranked = useMemo(() => {
    if (!rows.length) return [];
    const byDistrict = new Map();
    for (const row of rows) {
      const d = byDistrict.get(row.district) ?? {};
      d[row.indicator_code] = row.value;
      byDistrict.set(row.district, d);
    }
    return [...byDistrict.entries()]
      .map(([district, m]) => {
        const fies = m.fies_moderate_severe_pct ?? 0;
        const stunting = m.stunting_pct ?? 0;
        const fcs = m.food_consumption_score ?? 0;
        const hdds = m.hdds ?? 6;
        return {
          district,
          risk: fies + stunting + 0.2 * (100 - (fcs / 80) * 100) + 0.2 * (100 - (hdds / 12) * 100),
          fi: m.fies_moderate_severe_pct ?? null,
          stunting: m.stunting_pct ?? null,
          fcs: m.food_consumption_score ?? null,
        };
      })
      .sort((a, b) => b.risk - a.risk)
      .slice(0, 6);
  }, [rows]);

  if (!rows.length) return null;

  return (
    <section
      aria-label="CFSVA 2024 food security intelligence"
      className="rounded-2xl border border-emerald-100 bg-gradient-to-b from-white to-emerald-50/60 p-5 shadow-sm sm:p-6"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-emerald-100 p-2.5 text-emerald-700" aria-hidden="true">
            <Sprout className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Food Security &amp; Nutrition · CFSVA 2024</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Dedicated <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[10px]">district_food_security</code>
              layer — separate from the FinScope/EICV7 datasets, same district keys
            </p>
          </div>
        </div>
        <span className="rounded-full border border-emerald-200 bg-emerald-100/70 px-3 py-1 text-[11px] font-semibold text-emerald-700">
          {rows.length / 8} districts · 8 indicators
        </span>
      </header>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((tile) => {
          const Icon = tile.icon;
          return (
            <article key={tile.key} className="rounded-xl border border-emerald-100 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{tile.label}</h3>
              </div>
              <p className="mt-2 text-2xl font-extrabold text-slate-900">
                {tile.mean != null ? formatMetricValue({ value: tile.mean, unit: "%" }, { compact: true }) : "—"}
              </p>
              {tile.status && (
                <p className={`mt-1 text-[11px] font-semibold ${tile.status === "needs attention" ? "text-amber-600" : "text-emerald-600"}`}>
                  {tile.status} · {tile.target}
                </p>
              )}
            </article>
          );
        })}
      </div>

      {ranked.length > 0 && (
        <div className="mt-5 overflow-x-auto rounded-xl border border-emerald-100 bg-white">
          <table className="w-full min-w-[540px] text-left text-xs">
            <caption className="sr-only">Top food-vulnerability districts combining CFSVA indicators</caption>
            <thead className="bg-emerald-50 text-emerald-800">
              <tr>
                <th className="px-3 py-2 font-bold">Priority district</th>
                <th className="px-3 py-2 font-bold">Food insecurity</th>
                <th className="px-3 py-2 font-bold">Stunting</th>
                <th className="px-3 py-2 font-bold">Food Consumption Score</th>
                <th className="px-3 py-2 font-bold">Composite risk</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((d, i) => (
                <tr key={d.district} className={i % 2 ? "bg-emerald-50/40" : "bg-white"}>
                  <td className="px-3 py-2 font-semibold text-slate-800">{d.district}</td>
                  <td className="px-3 py-2 text-slate-600">{d.fi != null ? d.fi.toFixed(1) + "%" : "—"}</td>
                  <td className="px-3 py-2 text-slate-600">{d.stunting != null ? d.stunting.toFixed(1) + "%" : "—"}</td>
                  <td className="px-3 py-2 text-slate-600">{d.fcs != null ? d.fcs.toFixed(1) : "—"}</td>
                  <td className="px-3 py-2">
                    <span className="inline-block rounded-full bg-rose-50 px-2 py-0.5 font-semibold text-rose-600">
                      {d.risk.toFixed(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-[11px] text-slate-500">
        Composite risk = FI% + stunting% + 0.2·(100 − FCS%/80) + 0.2·(100 − HDDS%/12) · weights align to
        the NISR/IPC Priority Matrix precedent — tune before final publication.
      </p>
    </section>
  );
}
