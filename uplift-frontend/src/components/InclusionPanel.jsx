import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Landmark, Sparkles, Wallet, RotateCcw } from "lucide-react";
import SectionCard from "./Card";
import {
  fetchInclusionDistricts,
  fetchMatchmakerCatalog,
  postMatchmakerRecommendations,
} from "../lib/api";

const TIER_BANDS = [
  { key: "financial_health", label: "Healthy", color: "#047857" },
  { key: "financially_coping", label: "Coping", color: "#65a30d" },
  { key: "financially_vulnerable", label: "Vulnerable", color: "#f59e0b" },
  { key: "extremely_vulnerable", label: "Extreme", color: "#dc2626" },
];

const HEADLINE_METRICS = [
  { label: "Included", key: "financial_inclusion_rate", official: 96.0, tone: "text-emerald-600 bg-emerald-50" },
  { label: "Formal credit", key: "formal_credit", official: 24, tone: "text-sky-600 bg-sky-50" },
  { label: "Formal savings", key: "formal_savings", official: 59, tone: "text-violet-600 bg-violet-50" },
  { label: "Mobile money", key: "mobile_money", official: 77, tone: "text-amber-600 bg-amber-50" },
];

const CATEGORY_ACCENT = {
  savings: "bg-emerald-100 text-emerald-800",
  credit: "bg-sky-100 text-sky-800",
  subsidy: "bg-amber-100 text-amber-800",
  insurance: "bg-rose-100 text-rose-800",
};

const DEFAULT_PROFILE = {
  age_group: "youth",
  gender: "female",
  occupation: "farmer",
  goal: "start",
  has_phone: true,
  has_sacco_membership: false,
  district: "",
};

const FIELD_LABEL = "mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500";
const SELECT_CLASS =
  "h-10 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-sm text-slate-900 shadow-sm transition focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/15";

const meanMetric = (rows, key) =>
  rows.reduce((sum, r) => sum + (r.metrics?.[key] ?? 0), 0) / rows.length;

const humanize = (slug) => String(slug).replace(/_/g, " ");

function DropdownField({ label, value, onChange, children }) {
  return (
    <label className="block">
      <span className={FIELD_LABEL}>{label}</span>
      <select value={value} onChange={onChange} className={SELECT_CLASS}>
        {children}
      </select>
    </label>
  );
}

function EnumField({ field, value, options, onChange }) {
  return (
    <DropdownField label={field} value={value} onChange={onChange}>
      {options.map((v) => (
        <option key={v} value={v}>{humanize(v)}</option>
      ))}
    </DropdownField>
  );
}

