import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { HeartHandshake, HandCoins, ShieldAlert, Clock3, Landmark } from "lucide-react";
import SectionCard from "./Card";
import ChoroplethMap from "./ChoroplethMap";
import { fetchVupSummary } from "../lib/api";

const MAP_METRICS = [
  { key: "caseload_per_1000", label: "Caseload /1000", direction: "higher" },
  { key: "poverty_rate_among_beneficiaries", label: "Beneficiary poverty", direction: "lower" },
  { key: "payment_timeliness_pct", label: "Timeliness", direction: "higher" },
  { key: "moderate_among_beneficiaries", label: "Moderate VUP", direction: "lower" },
];

const COMPONENTS = [
  { key: "beneficiaries_ds", label: "Direct Support (DS)", fill: "#be123c" },
  { key: "beneficiaries_cpw", label: "Classic Public Works", fill: "#0d9488" },
  { key: "beneficiaries_epw", label: "Expanded Public Works", fill: "#38bdf8" },
  { key: "beneficiaries_nsds", label: "Financial Services (NSDS)", fill: "#8b5cf6" },
  { key: "beneficiaries_fs", label: "Farming Support (FS)", fill: "#f59e0b" },
];

const CHANNEL_COLORS = [
  { key: "umurenge_sacco", label: "Umurenge SACCO", color: "#0ea5e9" },
  { key: "mobile_money", label: "Mobile money", color: "#8b5cf6" },
  { key: "cash_pickup", label: "Cash pickup", color: "#f59e0b" },
];

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

const fmt = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);
const money = (v) => (v == null ? "—" : v.toLocaleString("en-US"));

