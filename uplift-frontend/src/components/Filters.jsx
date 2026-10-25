import { MapPin, RefreshCw, RotateCcw, Search, SlidersHorizontal, Table, X } from "lucide-react";
import { categoryLabels, categoryOptions, hasActiveFilters } from "../lib/filters";
import { categoryStyle } from "../lib/categories";

const CONTROL_CLASSES =
  "h-10 w-full appearance-none rounded-lg border border-slate-300 bg-white text-sm text-slate-900 shadow-sm transition focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400";

const CHEVRON = (
  <svg
    className="pointer-events-none absolute right-3 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400"
    viewBox="0 0 12 12"
    aria-hidden="true"
  >
    <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function FieldLabel({ htmlFor, children }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-600"
    >
      {children}
    </label>
  );
}

function SearchField({ query, onQueryChange }) {
  return (
    <div className="sm:col-span-2 lg:col-span-5">
      <FieldLabel htmlFor="metric-search">Search indicators · districts · provinces</FieldLabel>
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
        <input
          id="metric-search"
          type="search"
          autoComplete="off"
          placeholder="e.g. mobile money, poverty, Kigali…"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          className={`${CONTROL_CLASSES} pl-9 pr-9`}
        />
        {query ? (
          <button
            type="button"
            onClick={() => onQueryChange("")}
            aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function DistrictField({ regions, value, onChange, disabled }) {
  const byProvince = new Map();
  for (const r of regions) {
    if (!byProvince.has(r.province)) byProvince.set(r.province, []);
    byProvince.get(r.province).push(r);
  }
  return (
    <div className="sm:col-span-1 lg:col-span-3">
      <FieldLabel htmlFor="district-select">District</FieldLabel>
      <div className="relative">
        <MapPin
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
        <select
          id="district-select"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={`${CONTROL_CLASSES} pl-9 pr-8 font-medium`}
        >
          <option value="">All districts</option>
          {[...byProvince.entries()].map(([province, districts]) => (
            <optgroup key={province} label={province}>
              {districts.map((d) => (
                <option key={d.district} value={d.district}>
                  {d.district}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {CHEVRON}
      </div>
    </div>
  );
}

function CategoryField({ options, labels, value, onChange, disabled, totalCount }) {
  return (
    <div className="sm:col-span-1 lg:col-span-4">
      <FieldLabel htmlFor="category-select">Data category</FieldLabel>
      <div className="relative">
        <SlidersHorizontal
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
        <select
          id="category-select"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={`${CONTROL_CLASSES} pl-9 pr-8 font-medium`}
        >
          <option value="all">All categories · {totalCount} data points</option>
          {options.map(([id, count]) => (
            <option key={id} value={id}>
              {labels.get(id) ?? id.replace(/-/g, " ")} · {count}
            </option>
          ))}
        </select>
        {CHEVRON}
      </div>
    </div>
  );
}

function FilterChip({ label, dotClass, onRemove }) {
  return (
    <span className="inline-flex max-w-48 items-center gap-1.5 rounded-full border border-slate-200 bg-white py-0.5 pl-2 pr-1 text-[11px] font-semibold text-slate-600 shadow-sm">
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} />
      <span className="truncate">{label}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove filter: ${label}`}
        className="my-0.5 ml-0.5 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
      >
        <X className="h-3 w-3" aria-hidden="true" />
      </button>
    </span>
  );
}

export default function Filters({
  regions,
  displayRows,
  filters,
  onChange,
  matchCount,
  totalCount,
  updatedAt,
  onRefresh,
}) {
  const options = categoryOptions(displayRows);
  const labels = categoryLabels(displayRows);
  const hasActive = hasActiveFilters(filters);
  const time = updatedAt
    ? updatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "—";

  const settle = (patch) => onChange({ ...filters, ...patch });

  const chips = [];
  if (filters.district) {
    chips.push({ key: "district", label: filters.district, dot: "bg-sky-500", clear: () => settle({ district: "" }) });
  }
  if (filters.categoryId !== "all") {
    chips.push({
      key: "category",
      label: labels.get(filters.categoryId) ?? filters.categoryId,
      dot: categoryStyle(filters.categoryId).dot,
      clear: () => settle({ categoryId: "all" }),
    });
  }
  if (filters.query) {
    chips.push({ key: "query", label: `“${filters.query}”`, dot: "bg-emerald-500", clear: () => settle({ query: "" }) });
  }

  return (
    <section
      aria-label="Filters and search"
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="grid grid-cols-1 gap-3 px-5 py-4 sm:grid-cols-2 lg:grid-cols-12 lg:items-end">
        <SearchField query={filters.query} onQueryChange={(query) => settle({ query })} />
        <DistrictField
          regions={regions}
          value={filters.district}
          disabled={!regions.length}
          onChange={(district) => settle({ district })}
        />
        <CategoryField
          options={options}
          labels={labels}
          value={filters.categoryId}
          totalCount={totalCount}
          disabled={!displayRows.length}
          onChange={(categoryId) => settle({ categoryId })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 bg-slate-50/60 px-5 py-2.5">
        <p className="flex items-center gap-1.5 text-[11px] text-slate-600">
          <Table className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
          <span>
            <span className="font-bold text-slate-700">{matchCount.toLocaleString()}</span> of{" "}
            <span className="font-bold text-slate-700">{totalCount.toLocaleString()}</span> data points
            {filters.district ? ` in ${filters.district}` : " across all districts"} · synced {time}
          </span>
        </p>

        {chips.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5" aria-live="polite">
            {chips.map((chip) => (
              <FilterChip key={chip.key} label={chip.label} dotClass={chip.dot} onRemove={chip.clear} />
            ))}
          </div>
        )}

        <div className="ml-auto flex items-center gap-1.5">
          {hasActive && (
            <button
              type="button"
              onClick={() => onChange({ query: "", categoryId: "all", district: "" })}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-bold text-emerald-700 transition hover:bg-emerald-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Reset
            </button>
          )}
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 hover:text-slate-800"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>
    </section>
  );
}