function HealthPyramid({ rows }) {
  return (
    <SectionCard
      ariaLabel="FinScope financial-health tiers"
      icon={Wallet}
      tone="violet"
      title="Financial health pyramid (FinScope 2024)"
      subtitle="Only 1 in 10 Rwandan adults is financially healthy; 34% are vulnerable or extreme"
    >
      <div className="mb-3 flex h-9 overflow-hidden rounded-lg" role="img" aria-label="Financial health tiers">
        {TIER_BANDS.map((tier) => {
          const width = meanMetric(rows, tier.key);
          return (
            <div
              key={tier.key}
              className="flex items-center justify-center text-[10px] font-bold text-white sm:text-[11px]"
              style={{ width: `${width}%`, background: tier.color }}
              title={`${tier.label}: ${width.toFixed(1)}%`}
            >
              {width >= 8 ? `${width.toFixed(0)}%` : ""}
            </div>
          );
        })}
      </div>
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1">
        {TIER_BANDS.map(({ key, label, color }) => (
          <span key={key} className="flex items-center gap-1 text-[10px] font-semibold text-slate-600">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} aria-hidden="true" />
            {label}{' '}
            <span className="tabular-nums">{meanMetric(rows, key).toFixed(1)}%</span>
          </span>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {HEADLINE_METRICS.map((m) => {
          const value = meanMetric(rows, m.key);
          return (
            <article key={m.key} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-600">{m.label}</p>
              <p className="mt-1 text-xl font-extrabold tabular-nums text-slate-900">
                {value > 0.05 ? `${value.toFixed(0)}%` : "—"}
              </p>
              <p className="text-[10px] font-medium text-slate-500">official {m.official}%</p>
            </article>
          );
        })}
      </div>
    </SectionCard>
  );
}

function MatchResult({ result, rank }) {
  const reasons = result.reasons.slice(0, 3);
  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
            #{rank} · {result.provider}
          </p>
          <h3 className="text-sm font-bold text-slate-900">{result.name}</h3>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
            CATEGORY_ACCENT[result.category] ?? "bg-slate-100 text-slate-700"
          }`}
        >
          {result.category}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-violet-600"
            style={{ width: `${Math.round(result.score)}%` }}
            aria-hidden="true"
          />
        </div>
        <span className="text-xs font-bold tabular-nums text-violet-700">{Math.round(result.score)}</span>
      </div>
      <p className="mt-2 text-[11px] text-slate-600">{result.description}</p>
      <ul className="mt-2 space-y-1">
        {reasons.map((r) => (
          <li key={r.part ?? r.detail} className="flex gap-1.5 text-[11px] text-slate-600">
            <span aria-hidden="true" className="text-emerald-600">✓</span>
            {r.detail}
          </li>
        ))}
      </ul>
      {result.evidence && (
        <p className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[10px] italic leading-relaxed text-slate-500">
          {result.evidence}
        </p>
      )}
    </li>
  );
}

export default function InclusionPanel({ rows: rowsProp = [], selectedDistrict = "" }) {
  const [fetchedRows, setFetchedRows] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [results, setResults] = useState(null);
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState(null);
  const rows = rowsProp.length ? rowsProp : fetchedRows;

  useEffect(() => {
    if (rowsProp.length) return;
    const controller = new AbortController();
    fetchInclusionDistricts({ signal: controller.signal })
      .then((data) => data && setFetchedRows(data))
      .catch(() => {});
    fetchMatchmakerCatalog({ signal: controller.signal })
      .then((payload) => payload && setCatalog(payload))
      .catch(() => {});
    return () => controller.abort();
  }, [rowsProp.length]);

  // The map/tab selection drives the district field; local edits take over when
  // the user picks a different district themselves.
  const focusDistrict = selectedDistrict || profile.district;

  const creditGap = useMemo(
    () =>
      rows
        .map((r) => ({ district: r.district, value: r.metrics?.formal_credit ?? null }))
        .filter((d) => d.value != null)
        .sort((a, b) => a.value - b.value)
        .slice(0, 12),
    [rows],
  );

  const districtOptions = useMemo(() => rows.map((r) => r.district).sort(), [rows]);
  const enums = catalog?.profile_enums ?? null;

  const submit = async (event) => {
    event.preventDefault();
    setPosting(true);
    setPostError(null);
    try {
      const payload = { ...profile };
      if (focusDistrict && focusDistrict !== "National") payload.district = focusDistrict;
      else delete payload.district;
      const body = await postMatchmakerRecommendations(payload);
      setResults(body);
    } catch (err) {
      setResults(null);
      setPostError(err?.message ?? "The matchmaker request failed.");
    } finally {
      setPosting(false);
    }
  };

  const resetForm = () => {
    setProfile(DEFAULT_PROFILE);
    setResults(null);
    setPostError(null);
  };

  if (!rows.length) {
    return (
      <SectionCard
        ariaLabel="Financial inclusion and credit matchmaker"
        icon={Landmark}
        tone="violet"
        title="Inclusion & Opportunity Matchmaker · FinScope 2024"
      >
        <div className="rounded-xl border border-dashed border-violet-300 bg-violet-50/50 p-8 text-center">
          <p className="text-sm font-semibold text-slate-800">FinScope layer loading… or not seeded</p>
          <pre className="mx-auto mt-3 max-w-md rounded-lg bg-slate-900 px-4 py-3 text-left text-[11px] leading-relaxed text-emerald-300">
            python3 seed_data.py && python3 seed_lfs.py && python3 seed_vup.py
          </pre>
        </div>
      </SectionCard>
    );
  }

  return (
    <div className="space-y-4">
      <HealthPyramid rows={rows} />

      <SectionCard
        ariaLabel="District credit gaps"
        icon={Landmark}
        tone="violet"
        title="Where formal credit reaches the fewest adults"
        subtitle="Bottom 12 districts by formal credit use — prime matchmaker targets"
        bodyClass="px-4 py-4"
      >
        <ResponsiveContainer width="100%" height={Math.max(220, creditGap.length * 28)}>
          <BarChart data={creditGap} layout="vertical" margin={{ top: 4, right: 30, bottom: 0, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} unit="%" />
            <YAxis type="category" dataKey="district" width={94} tick={{ fontSize: 10, fill: "#334155" }} />
            <Tooltip
              formatter={(v, name) => [`${Number(v).toFixed(1)}%`, name === "value" ? "Formal credit" : "Mobile money"]}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Bar dataKey="value" radius={[0, 5, 5, 0]} barSize={13} fill="#7c3aed" />
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-[11px] text-slate-600">
          National anchors: inclusion 96% · formal credit 24% · vulnerable + extreme 34%.
        </p>
      </SectionCard>

      <SectionCard
        ariaLabel="Opportunity and credit matchmaker"
        icon={Sparkles}
        tone="violet"
        title="Opportunity & Credit Matchmaker"
        subtitle="Describe the profile — get an explainable shortlist of products they can use today"
        actions={
          <button
            type="button"
            onClick={resetForm}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-500"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Reset
          </button>
        }
      >
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <DropdownField
              label="District focus"
              value={focusDistrict === "National" ? "" : focusDistrict}
              onChange={(e) => setProfile((p) => ({ ...p, district: e.target.value }))}
            >
              <option value="National">National (all districts)</option>
              {districtOptions.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </DropdownField>
            <EnumField
              field="Main goal"
              value={profile.goal}
              options={enums?.goal ?? ["start"]}
              onChange={(e) => setProfile((p) => ({ ...p, goal: e.target.value }))}
            />
            <EnumField
              field="Occupation"
              value={profile.occupation}
              options={enums?.occupation ?? ["farmer"]}
              onChange={(e) => setProfile((p) => ({ ...p, occupation: e.target.value }))}
            />
            <EnumField
              field="Age group"
              value={profile.age_group}
              options={enums?.age_group ?? ["youth", "adult"]}
              onChange={(e) => setProfile((p) => ({ ...p, age_group: e.target.value }))}
            />
            <EnumField
              field="Gender"
              value={profile.gender}
              options={enums?.gender ?? ["female", "male", "prefer_not_to_say"]}
              onChange={(e) => setProfile((p) => ({ ...p, gender: e.target.value }))}
            />
            <div className="flex items-end">
              <button
                type="submit"
                disabled={posting}
                className="h-10 w-full rounded-lg bg-violet-700 px-3 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-800 disabled:opacity-60"
              >
                {posting ? "Matching…" : "Show my matches"}
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-6 border-t border-slate-100 pt-3">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
              <input
                type="checkbox"
                checked={profile.has_phone}
                onChange={(e) => setProfile((p) => ({ ...p, has_phone: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-300 text-violet-700"
              />
              Has a phone
            </label>
            <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
              <input
                type="checkbox"
                checked={profile.has_sacco_membership}
                onChange={(e) => setProfile((p) => ({ ...p, has_sacco_membership: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-300 text-violet-700"
              />
              Already a SACCO member
            </label>
          </div>
        </form>

        {postError && (
          <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700">
            {postError}
          </p>
        )}

        {results && (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-slate-600">
              Matched <b>{results.profile?.district ?? "national"}</b> context — formal credit{" "}
              {results.district_context?.formal_credit ?? "—"}%, mobile money{" "}
              {results.district_context?.mobile_money ?? "—"}%, VUP client poverty{" "}
              {results.district_context?.poverty_among_vup_beneficiaries ?? "—"}%
            </p>
            <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {results.results.map((res, i) => (
                <MatchResult key={res.product_id} result={res} rank={i + 1} />
              ))}
            </ol>
            <p className="text-[11px] italic text-slate-500">{results.disclaimer}</p>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