export default function VupPanel({
  rows = [],
  selectedDistrict = "",
  onSelectDistrict = () => {},
}) {
  const [summary, setSummary] = useState(null);
  const [province, setProvince] = useState("");

  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    fetchVupSummary({ signal: controller.signal })
      .then((payload) => live && setSummary(payload))
      .catch(() => live && setSummary(null));
    return () => {
      live = false;
      controller.abort();
    };
  }, []);

  const provinces = useMemo(() => [...new Set(rows.map((r) => r.province))].sort(), [rows]);
  const scoped = useMemo(
    () => (province ? rows.filter((r) => r.province === province) : rows),
    [rows, province],
  );

  const componentTotals = useMemo(() => {
    const totals = summary?.national?.component_totals;
    if (totals) {
      return COMPONENTS.map((c) => ({ ...c, total: totals[c.key] }));
    }
    return COMPONENTS.map((c) => ({ ...c, total: rows.reduce((s, r) => s + (r[c.key] ?? 0), 0) }));
  }, [summary, rows]);

  const channelData = useMemo(() => {
    if (!rows.length) return [];
    return CHANNEL_COLORS.map((ch) => ({
      name: ch.label,
      value: Number(wmean(rows, ch.key) ?? 0),
      color: ch.color,
    }));
  }, [rows]);

  const districtLeague = useMemo(
    () =>
      [...scoped]
        .sort((a, b) => (b.poverty_rate_among_beneficiaries ?? 0) - (a.poverty_rate_among_beneficiaries ?? 0))
        .slice(0, 10),
    [scoped],
  );

  if (!rows.length) {
    return (
      <SectionCard
        ariaLabel="VUP social protection tracker"
        icon={HeartHandshake}
        tone="emerald"
        title="VUP & Social Protection Tracker"
        subtitle="Module B — 30-district caseload, poverty and payment telemetry"
      >
        <div className="rounded-xl border border-dashed border-emerald-300 bg-emerald-50/50 p-8 text-center">
          <p className="text-sm font-semibold text-slate-800">VUP layer not seeded yet</p>
          <pre className="mx-auto mt-3 max-w-md rounded-lg bg-slate-900 px-4 py-3 text-left text-[11px] leading-relaxed text-emerald-300">
            python3 seed_vup.py --url $DATABASE_URL
          </pre>
        </div>
      </SectionCard>
    );
  }

  const totalBeneficiaries = componentTotals.reduce((s, c) => s + (c.total ?? 0), 0);
  const povertyAmong = summary?.national?.poverty_among_beneficiaries ?? wmean(rows, "poverty_rate_among_beneficiaries");
  const extreme = summary?.national?.extreme_among_beneficiaries ?? wmean(rows, "extreme_rate_among_beneficiaries");
  const timeliness = summary?.national?.payment_timeliness ?? wmean(rows, "payment_timeliness_pct");

  const KPI_TILES = [
    {
      label: "Total VUP beneficiaries",
      value: money(totalBeneficiaries),
      anchor: "5 components · NST2 totals",
      icon: HandCoins,
      tone: "text-emerald-600 bg-emerald-50",
    },
    {
      label: "Poverty among clients",
      value: fmt(povertyAmong),
      anchor: extreme != null ? `extreme ${extreme.toFixed(1)}% · official anchor ~41%` : "official anchor ~41%",
      icon: ShieldAlert,
      tone: "text-rose-600 bg-rose-50",
    },
    {
      label: "Payment timeliness",
      value: fmt(timeliness),
      anchor: "on-time disbursements",
      icon: Clock3,
      tone: "text-sky-600 bg-sky-50",
    },
    {
      label: "SACCO disbursement share",
      value: `${Number(channelData[0]?.value ?? 0).toFixed(0)}%`,
      anchor: "Umurenge SACCO rails",
      icon: Landmark,
      tone: "text-amber-600 bg-amber-50",
    },
  ];

  return (
    <div className="space-y-4">
      <section aria-label="VUP headline indicators" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPI_TILES.map((tile) => {
          const Icon = tile.icon;
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
                {province ? `${province} scope` : "national (weighted)"} · {tile.anchor}
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
          title="VUP reach and welfare by district"
          subtitle="Caseload intensity, poverty among beneficiaries, payment timeliness · click a district to focus"
          tone="emerald"
        />

        <SectionCard
          ariaLabel="VUP component composition"
          icon={HeartHandshake}
          tone="emerald"
          title="Five-pillar caseload architecture"
          subtitle="Public works, direct support and livelihood tracks"
          bodyClass="px-4 py-4"
        >
          <ResponsiveContainer width="100%" height={210}>
            <BarChart data={componentTotals} margin={{ top: 6, right: 16, bottom: 26, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#64748b" }} interval={0} />
              <YAxis tick={{ fontSize: 9, fill: "#64748b" }} width={52} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
              <Tooltip
                formatter={(v) => [`${Number(v).toLocaleString()} beneficiaries`, "Caseload"]}
                labelFormatter={(l) => l}
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
              />
              <Bar dataKey="total" radius={[6, 6, 0, 0]} barSize={34}>
                {componentTotals.map((c) => (
                  <Cell key={c.key} fill={c.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <h3 className="mt-3 text-xs font-bold text-slate-800">Disbursement channels</h3>
          <ResponsiveContainer width="100%" height={170}>
            <PieChart>
              <Pie
                data={channelData}
                dataKey="value"
                nameKey="name"
                innerRadius={38}
                outerRadius={62}
                paddingAngle={2}
              >
                {channelData.map((ch) => (
                  <Cell key={ch.name} fill={ch.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 text-[11px] text-slate-600">
            {channelData.map((ch) => (
              <span key={ch.name} className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: ch.color }} />
                {ch.name} <b className="text-slate-800">{ch.value.toFixed(1)}%</b>
              </span>
            ))}
          </div>
        </SectionCard>
      </div>

      <SectionCard
        ariaLabel="VUP district league"
        icon={ShieldAlert}
        tone="emerald"
        title="Welfare of households inside the programme"
        subtitle="Poverty among VUP clients tracks district poverty intensity — deep-rural districts carry ~45% client poverty vs Kigali core ~34%"
        actions={
          <select
            value={province}
            onChange={(e) => setProvince(e.target.value)}
            aria-label="Filter by province"
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-emerald-500 focus:outline-none"
          >
            <option value="">All provinces</option>
            {provinces.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        }
        bodyClass="px-4 py-4"
      >
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full min-w-[640px] text-left text-xs">
            <caption className="sr-only">
              VUP caseload and welfare by district, 2025 panel
            </caption>
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 font-bold">District</th>
                <th className="px-3 py-2 text-right font-bold">DS</th>
                <th className="px-3 py-2 text-right font-bold">cPW</th>
                <th className="px-3 py-2 text-right font-bold">ePW</th>
                <th className="px-3 py-2 text-right font-bold">FS</th>
                <th className="px-3 py-2 text-right font-bold">Client poverty</th>
                <th className="px-3 py-2 text-right font-bold">Extreme</th>
                <th className="px-3 py-2 text-right font-bold">Timeliness</th>
                <th className="px-3 py-2 text-right font-bold">Caseload /1000</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {districtLeague.map((d) => (
                <tr
                  key={d.district}
                  onClick={() => onSelectDistrict(selectedDistrict === d.district ? "" : d.district)}
                  className={`cursor-pointer transition-colors hover:bg-slate-50 ${d.district === selectedDistrict ? "bg-indigo-50" : ""}`}
                >
                  <td className="px-3 py-2 font-semibold text-slate-800">{d.district}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{money(d.beneficiaries_ds)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{money(d.beneficiaries_cpw)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{money(d.beneficiaries_epw)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{money(d.beneficiaries_fs)}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-semibold text-rose-700">
                    {d.poverty_rate_among_beneficiaries?.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.extreme_rate_among_beneficiaries?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.payment_timeliness_pct?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">{d.caseload_per_1000?.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-2.5">
          <summary className="cursor-pointer text-[11px] font-semibold text-slate-600">
            Methodology & official anchors
          </summary>
          <div className="mt-2 space-y-1 text-[11px] leading-relaxed text-slate-600">
            <p>
              Official anchors: ~41% poverty among VUP beneficiaries (12.5 extreme + 28.5 moderate;
              EICV7 household register basis) · national component totals DS 131,500 · cPW 246,000 ·
              ePW 158,500 · NSDS 47,200 · FS 88,600 · timeliness 91% · disbursement mix SACCO 61% /
              MoMo 24% / cash 15%.
            </p>
            <p>
              Caseloads distributed by population × poverty-intensity × archetypes, largest-remainder
              rounding to hit exact national totals. API: <code>GET /api/vup/districts</code> ·{" "}
              <code>/summary</code> · <code>/metrics</code>.
            </p>
          </div>
        </details>
      </SectionCard>
    </div>
  );
}
