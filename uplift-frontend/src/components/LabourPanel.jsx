import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Briefcase, Factory, TrendingDown, Users, GraduationCap } from "lucide-react";
import SectionCard from "./Card";
import ChoroplethMap from "./ChoroplethMap";
import { fetchLabourDisaggregation } from "../lib/api";

const PROVINCE_COLORS = {
  "City of Kigali": "#0ea5e9",
  "Eastern Province": "#f43f5e",
  "Northern Province": "#8b5cf6",
  "Southern Province": "#16a34a",
  "Western Province": "#f59e0b",
};

const MAP_METRICS = [
  { key: "unemployment_rate", label: "Unemployment", direction: "lower" },
  { key: "youth_neet_rate", label: "Youth NEET", direction: "lower" },
  { key: "inactivity_rate", label: "Inactivity", direction: "lower" },
  { key: "informal_employment_rate", label: "Informality", direction: "lower" },
  { key: "employment_ratio", label: "Employment ratio", direction: "higher" },
  { key: "disability_lfpr", label: "Disability LFPR", direction: "higher" },
];

const OPTIONS_LABELS = {
  gender: { male: "Men", female: "Women" },
  education: {
    tvet: "TVET graduates",
    general: "General education",
    no_formal: "No formal education",
  },
  disability: { disabled: "Person with disability", not_disabled: "No disability" },
};

function wmean(rows, key) {
  let w = 0;
  let s = 0;
  for (const r of rows) {
    const val = r[key];
    if (val == null) continue;
    const wt = r.population_weight || 1;
    w += wt;
    s += val * wt;
  }
  return w > 0 ? s / w : null;
}

const fmt = (v, decimals = 1) => (v == null ? "—" : `${Number(v).toFixed(decimals)}%`);

