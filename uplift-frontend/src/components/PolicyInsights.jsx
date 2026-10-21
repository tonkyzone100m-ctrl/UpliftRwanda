import { useCallback, useEffect, useState } from "react";
import { CircleAlert, CircleCheck, Info, Lightbulb, Sparkles, Target, Wifi, WifiOff } from "lucide-react";
import { fetchDistrictInsights, fetchNationalInsights } from "../lib/api";
import { buildPolicyInsights } from "../lib/policy";

const SEVERITY_META = {
  critical: { icon: CircleAlert, chip: "bg-rose-50 text-rose-600", border: "border-rose-200", label: "Act now" },
  attention: { icon: Target, chip: "bg-amber-50 text-amber-700", border: "border-amber-200", label: "Priority" },
  strength: { icon: CircleCheck, chip: "bg-emerald-50 text-emerald-700", border: "border-emerald-200", label: "Model practice" },
};

function InsightCard({ insight }) {
  const meta = SEVERITY_META[insight.severity];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <li className={`rounded-xl border ${meta.border} bg-white p-4 transition hover:shadow-md`}>
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 shrink-0 rounded-lg p-2 ${meta.chip}`}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${meta.chip}`}>
              {meta.label}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
              {insight.pillar}
            </span>
          </div>
          <h4 className="mt-2 text-sm font-bold text-gray-900">{insight.title}</h4>
          <p className="mt-1 text-xs leading-relaxed text-gray-600">{insight.description}</p>
          {(insight.data ?? []).length > 0 && (
            <ul className="mt-2 space-y-1">
              {insight.data.map((line) => (
                <li key={line} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-gray-500">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gray-300" aria-hidden="true" />
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
      className="rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-900 to-slate-800 p-5 text-slate-100 shadow-sm sm:p-6"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-sky-500/15 p-2.5 text-sky-300" aria-hidden="true">
            <Lightbulb className="h-5 w-5" />
          </span>
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold">
              NST2 Policy Insights
              <Sparkles className="h-4 w-4 text-yellow-300" aria-hidden="true" />
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Auto-generated from live indicators · Vision 2050 &amp; NST2 alignment
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
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
        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2" aria-hidden="true">
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
        <div className="mt-5 flex items-start gap-3 rounded-xl border border-slate-600/60 bg-slate-700/30 p-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-300" aria-hidden="true" />
          <p className="text-xs leading-relaxed text-slate-300">
            No policy rules matched for this scope yet. Once FinScope/EICV indicators for {scope} are
            present in the database, NST2 recommendations appear here automatically
            (rules: poverty &gt; 30%, vulnerability &gt; 30%, mobile money &lt; 75%, climate exposure &gt; 69%).
          </p>
        </div>
      ) : (
        <ul className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2">
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
