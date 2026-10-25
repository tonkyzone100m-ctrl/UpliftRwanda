import { useCallback, useEffect, useRef, useState } from "react";
import { FlaskConical, Info, Loader2, SlidersHorizontal } from "lucide-react";
import { fetchDistrictList, runSimulation } from "../lib/api";
import ScenarioChart from "./ScenarioChart";
import SectionCard from "./Card";

const LEVERS = [
  { key: "mobile_money", label: "Mobile money adoption", hint: "FinScope 2024 national: 77%", max: 15 },
  { key: "formal_credit", label: "Formal credit access", hint: "FinScope 2024 national: 24%", max: 15 },
  { key: "formal_savings", label: "Formal savings uptake", hint: "FinScope 2024 national: 59%", max: 15 },
  { key: "social_protection", label: "Social protection reach", hint: "EICV7 national: 61.3%", max: 15 },
];

const INITIAL_DELTAS = { mobile_money: 5, formal_credit: 3, formal_savings: 0, social_protection: 0 };

export default function ScenarioLab() {
  const [deltas, setDeltas] = useState(INITIAL_DELTAS);
  const [horizon, setHorizon] = useState(2);
  const [district, setDistrict] = useState("");
  const [scope, setScope] = useState("national");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [labDistricts, setLabDistricts] = useState([]);
  const debounce = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchDistrictList({ signal: controller.signal })
      .then((list) => setLabDistricts(list))
      .catch(() => setLabDistricts([])); // lab still runs on national scope
    return () => controller.abort();
  }, []);

  const run = useCallback(async (signal) => {
    setBusy(true);
    setError(null);
    try {
      const payload = await runSimulation({
        driver_deltas: deltas,
        horizon_years: horizon,
        district: scope === "district" ? district : null,
      }, { signal });
      setResult(payload);
    } catch (err) {
      if (err?.name === "AbortError") return;
      setError(err?.message ?? "Simulation failed");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }, [deltas, horizon, scope, district]);

  useEffect(() => {
    const controller = new AbortController();
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => run(controller.signal), 450);
    return () => {
      clearTimeout(debounce.current);
      controller.abort();
    };
  }, [run]);

  return (
    <SectionCard
      ariaLabel="Predictive scenario lab"
      icon={FlaskConical}
      tone="emerald"
      title="Policy Scenario Lab"
      subtitle="Ridge-blended elasticity model trained on the embedded FinScope 2024 / EICV7 district panel"
      actions={
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
          <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" /> Horizon
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs shadow-sm transition focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15"
          >
            {[1, 2, 3, 4, 5].map((h) => (
              <option key={h} value={h}>{h} year{h > 1 ? "s" : ""}</option>
            ))}
          </select>
        </label>
      }
    >
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(260px,340px)_1fr]">
        {/* levers */}
        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-slate-600">
            <input
              type="radio"
              name="sim-scope"
              checked={scope === "national"}
              onChange={() => setScope("national")}
              className="h-4 w-4 accent-emerald-600"
            />
            National · weighted mean
          </label>
          <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-slate-600">
            <input
              type="radio"
              name="sim-scope"
              checked={scope === "district"}
              onChange={() => setScope("district")}
              className="h-4 w-4 accent-emerald-600"
            />
            Target district
            <select
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              disabled={scope !== "district"}
              className="ml-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium normal-case text-slate-700 shadow-sm transition focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15 disabled:bg-slate-100"
            >
              <option value="">Choose…</option>
              {(labDistricts || []).map((d) => (
                <option key={d.district} value={d.district}>{d.district}</option>
              ))}
            </select>
          </label>

          <hr className="border-slate-200" />

          {LEVERS.map((lever) => {
            const v = deltas[lever.key] ?? 0;
            return (
              <div key={lever.key}>
                <div className="flex items-baseline justify-between gap-2">
                  <label htmlFor={`lever-${lever.key}`} className="text-xs font-semibold text-slate-700">
                    {lever.label}
                  </label>
                  <span className="font-mono text-[11px] text-slate-600">
                    {v > 0 ? "+" : ""}{v.toFixed(1)} pp
                  </span>
                </div>
                <input
                  id={`lever-${lever.key}`}
                  type="range"
                  min={-5}
                  max={lever.max}
                  step={0.5}
                  value={v}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    setDeltas((d) => ({ ...d, [lever.key]: next }));
                  }}
                  className="mt-1 w-full accent-emerald-600"
                />
                <p className="mt-0.5 text-[10px] text-slate-500">{lever.hint}</p>
              </div>
            );
          })}
          <button
            type="button"
            onClick={() => setDeltas({ ...INITIAL_DELTAS })}
            className="w-full rounded-lg border border-slate-300 bg-slate-50 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:bg-slate-100"
          >
            Reset levers
          </button>
        </div>

        {/* results */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          {busy && !result && (
            <div className="flex items-center gap-2 py-10 text-xs text-slate-500" role="status">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Running simulation…
            </div>
          )}
          {error && (
            <div className="mb-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700" role="alert">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" /> {error}
            </div>
          )}
          {result && (
            <>
              {scope === "district" && district && result.district ? (
                <ScenarioChart outcomes={result.district} uncertainty={result.uncertainty_bands ?? {}} />
              ) : (
                <ScenarioChart outcomes={result.national} uncertainty={result.uncertainty_bands ?? {}} />
              )}
              {(result.warnings ?? []).length > 0 && (
                <p className="mt-2 text-[11px] text-amber-600" role="status">{result.warnings[0]}</p>
              )}
              <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/80 p-3" open={false}>
                <summary className="cursor-pointer text-[11px] font-bold text-slate-600">
                  Model card · coefficients · RMSE · methodology
                </summary>
                <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
                  Outcome across 30 district coordinates: ridge-blended OLS (pp outcomes against four
                  policy-lever drivers), FinScope/EICV7-aligned priors, ramp applied as g/H of the horizon
                  and 0–100 plausibility clamped. Uncertainty bands: ±1.96·RMSE/√30 from the regression fit.
                </p>
                <pre className="mt-2 overflow-x-auto font-mono text-[10px] leading-4 text-slate-600">
                  {JSON.stringify(result.model, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>
      </div>
    </SectionCard>
  );
}