export default function LabourPanel({
  rows = [],
  selectedDistrict = "",
  onSelectDistrict = () => {},
}) {
  const [dimension, setDimension] = useState("education");
  const [disagg, setDisagg] = useState(null);

  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    fetchLabourDisaggregation(dimension, { signal: controller.signal })
      .then((payload) => live && setDisagg(payload))
      .catch(() => live && setDisagg(null));
    return () => {
      live = false;
      controller.abort();
    };
  }, [dimension]);

  const provinces = useMemo(() => [...new Set(rows.map((r) => r.province))].sort(), [rows]);
  const [province, setProvince] = useState("");
  const scoped = useMemo(
    () => (province ? rows.filter((r) => r.province === province) : rows),
    [rows, province],
  );
  const scopedDistrict = useMemo(
    () => (selectedDistrict ? rows.find((r) => r.district === selectedDistrict) ?? null : null),
    [rows, selectedDistrict],
  );

  const regionStats = useMemo(() => {
    const set = scoped.length ? scoped : rows;
    return {
      unemployment: wmean(set, "unemployment_rate"),
      neet: wmean(set, "youth_neet_rate"),
      gender_gap: wmean(set, "lfpr_male") != null && wmean(set, "lfpr_female") != null
        ? wmean(set, "lfpr_male") - wmean(set, "lfpr_female")
        : null,
      tvet_advantage:
        wmean(set, "general_education_unemployment_rate") != null &&
        wmean(set, "tvet_unemployment_rate") != null
          ? wmean(set, "general_education_unemployment_rate") - wmean(set, "tvet_unemployment_rate")
          : null,
    };
  }, [scoped, rows]);

  const scatterData = useMemo(
    () =>
      scoped
        .filter((r) => r.unemployment_rate != null && r.youth_neet_rate != null)
        .map((r) => ({
          x: r.unemployment_rate,
          y: r.youth_neet_rate,
          z: r.population_weight,
          district: r.district,
          province: r.province,
        })),
    [scoped],
  );

  const barData = useMemo(
    () =>
      (disagg?.rows ?? [])
        .map((row) => ({
          district: row.district,
          district_name: row.district,
          // serialise the metric columns under segment labels
          ...Object.fromEntries(
            disagg?.segments.map((seg) => [
              OPTIONS_LABELS[dimension]?.[seg] ?? seg,
              row.metrics?.[seg] ?? null,
            ]) ?? [],
          ),
        }))
        .filter((d) => d.district === selectedDistrict)
        .concat(
          (disagg?.rows ?? [])
            .map((row) => ({
              district: row.district,
              district_name: row.district,
              ...Object.fromEntries(
                disagg?.segments.map((seg) => [
                  OPTIONS_LABELS[dimension]?.[seg] ?? seg,
                  row.metrics?.[seg] ?? null,
                ]) ?? [],
              ),
            }))
            .filter((d) => d.district !== selectedDistrict),
        )
        .slice(0, 14),
    [disagg, dimension, selectedDistrict],
  );

  const league = useMemo(
    () =>
      [...scoped]
        .sort((a, b) => (b.youth_neet_rate ?? 0) - (a.youth_neet_rate ?? 0))
        .slice(0, 10),
    [scoped],
  );

  if (!rows.length) {
    return (
      <SectionCard
        ariaLabel="NISR LFS 2025 labour market"
        icon={Briefcase}
        tone="teal"
        title="Labour Market Intelligence · NISR LFS 2025"
        subtitle="First-data-layer under Module A — 30-district calibrated labour panel"
      >
        <div className="rounded-xl border border-dashed border-teal-300 bg-teal-50/50 p-8 text-center">
          <p className="text-sm font-semibold text-slate-800">LFS 2025 layer not seeded yet</p>
          <pre className="mx-auto mt-3 max-w-md rounded-lg bg-slate-900 px-4 py-3 text-left text-[11px] leading-relaxed text-emerald-300">
            python3 seed_lfs.py --url $DATABASE_URL
          </pre>
        </div>
      </SectionCard>
    );
  }

  const KPI_TILES = [
    {
      label: "Unemployment (LFS 2025)",
      value: fmt(regionStats.unemployment),
      anchor: "national 12.4%",
      icon: TrendingDown,
      tone: "text-rose-600 bg-rose-50",
    },
    {
      label: "Youth NEET",
      value: fmt(regionStats.neet),
      anchor: "nationally 1 in 4 young Rwandans",
      icon: Users,
      tone: "text-amber-600 bg-amber-50",
    },
    {
      label: "LFPR gender gap",
      value: `${regionStats.gender_gap != null ? regionStats.gender_gap.toFixed(1) : "—"} pp`,
      anchor: "official anchor 14.3 pp",
      icon: Users,
      tone: "text-sky-600 bg-sky-50",
    },
    {
      label: "TVET unemployment advantage",
      value: `${regionStats.tvet_advantage != null ? regionStats.tvet_advantage.toFixed(1) : "—"} pp`,
      anchor: "TVET Triton + digital job supply chains",
      icon: GraduationCap,
      tone: "text-emerald-600 bg-emerald-50",
    },
  ];

  return (
    <div className="space-y-4">
      <section aria-label="LFS 2025 headline indicators" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {KPI_TILES.map((tile) => {
          const Icon = tile.icon;
          const focused = Boolean(scopedDistrict);
          return (
            <article key={tile.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <span className={`rounded-lg p-2 ${tile.tone}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-600">{tile.label}</h3>
              </div>
              <p className="mt-2 text-2xl font-extrabold tabular-nums text-slate-900">{tile.value}</p>
              <p className="mt-0.5 text-[11px] font-medium text-slate-500">
                {focused ? `${selectedDistrict} vs national` : "national · weighted"} · {tile.anchor}
              </p>
            </article>
          );
        })}
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] xl:items-start">
        <ChoroplethMap
          rows={scoped}
          metricDefs={MAP_METRICS}
          selectedDistrict={selectedDistrict}
          onSelectDistrict={onSelectDistrict}
          title="Labour-market pressure by district"
          subtitle="NISR RLFS 2025 calibrated panel · click a district to focus"
          tone="teal"
        />

        <SectionCard
          ariaLabel="Unemployment vs youth NEET scatter"
          icon={TrendingDown}
          tone="teal"
          title="Unemployment vs youth idle-ness"
          subtitle="Bubble size = population weight · dashed lines mark in-scope means"
          bodyClass="px-4 py-4"
        >
          <ResponsiveContainer width="100%" height={330}>
            <ScatterChart margin={{ top: 10, right: 14, bottom: 14, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="x"
                name="Unemployment"
                tick={{ fontSize: 9, fill: "#64748b" }}
                label={{ value: "unemployment %", fontSize: 9, position: "insideBottom", offset: -8, fill: "#64748b" }}
              />
              <YAxis
                dataKey="y"
                name="Youth NEET"
                width={38}
                tick={{ fontSize: 9, fill: "#64748b" }}
              />
              <ReferenceLine x={regionStats.unemployment ?? 12.4} stroke="#64748b" strokeDasharray="4 3" />
              <ReferenceLine y={regionStats.neet ?? 24.5} stroke="#64748b" strokeDasharray="4 3" />
              <Tooltip
                formatter={(v, name) => [`${Number(v).toFixed(1)}%`, name === "x" ? "Unemployment" : "Youth NEET"]}
                labelFormatter={() => ""}
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
              />
              <Scatter data={scatterData} fill="#0d9488">
                {scatterData.map((d) => (
                  <Cell
                    key={d.district}
                    cursor="pointer"
                    onClick={() => onSelectDistrict(selectedDistrict === d.district ? "" : d.district)}
                    fill={d.district === selectedDistrict ? "#4338ca" : PROVINCE_COLORS[d.province] ?? "#0d9488"}
                    fillOpacity={d.district === selectedDistrict ? 1 : 0.72}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-slate-500">
            {provinces.map((p) => (
              <span key={p} className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: PROVINCE_COLORS[p] }} />
                {p}
              </span>
            ))}
          </div>
        </SectionCard>
      </div>

      <SectionCard
        ariaLabel="Segment disaggregation and league tables"
        icon={Factory}
        tone="teal"
        title="Who is left out of paid work"
        subtitle={<>Segment unemployment by district — TVET vs general education, gender, disability · <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px]">/api/labour/indicators</code></>}
        actions={
          <>
            <select
              value={province}
              onChange={(e) => setProvince(e.target.value)}
              aria-label="Filter by province"
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-teal-500 focus:outline-none"
            >
              <option value="">All provinces</option>
              {provinces.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <select
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
              aria-label="Choose disaggregation dimension"
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-teal-500 focus:outline-none"
            >
              <option value="education">By education</option>
              <option value="gender">By gender</option>
              <option value="disability">By disability status</option>
            </select>
          </>
        }
        bodyClass="px-4 py-4"
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <div className="rounded-xl border border-slate-200 p-3">
            <h3 className="mb-2 text-xs font-bold text-slate-800">
              {OPTIONS_LABELS[dimension] ? Object.values(OPTIONS_LABELS[dimension]).join(" vs ") : dimension} — unemployment % by district
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(230, barData.length * 30)}>
              <BarChart data={barData} layout="vertical" margin={{ top: 4, right: 24, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis type="category" dataKey="district_name" width={94} tick={{ fontSize: 10, fill: "#334155" }} />
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {Object.values(OPTIONS_LABELS[dimension] ?? {}).map((label, i) => (
                  <Bar key={label} dataKey={label} fill={["#0d9488", "#f59e0b", "#8b5cf6"][i % 3]} barSize={9} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="rounded-xl border border-slate-200 p-3">
            <h3 className="mb-2 text-xs font-bold text-slate-800">Highest youth NEET (in scope)</h3>
            <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight: 300 }}>
              <table className="w-full min-w-[22rem] text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 font-bold">District</th>
                    <th className="px-3 py-2 text-right font-bold">NEET</th>
                    <th className="px-3 py-2 text-right font-bold">Unemp.</th>
                    <th className="px-3 py-2 text-right font-bold">Informality</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {league.map((d) => (
                    <tr
                      key={d.district}
                      onClick={() => onSelectDistrict(selectedDistrict === d.district ? "" : d.district)}
                      className={`cursor-pointer transition-colors hover:bg-slate-50 ${d.district === selectedDistrict ? "bg-indigo-50" : ""}`}
                    >
                      <td className="px-3 py-2 font-semibold text-slate-800">{d.district}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.youth_neet_rate?.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.unemployment_rate?.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.informal_employment_rate?.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-2.5">
          <summary className="cursor-pointer text-[11px] font-semibold text-slate-600">
            Methodology & official anchors
          </summary>
          <div className="mt-2 space-y-1 text-[11px] leading-relaxed text-slate-600">
            <p>
              Official anchors: unemployment 12.4% · youth NEET 24.5% · LFPR 66.3% with a 14.3 pp gap
              (male 73.4% vs female 59.0%) · inactivity is deepest in Gisagara, Nyaruguru and Ruhango;
              urban unemployment is structurally higher while deep-rural informality is universal.
            </p>
            <p>
              NISR RLFS 2025 microdata panel expanded to all 30 districts with population-weighted
              calibration to the official national hierarchy (employment → labour force → working-age
              population). API: <code>GET /api/labour/districts</code> · <code>/summary</code> ·{" "}
              <code>/disaggregation</code>.
            </p>
          </div>
        </details>
      </SectionCard>
    </div>
  );
}
