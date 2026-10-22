import { MapPinned } from "lucide-react";
import { formatMetricValue, METRIC_DEFS } from "../lib/metrics";
import { resolveRegionMetric } from "../lib/stats";
import MetricIcon from "./icons";
import SectionCard from "./Card";

const STATUS_META = {
  good: {
    chip: "bg-emerald-50 text-emerald-700",
    bar: "bg-emerald-500",
    label: "On track",
  },
  below: {
    chip: "bg-sky-50 text-sky-700",
    bar: "bg-sky-400",
    label: "Below national avg",
  },
  worse: {
    chip: "bg-amber-50 text-amber-700",
    bar: "bg-amber-400",
    label: "Above national avg",
  },
  critical: {
    chip: "bg-rose-50 text-rose-600",
    bar: "bg-rose-500",
    label: "Critical",
  },
  neutral: {
    chip: "bg-slate-100 text-slate-600",
    bar: "bg-slate-300",
    label: "No benchmark",
  },
};

function progressWidth(entry) {
  const v = entry.value;
  const unit = String(entry.unit ?? "");
  if (v >= 0 && v <= 100 && /%|percent/i.test(unit)) return v;
  if (v >= 0 && v <= 1 && /index|ratio/i.test(unit)) return v * 100;
  return Math.max(0, Math.min(100, v));
}

function MetricCard({ def, resolved }) {
  const entry = resolved;
  const statusMeta = STATUS_META[entry.status] ?? STATUS_META.neutral;
  const width = progressWidth(entry.entry);
  const national = entry.national;
  const diff = national?.value != null ? entry.entry.value - national.value : null;
  const diffGood = def.direction === "higher" ? diff >= 0 : diff <= 0;

  return (
    <article className="mb-4 flex break-inside-avoid flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className={`rounded-lg p-2 ${statusMeta.chip}`}>
            <MetricIcon name={def.icon} />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-slate-800">{def.label}</h3>
            <p className="text-[11px] text-slate-500">{entry.entry.indicator_name}</p>
          </div>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${statusMeta.chip}`}>
          {statusMeta.label}
        </span>
      </div>

      <p className="mt-3 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{entry.formatted}</p>

      <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${def.label}: ${entry.formatted}`}>
        <div
          className={`h-full rounded-full transition-all duration-700 ${statusMeta.bar}`}
          style={{ width: `${width}%` }}
        />
      </div>

      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <span className="text-slate-600">
          National avg: <span className="font-semibold text-slate-700">{entry.nationalFormatted}</span>
        </span>
        {diff != null ? (
          <span
            className={`font-semibold ${diffGood ? "text-emerald-600" : "text-rose-500"}`}
            title={`District minus national average (in ${entry.entry.unit || "units"})`}
          >
            {diff >= 0 ? "+" : "−"}
            {Math.abs(diff).toFixed(1)} vs avg
          </span>
        ) : (
          <span className="text-slate-500">
            {def.direction === "higher" ? "higher is better" : "lower is better"}
          </span>
        )}
      </div>
    </article>
  );
}

export default function DistrictFocus({ region, stats }) {
  if (!region) return null;
  const cardDefs = METRIC_DEFS.filter((def) => region.metricMap[def.key]);
  const others = region.metrics.filter((m) => m.defKey == null);
  const year = region.years.length ? region.years[region.years.length - 1] : null;

  return (
    <SectionCard
      ariaLabel="District focus"
      icon={MapPinned}
      tone="teal"
      eyebrow="District deep dive"
      title={region.district}
      subtitle={
        <>
          {region.province} · {region.areaType} · {cardDefs.length} key indicators
          {year ? ` · survey year ${year}` : ""}
        </>
      }
      actions={
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/15">
          {stats?.years?.length ? `Survey years ${stats.years.join(", ")}` : "Live EICV/FinScope data"}
        </span>
      }
    >
      {cardDefs.length === 0 && others.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">No indicator rows available for this district.</p>
      ) : (
        <>
          <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
            {cardDefs.map((def) => (
              <MetricCard key={def.key} def={def} resolved={resolveRegionMetric(region, def.key, stats)} />
            ))}
          </div>

          {others.length > 0 && (
            <details className="group mt-4 rounded-xl border border-slate-200 bg-slate-50/60 open:bg-slate-50">
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-xs font-semibold text-slate-600">
                <span>Other dataset indicators ({others.length})</span>
                <span className="text-slate-500">toggle</span>
              </summary>
              <ul className="divide-y divide-slate-100 px-4 pb-2 text-sm">
                {others.map((m, i) => (
                  <li key={`${m.indicator_code}-${i}`} className="flex items-center justify-between gap-4 py-2">
                    <span className="min-w-0 truncate text-slate-600">{m.indicator_name}</span>
                    <span className="font-mono text-sm font-semibold tabular-nums text-slate-800">
                      {formatMetricValue(m, { compact: true })}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </SectionCard>
  );
}
