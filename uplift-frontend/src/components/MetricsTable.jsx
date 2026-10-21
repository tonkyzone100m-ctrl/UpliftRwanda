import { useMemo } from "react";
import { ArrowDownRight, ArrowUpRight, ChartBarBig, Minus, SearchX } from "lucide-react";
import { formatMetricValue, resolveMetricDef } from "../lib/metrics";
import MetricIcon from "./icons";

function DeltaChip({ entry, def, nationalMean }) {
  if (!def || nationalMean == null) {
    return <span className="text-xs text-gray-300">—</span>;
  }
  const delta = entry.value - nationalMean;
  const improving = def.direction === "higher" ? delta >= 0 : delta <= 0;
  const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "0";
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        improving ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"
      }`}
      title={`Deviation from the national mean (same unit as ${entry.unit || "indicator"})`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {sign}
      {Math.abs(delta).toFixed(1)}
    </span>
  );
}

export default function MetricsTable({ rows, stats, hasFilters, emptyHint }) {
  const enriched = useMemo(
    () =>
      rows.map((row) => {
        const def = resolveMetricDef(row);
        return {
          ...row,
          def,
          defIcon: def?.icon ?? null,
          defLabel: def?.label ?? null,
          direction: def?.direction ?? null,
          formatted: formatMetricValue(row, { compact: true }),
        };
      }),
    [rows],
  );

  return (
    <section aria-label="Indicator data table" className="rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-bold text-gray-900">
          <ChartBarBig className="h-4 w-4 text-gray-400" aria-hidden="true" />
          Indicator explorer
        </h2>
        <p className="text-xs text-gray-400">
          {enriched.length} row{enriched.length === 1 ? "" : "s"} · EICV / FinScope inspired seed data
        </p>
      </div>

      {enriched.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 p-12 text-center" role="status">
          <SearchX className="h-8 w-8 text-gray-300" aria-hidden="true" />
          <p className="text-sm font-semibold text-gray-600">
            {hasFilters ? "No indicators match your current filters" : "No data points to display"}
          </p>
          <p className="max-w-sm text-xs text-gray-400">
            {emptyHint ?? "The seeded dataset appears here once the API serves survey metrics."}
          </p>
        </div>
      ) : (
        <div className="max-h-[520px] overflow-auto rounded-b-2xl" tabIndex={0}>
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="sticky top-0 z-10 bg-gray-50/95 backdrop-blur">
              <tr>
                {["District", "Indicator", "Category", "Value", "vs National", "Year", "Area"].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {enriched.map((row) => {
                const nationalMean = row.def ? stats?.perMetric?.[row.def.key]?.mean ?? null : null;
                return (
                  <tr key={row.rowId} className="transition-colors hover:bg-gray-50/70">
                    <td className="px-4 py-3 align-top">
                      <p className="font-semibold text-gray-800">{row.district}</p>
                      <p className="mt-0.5 text-xs text-gray-400">{row.province}</p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex items-start gap-2">
                        <MetricIcon name={row.defIcon} className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                        <div className="min-w-0">
                          <p className="font-medium text-gray-700">{row.defLabel ?? row.indicator_name}</p>
                          <p className="text-xs text-gray-400">{row.indicator_code}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
                        {row.category ?? "Uncategorized"}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-top font-mono text-sm font-semibold text-gray-900">
                      {row.formatted}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <DeltaChip entry={row} def={row.def} nationalMean={nationalMean} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 align-top text-xs text-gray-500">
                      {row.survey_year ?? "—"}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          /urban/i.test(row.area_type ?? "")
                            ? "bg-sky-50 text-sky-700"
                            : /rural/i.test(row.area_type ?? "")
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {row.area_type ?? "—"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
