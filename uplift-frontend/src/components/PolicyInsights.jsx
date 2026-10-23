import { useCallback, useEffect, useState } from "react";
import { CircleAlert, CircleCheck, Info, Lightbulb, Sparkles, Target, Wifi, WifiOff } from "lucide-react";
import { fetchDistrictInsights, fetchNationalInsights } from "../lib/api";
import { buildPolicyInsights } from "../lib/policy";

const SEVERITY_META = {
  critical: { icon: CircleAlert, chip: "bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-500/30", border: "border-rose-500/40", label: "Act now" },
  attention: { icon: Target, chip: "bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-500/30", border: "border-amber-500/40", label: "Priority" },
  strength: { icon: CircleCheck, chip: "bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30", border: "border-emerald-500/40", label: "Model practice" },
};

function InsightCard({ insight }) {
  const meta = SEVERITY_META[insight.severity];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <li
      className={`mb-3 break-inside-avoid rounded-xl border ${meta.border} bg-slate-900/80 p-4 transition hover:border-slate-500`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 shrink-0 rounded-lg p-2 ${meta.chip}`}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${meta.chip}`}>
              {meta.label}
            </span>
            <span className="rounded-full bg-slate-700/60 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
              {insight.pillar}
            </span>
          </div>
          <h4 className="mt-2 text-sm font-bold text-slate-100">{insight.title}</h4>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">{insight.description}</p>
          {(insight.data ?? []).length > 0 && (
            <ul className="mt-2 space-y-1">
              {insight.data.map((line) => (
                <li key={line} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-slate-400">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-500" aria-hidden="true" />
                  {line}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </li>
  );
}

export default function PolicyInsights({ district = "", fallbackRegion = null, fallbackStats = null }) {
  const [state, setState] = useState({ status: "loading", insights: [], source: "engine" });

  const run = useCallback(async (signal) => {
    setState({ status: "loading", insights: [], source: "engine" });
    const fetcher = district ? fetchDistrictInsights(district, { signal }) : fetchNationalInsights({ signal });
    try {
      const payload = await fetcher;
      setState({ status: "ready", insights: payload.insights ?? [], source: "engine" });
    } catch (error) {
      if (error?.name === "AbortError") return;
      const insights = fallbackRegion ? buildPolicyInsights(fallbackRegion, fallbackStats) : [];
      setState({ status: "fallback", insights, source: "local" });
    }
  }, [district, fallbackRegion, fallbackStats]);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async policy-engine fetch
    run(controller.signal);
    return () => controller.abort();
  }, [run]);

  const { status, insights, source } = state;
  const scope = district || "National Average";
  const criticalCount = insights.filter((i) => i.severity === "critical").length;

  return (
    <section
      aria-label="NST2 policy insights"
      className="rounded-2xl border border-slate-800 bg-slate-900 p-5 text-slate-100 shadow-sm"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="shrink-0 rounded-lg bg-sky-500/15 p-2.5 text-sky-300" aria-hidden="true">
            <Lightbulb className="h-5 w-5" />
          </span>
          <div>
            <p className="mb-0.5 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-300">
              NISR Policy Engine
            </p>
            <h2 className="flex items-center gap-1.5 text-sm font-bold text-white">
              NST2 Policy Insights
              <Sparkles className="h-3.5 w-3.5 text-yellow-300" aria-hidden="true" />
            </h2>
            <p className="mt-0.5 text-xs text-slate-300">
              Auto-generated from live indicators · Vision 2050 &amp; NST2 alignment
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-600/60 bg-slate-700/40 px-2.5 py-1 text-[10px] font-semibold text-slate-300"
            title={source === "engine" ? "Running on the FastAPI policy engine (FinScope 2024 thresholds)" : "Backend unreachable — using the built-in mirror of the engine"}
          >
            {source === "engine" ? <Wifi className="h-3 w-3 text-emerald-300" /> : <WifiOff className="h-3 w-3 text-amber-300" />}
            {source === "engine" ? "NISR engine" : "Offline mirror"}
          </span>
          {insights.length > 0 && (
            <span className="rounded-full border border-slate-600 bg-slate-700/50 px-3 py-1 text-[11px] font-semibold text-slate-200">
              {scope}
              {criticalCount > 0 && <span className="ml-2 text-rose-300">{criticalCount} critical</span>}
            </span>
          )}
        </div>
      </header>

      {status === "loading" ? (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2" aria-hidden="true">
          {[0, 1].map((i) => (
            <div key={i} className="animate-pulse rounded-xl border border-slate-600/40 bg-slate-700/30 p-4">
              <div className="h-3 w-24 rounded bg-slate-600/60" />
              <div className="mt-3 h-3 w-40 rounded bg-slate-600/40" />
              <div className="mt-3 h-2 w-full rounded bg-slate-600/30" />
              <div className="mt-2 h-2 w-3/4 rounded bg-slate-600/30" />
            </div>
          ))}
        </div>
      ) : insights.length === 0 ? (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-slate-700 bg-slate-800/60 p-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-300" aria-hidden="true" />
          <p className="text-xs leading-relaxed text-slate-300">
            No policy rules matched yet. Once indicators for {scope} exist in the database, NST2
            recommendations appear here automatically.
          </p>
        </div>
      ) : (
        <ul className="mt-4 columns-1 gap-3 md:columns-2">
          {insights.map((i) => (
            <InsightCard key={i.id} insight={i} />
          ))}
        </ul>
      )}

      {status === "fallback" && insights.length === 0 && (
        <p className="mt-4 text-[11px] text-amber-300" role="status">
          The policy engine service is unreachable — start the backend (uvicorn main:app) or refresh.
        </p>
      )}
    </section>
  );
}
