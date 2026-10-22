import {
  AlertTriangle,
  Frown,
  Landmark,
  Trophy,
  Wallet,
} from "lucide-react";
import { extremeMetricEntry } from "../lib/stats";

function Card({ accent, icon: Icon, label, value, sub, loading }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`absolute inset-x-0 top-0 h-1 ${accent.bar}`} aria-hidden="true" />
      <div className="flex items-start justify-between gap-3">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">{label}</p>
        <span className={`rounded-lg p-2 ${accent.chip}`}>
          <Icon className={`h-4 w-4 ${accent.iconText}`} aria-hidden="true" />
        </span>
      </div>
      {loading ? (
        <div className="mt-3 space-y-2" aria-hidden="true">
          <div className="h-7 w-28 animate-pulse-soft rounded bg-slate-200" />
          <div className="h-3.5 w-40 animate-pulse-soft rounded bg-slate-100" />
        </div>
      ) : (
        <>
          <p className="mt-2 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{value}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-600">{sub}</p>
        </>
      )}
    </div>
  );
}

export default function SummaryCards({ stats, loading }) {
  const poverty = stats?.perMetric?.povertyRate;
  const inclusion = stats?.perMetric?.financialInclusion;
  const social = stats?.perMetric?.socialProtection;
  const bestInclusion = extremeMetricEntry(stats, "financialInclusion", "good");
  const worstPoverty = extremeMetricEntry(stats, "povertyRate", "bad");

  const cards = [
    {
      key: "inclusion",
      icon: Wallet,
      accent: { bar: "bg-sky-500", chip: "bg-sky-50", iconText: "text-sky-600" },
      label: "Avg · Financial Inclusion",
      value: loading ? "…" : inclusion ? `${inclusion.mean.toFixed(1)}%` : "—",
      sub: `National mean across districts · NST2 benchmark ≥ 80%`,
    },
    {
      key: "poverty",
      icon: Frown,
      accent: { bar: "bg-amber-400", chip: "bg-amber-50", iconText: "text-amber-600" },
      label: "Avg · Poverty Headcount",
      value: loading ? "…" : poverty ? `${poverty.mean.toFixed(1)}%` : "—",
      sub: `National mean across districts · guardrail < 30%`,
    },
    {
      key: "social",
      icon: Landmark,
      accent: { bar: "bg-violet-500", chip: "bg-violet-50", iconText: "text-violet-600" },
      label: "Avg · Social Protection",
      value: loading ? "…" : social ? `${social.mean.toFixed(1)}%` : "—",
      sub: `National mean across districts · target ≥ 60%`,
    },
    {
      key: "best-inclusion",
      icon: Trophy,
      accent: { bar: "bg-emerald-500", chip: "bg-emerald-50", iconText: "text-emerald-600" },
      label: "Top Inclusion District",
      value: loading ? "…" : bestInclusion?.formatted ?? "—",
      sub: bestInclusion ? `${bestInclusion.entry.district} · ${bestInclusion.entry.province}` : "No inclusion data yet",
    },
    {
      key: "worst-poverty",
      icon: AlertTriangle,
      accent: { bar: "bg-rose-500", chip: "bg-rose-50", iconText: "text-rose-600" },
      label: "Highest Poverty",
      value: loading ? "…" : worstPoverty?.formatted ?? "—",
      sub: worstPoverty ? `${worstPoverty.entry.district} · ${worstPoverty.entry.province}` : "No poverty data yet",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {cards.map((c) => (
        <Card key={c.key} {...c} loading={loading} />
      ))}
    </div>
  );
}
