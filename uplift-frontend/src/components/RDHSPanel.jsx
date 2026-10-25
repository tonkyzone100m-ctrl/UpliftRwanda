import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Wallet, Smartphone, Landmark, Zap } from "lucide-react";
import SectionCard from "./Card";
import { weightedMean } from "../lib/format";

const PROVINCE_COLORS = {
  "City of Kigali": "#0ea5e9",
  "Eastern Province": "#f43f5e",
  "Northern Province": "#8b5cf6",
  "Southern Province": "#16a34a",
  "Western Province": "#f59e0b",
};

const CHART_INDICATORS = [
  { key: "bank_account_pct", label: "Bank account", unit: "%" },
  { key: "mobile_fintech_pct", label: "Mobile money / fintech use", unit: "%" },
  { key: "insurance_pct", label: "Health insurance coverage", unit: "%" },
  { key: "electricity_pct", label: "Electricity access", unit: "%" },
  { key: "improved_water_pct", label: "Improved water source", unit: "%" },
  { key: "improved_sanitation_pct", label: "Improved sanitation", unit: "%" },
  { key: "mobile_phone_pct", label: "Mobile phone ownership", unit: "%" },
  { key: "urban_pct", label: "Urban households", unit: "%" },
  { key: "wealth_p40_pct", label: "Wealth share of bottom 40%", unit: "%" },
  { key: "imr_per_1000", label: "Infant mortality (IMR)", unit: "per 1,000" },
  { key: "u5mr_per_1000", label: "Under-5 mortality (U5MR)", unit: "per 1,000" },
  { key: "stunting_pct", label: "Child stunting", unit: "%" },
  { key: "wasting_pct", label: "Child wasting", unit: "%" },
];

const KPI_TILES = [
  { key: "bank_account_pct", label: "Bank Account", icon: Wallet, unit: "%" },
  { key: "mobile_fintech_pct", label: "Mobile Money / Fintech", icon: Smartphone, unit: "%" },
  { key: "insurance_pct", label: "Health Insurance", icon: Landmark, unit: "%" },
  { key: "electricity_pct", label: "Electricity", icon: Zap, unit: "%" },
];

const QUINTILES = [
  { key: "wealth_q1", label: "Poorest", fill: "#dc2626" },
  { key: "wealth_q2", label: "Poorer", fill: "#f59e0b" },
  { key: "wealth_q3", label: "Middle", fill: "#eab308" },
  { key: "wealth_q4", label: "Richer", fill: "#38bdf8" },
  { key: "wealth_q5", label: "Richest", fill: "#047857" },
];


function pearson(pairs) {
  if (pairs.length < 3) return null;
  const mx = pairs.reduce((s, p) => s + p[0], 0) / pairs.length;
  const my = pairs.reduce((s, p) => s + p[1], 0) / pairs.length;
  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (const [x, y] of pairs) {
    sxy += (x - mx) * (y - my);
    sxx += (x - mx) ** 2;
    syy += (y - my) ** 2;
  }
  return sxx > 0 && syy > 0 ? sxy / Math.sqrt(sxx * syy) : null;
}

const pct = (v, unit = "%") => (v == null ? "—" : `${v.toFixed(1)}${unit === "%" ? "%" : " ‰"}`);

/**
 * RDHS 2025 living standards & poverty dynamics — third data layer, additive
 * only. Renders an actionable empty state until the layer is seeded
 * (python3 seed_rdhs.py); the FinScope/EICV7 + CFSVA dashboards never block.
 */
