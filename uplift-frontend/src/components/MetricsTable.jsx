import { useMemo } from "react";
import { ArrowDownRight, ArrowUpRight, ChartBarBig, Minus, SearchX } from "lucide-react";
import { formatMetricValue, resolveMetricDef } from "../lib/metrics";
import { CategoryBadge, DistrictBadge } from "./Badges";
import MetricIcon from "./icons";

const TH_BASE =
  "whitespace-nowrap px-3.5 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-slate-500";
const TH_RIGHT = `${TH_BASE} text-right`;
const TD_BASE = "border-b border-slate-100 px-3.5 py-2.5 align-top";

function DeltaChip({ entry, def, nationalMean }) {
  if (!def || nationalMean == null) {
    return <span className="text-xs text-slate-300">—</span>;
  }
  const delta = entry.value - nationalMean;
  const improving = def.direction === "higher" ? delta >= 0 : delta <= 0;
  const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "0";
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums ring-1 ring-inset ${
        improving
          ? "bg-emerald-50 text-emerald-700 ring-emerald-600/15"
          : "bg-rose-50 text-rose-600 ring-rose-600/15"
      }`}
      title={`Deviation from the national mean (same unit as ${entry.unit || "indicator"})`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {sign}
      {Math.abs(delta).toFixed(1)}
    </span>
  );
}

function AreaBadge({ areaType }) {
  const urban = /urban/i.test(areaType ?? "");
  const rural = /rural/i.test(areaType ?? "");
  const tone = rural
    ? "bg-emerald-50 text-emerald-700 ring-emerald-600/15"
    : urban
      ? "bg-sky-50 text-sky-700 ring-sky-600/15"
      : "bg-slate-100 text-slate-500 ring-slate-500/15";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${tone}`}>
      {areaType ?? "—"}
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
    <section
      aria-label="Indicator data table"
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-900">
          <ChartBarBig className="h-4 w-4 text-slate-400" aria-hidden="true" />
          Indicator explorer
        </h2>
        <p className="text-[11px] font-medium text-slate-600">
          {enriched.length.toLocaleString()} row{enriched.length === 1 ? "" : "s"} · EICV7 / FinScope / CFSVA panel
        </p>
      </div>

      {enriched.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 p-12 text-center" role="status">
          <SearchX className="h-8 w-8 text-slate-300" aria-hidden="true" />
          <p className="text-sm font-semibold text-slate-600">
            {hasFilters ? "No indicators match your current filters" : "No data points to display"}
          </p>
          <p className="max-w-sm text-xs text-slate-400">
            {emptyHint ?? "The seeded dataset appears here once the API serves survey metrics."}
          </p>
        </div>
      ) : (
        <div className="max-h-[560px] overflow-auto" tabIndex={0}>
          <table className="w-full min-w-[880px] border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                {["District", "Indicator", "Category", "Value", "vs National", "Year", "Area"].map((h, i) => (
                  <th
                    key={h}
                    scope="col"
                    className={`sticky top-0 z-20 border-b border-slate-200 bg-slate-100/95 backdrop-blur ${
                      i >= 3 && i <= 4 ? TH_RIGHT : TH_BASE
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {enriched.map((row, index) => {
                const nationalMean = row.def ? stats?.perMetric?.[row.def.key]?.mean ?? null : null;
                const zebra = index % 2 === 0 ? "bg-white" : "bg-slate-50/70";
                return (
                  <tr key={row.rowId} className={`${zebra} transition-colors hover:bg-sky-50/70`}>
                    <td className={`${TD_BASE} min-w-[9rem]`}>
                      <DistrictBadge district={row.district} />
                      <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        {row.province}
                      </p>
                    </td>
                    <td className={`${TD_BASE} min-w-[14rem]`}>
                      <div className="flex items-start gap-2">
                        <MetricIcon name={row.defIcon} className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-700">{row.defLabel ?? row.indicator_name}</p>
                          <p className="text-[11px] font-medium text-slate-500">{row.indicator_code}</p>
                        </div>
                      </div>
                    </td>
                    <td className={`${TD_BASE} min-w-[10rem] max-w-[14rem]`}>
                      <CategoryBadge categoryId={row.categoryId} category={row.category} />
                    </td>
                    <td className={`${TD_BASE} whitespace-nowrap text-right font-mono text-sm font-bold tabular-nums text-slate-900`}>
                      {row.formatted}
                    </td>
                    <td className={`${TD_BASE} text-right`}>
                      <div className="flex justify-end">
                        <DeltaChip entry={row} def={row.def} nationalMean={nationalMean} />
                      </div>
                    </td>
                    <td className={`${TD_BASE} whitespace-nowrap text-[11px] font-medium tabular-nums text-slate-600`}>
                      {row.survey_year ?? "—"}
                    </td>
                    <td className={TD_BASE}>
                      <AreaBadge areaType={row.area_type} />
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