export default function RDHSPanel({
  rows = [],
  selectedDistrict = "",
  onSelectDistrict = () => {},
}) {
  const [province, setProvince] = useState("");
  const [indicator, setIndicator] = useState("bank_account_pct");

  const provinces = useMemo(
    () => [...new Set(rows.map((r) => r.province))].sort(),
    [rows],
  );

  const scoped = useMemo(
    () => (province ? rows.filter((r) => r.province === province) : rows),
    [rows, province],
  );

  const scopedDistrict = useMemo(
    () => scoped.find((r) => r.district === selectedDistrict) ?? null,
    [scoped, selectedDistrict],
  );

  const indDef = CHART_INDICATORS.find((i) => i.key === indicator) ?? CHART_INDICATORS[0];

  const barData = useMemo(
    () =>
      scoped
        .filter((r) => r[indicator] != null)
        .map((r) => ({ district: r.district, value: r[indicator], province: r.province }))
        .sort((a, b) => b.value - a.value),
    [scoped, indicator],
  );

  const wealthData = useMemo(() => {
    if (!scoped.length) return [];
    const national = QUINTILES.map((q) => weightedMean(scoped, q.key, "households"));
    const scopeRow = {
      name: scopedDistrict ? "In-scope mean" : "All in scope",
      ...Object.fromEntries(QUINTILES.map((q, i) => [q.label, national[i]])),
    };
    if (!scopedDistrict) return [scopeRow];
    return [
      scopeRow,
      {
        name: scopedDistrict.district,
        ...Object.fromEntries(QUINTILES.map((q) => [q.label, scopedDistrict[q.key]])),
      },
    ];
  }, [scoped, scopedDistrict]);

  const scatterData = useMemo(
    () =>
      scoped
        .filter((r) => r.bank_account_pct != null && r.wealth_p40_pct != null)
        .map((r) => ({
          x: r.bank_account_pct,
          y: r.wealth_p40_pct,
          z: r.households ?? 1,
          district: r.district,
          province: r.province,
        })),
    [scoped],
  );

  const corr = useMemo(
    () => pearson(scatterData.map((d) => [d.x, d.y])),
    [scatterData],
  );

  const outcomes = useMemo(
    () =>
      scoped
        .filter((r) => r.u5mr_per_1000 != null)
        .sort((a, b) => b.u5mr_per_1000 - a.u5mr_per_1000),
    [scoped],
  );

  if (!rows.length) {
    return (
      <SectionCard
        ariaLabel="RDHS 2025 living standards"
        icon={Activity}
        tone="violet"
        title="Living Standards & Poverty Dynamics · RDHS 2025"
        subtitle="Third NISR data layer — household (RWHR91FL) + birth (RWBR91FL) recodes"
      >
        <div className="rounded-xl border border-dashed border-violet-300 bg-violet-50/50 p-8 text-center">
          <p className="text-sm font-semibold text-slate-800">RDHS 2025 layer not seeded yet</p>
          <p className="mt-1 text-xs text-slate-600">
            Generate the district panel from the microdata, then seed the layer:
          </p>
          <pre className="mx-auto mt-3 max-w-md rounded-lg bg-slate-900 px-4 py-3 text-left text-[11px] leading-relaxed text-emerald-300">
            python3 preprocess_rdhs.py{"\n"}python3 seed_rdhs.py --url $DATABASE_URL
          </pre>
        </div>
      </SectionCard>
    );
  }

  const householdsTotal = rows.reduce((s, r) => s + (r.households ?? 0), 0);
  const birthsTotal = rows.reduce((s, r) => s + (r.births ?? 0), 0);

  return (
    <div className="space-y-4">
      {/* KPI strip — financial inclusion & living standards */}
      <section
        aria-label="RDHS 2025 headline indicators"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        {KPI_TILES.map((tile, i) => {
          const Icon = tile.icon;
          const focused = scopedDistrict?.[tile.key];
          const mean = weightedMean(scoped, tile.key, "households");
          const tone = ["emerald", "amber", "sky", "violet"][i];
          const tones = {
            emerald: "text-emerald-600 bg-emerald-50",
            amber: "text-amber-600 bg-amber-50",
            sky: "text-sky-600 bg-sky-50",
            violet: "text-violet-600 bg-violet-50",
          };
          return (
            <article
              key={tile.key}
              className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span className={`rounded-lg p-2 ${tones[tone]}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-600">
                  {tile.label}
                </h3>
              </div>
              <p className="mt-2 text-2xl font-extrabold tabular-nums text-slate-900">
                {pct(focused ?? mean)}
              </p>
              <p className="mt-0.5 text-[11px] font-medium text-slate-500">
                {focused != null
                  ? `${scopedDistrict.district} · in-scope mean ${pct(mean)}`
                  : `national (household-weighted) · ${province || "all 5 provinces"}`}
              </p>
            </article>
          );
        })}
      </section>

      <SectionCard
        ariaLabel="RDHS 2025 district comparison"
        icon={Activity}
        tone="violet"
        title="Living Standards & Poverty Dynamics · RDHS 2025"
        subtitle={
          <>
            Third NISR layer — household + birth recodes · {householdsTotal.toLocaleString("en-US")} households ·{" "}
            {birthsTotal.toLocaleString("en-US")} births
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={province}
              onChange={(e) => setProvince(e.target.value)}
              aria-label="Filter by province"
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-violet-400 focus:outline-none"
            >
              <option value="">All provinces</option>
              {provinces.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <select
              value={selectedDistrict}
              onChange={(e) => onSelectDistrict(e.target.value)}
              aria-label="Focus a district"
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-violet-400 focus:outline-none"
            >
              <option value="">All districts in scope</option>
              {scoped.map((r) => (
                <option key={r.district} value={r.district}>{r.district}</option>
              ))}
            </select>
          </div>
        }
      >
        {/* Chart A — selected indicator across districts */}
        <div className="rounded-xl border border-slate-200 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-bold text-slate-800">
              {indDef.label} by district{" "}
              <span className="font-normal text-slate-500">({indDef.unit}, DHS-weights)</span>
            </h3>
            <select
              value={indicator}
              onChange={(e) => setIndicator(e.target.value)}
              aria-label="Choose indicator to chart"
              className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 focus:border-violet-400 focus:outline-none"
            >
              {CHART_INDICATORS.map((i) => (
                <option key={i.key} value={i.key}>{i.label}</option>
              ))}
            </select>
          </div>
          <div className="max-h-[420px] overflow-y-auto pr-1">
            <ResponsiveContainer width="100%" height={Math.max(220, barData.length * 27 + 30)}>
              <BarChart
                data={barData}
                layout="vertical"
                margin={{ top: 4, right: 28, bottom: 0, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis
                  type="number"
                  domain={[0, Math.ceil(Math.max(10, ...barData.map((d) => d.value)) * 1.15)]}
                  tick={{ fontSize: 10, fill: "#64748b" }}
                />
                <YAxis type="category" dataKey="district" width={92} tick={{ fontSize: 10, fill: "#334155" }} />
                <Tooltip
                  formatter={(v) => [`${Number(v).toFixed(1)} ${indDef.unit}`, indDef.label]}
                  labelStyle={{ fontWeight: 700, fontSize: 11 }}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                  {barData.map((d) => (
                    <Cell
                      key={d.district}
                      cursor="pointer"
                      onClick={() => onSelectDistrict(selectedDistrict === d.district ? "" : d.district)}
                      fill={
                        d.district === selectedDistrict
                          ? "#4338ca"
                          : PROVINCE_COLORS[d.province] ?? "#cbd5e1"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-slate-500">
            {provinces.map((p) => (
              <span key={p} className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: PROVINCE_COLORS[p] }} />
                {p}
              </span>
            ))}
            <span className="ml-auto">
              Click a bar to focus that district · selected: <b className="text-indigo-700">{selectedDistrict || "none"}</b>
            </span>
          </div>
        </div>

        {/* Chart B — wealth quintiles + poverty-dynamics scatter */}
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <div className="rounded-xl border border-slate-200 p-3">
            <h3 className="text-xs font-bold text-slate-800">
              Wealth quintile shares (hv270)
              <span className="ml-1 font-normal text-slate-500">
                {scopedDistrict ? `${scopedDistrict.district} vs in-scope mean` : "in-scope household-weighted mean"}
              </span>
            </h3>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={wealthData} layout="vertical" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={110}
                  tick={{ fontSize: 10, fill: "#334155" }}
                  tickFormatter={(n) => (n.length > 16 ? `${n.slice(0, 15)}…` : n)}
                />
                <Tooltip
                  formatter={(v, name) => [`${Number(v).toFixed(1)}%`, name]}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                {QUINTILES.map((q) => (
                  <Bar key={q.key} dataKey={q.label} stackId="w" fill={q.fill} barSize={18} />
                ))}
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11px] text-slate-600">
              {scopedDistrict ? (
                <>
                  {scopedDistrict.district}: poorest quintile{" "}
                  <b className="text-slate-800">{pct(scopedDistrict.wealth_p20_pct)}</b> · bottom-40%{" "}
                  <b className="text-slate-800">{pct(scopedDistrict.wealth_p40_pct)}</b>
                </>
              ) : (
                <>Pick a district to compare against the in-scope mean.</>
              )}
              {" "}Bottom-40% share is a core Vision 2050 prosperity-tracking lens.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 p-3">
            <h3 className="text-xs font-bold text-slate-800">
              Poverty dynamics — financial inclusion vs prosperity sharing
              <span className="ml-1 font-normal text-slate-500">(dot size = households)</span>
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart margin={{ top: 10, right: 14, bottom: 14, left: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="x"
                  name="Bank account"
                  domain={[0, "dataMax + 5"]}
                  tick={{ fontSize: 10, fill: "#64748b" }}
                  label={{ value: "bank account %", fontSize: 10, position: "insideBottom", offset: -8, fill: "#64748b" }}
                />
                <YAxis
                  dataKey="y"
                  name="Bottom-40% wealth share"
                  width={38}
                  tick={{ fontSize: 10, fill: "#64748b" }}
                />
                <ReferenceLine
                  x={weightedMean(scoped, "bank_account_pct", "households")}
                  stroke="#64748b"
                  strokeDasharray="4 3"
                />
                <ReferenceLine
                  y={weightedMean(scoped, "wealth_p40_pct", "households")}
                  stroke="#64748b"
                  strokeDasharray="4 3"
                />
                <Tooltip
                  formatter={(v, name) => [Number(v).toFixed(1), name]}
                  labelFormatter={() => ""}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <Scatter data={scatterData} fill="#8b5cf6">
                  {scatterData.map((d) => (
                    <Cell
                      key={d.district}
                      cursor="pointer"
                      onClick={() => onSelectDistrict(selectedDistrict === d.district ? "" : d.district)}
                      fill={d.district === selectedDistrict ? "#4338ca" : PROVINCE_COLORS[d.province] ?? "#8b5cf6"}
                      fillOpacity={d.district === selectedDistrict ? 1 : 0.75}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11px] text-slate-600">
              Districts where bank accounts reach farther also capture a larger bottom-40%
              wealth share (household-weighted r ={" "}
              <b className="text-slate-800">{corr != null ? corr.toFixed(2) : "—"}</b>) · dashed lines
              mark in-scope national means.
            </p>
          </div>
        </div>

        {/* Outcomes table — mortality & child nutrition */}
        {outcomes.length > 0 && (
          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full min-w-[560px] text-left text-xs">
              <caption className="sr-only">
                Child mortality and nutrition by district, RDHS 2025 birth recode
              </caption>
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2 font-bold">District</th>
                  <th className="px-3 py-2 text-right font-bold">IMR (‰)</th>
                  <th className="px-3 py-2 text-right font-bold">U5MR (‰)</th>
                  <th className="px-3 py-2 text-right font-bold">Stunting</th>
                  <th className="px-3 py-2 text-right font-bold">Underweight</th>
                  <th className="px-3 py-2 text-right font-bold">Wasting</th>
                  <th className="px-3 py-2 text-right font-bold">Children</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {outcomes.map((d) => (
                  <tr
                    key={d.district}
                    className={`transition-colors hover:bg-slate-50 ${d.district === selectedDistrict ? "bg-indigo-50" : ""}`}
                  >
                    <td className="px-3 py-2 font-semibold text-slate-800">{d.district}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600" title={d.imr_per_1000 != null ? `${d.imr_per_1000.toFixed(1)}‰ (complete-exposure cohort)` : "insufficient exposure"}>
                      {d.imr_per_1000 != null ? d.imr_per_1000.toFixed(1) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                      {d.u5mr_per_1000 != null ? d.u5mr_per_1000.toFixed(1) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">{pct(d.stunting_pct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">{pct(d.underweight_pct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">{pct(d.wasting_pct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-500">{d.children_measured ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-2.5">
          <summary className="cursor-pointer text-[11px] font-semibold text-slate-600">
            Estimation method
          </summary>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
            DHS hv005/v005 survey weights · bank = hv247, fintech use = hv263 · wealth quintiles = hv270 ·
            IMR/U5MR = direct complete-exposure cohort from the birth history (conservative vs the official
            synthetic-cohort tables) · stunting/underweight/wasting = WHO z-score &lt; −2 SD among children
            &lt;60 months · full definitions: <code>GET /api/rdhs/indicators</code>.
          </p>
        </details>
      </SectionCard>
    </div>
  );
}
