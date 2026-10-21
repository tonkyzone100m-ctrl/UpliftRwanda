import { MapPin, RefreshCw, RotateCcw, Search, Table, X } from "lucide-react";
import { categoryLabels, categoryOptions } from "../lib/filters";

function SearchField({ query, onQueryChange }) {
  return (
    <div className="min-w-0 flex-1 sm:max-w-md">
      <label htmlFor="metric-search" className="mb-1.5 block text-xs font-semibold text-gray-600">
        Search indicators, districts or provinces
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
        <input
          id="metric-search"
          type="search"
          autoComplete="off"
          placeholder="e.g. “mobile money”, “poverty”, “Kigali”…"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-gray-50 py-2.5 pl-9 pr-9 text-sm text-gray-900 shadow-sm transition placeholder:text-gray-400 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/15"
        />
        {query ? (
          <button
            type="button"
            onClick={() => onQueryChange("")}
            aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function DistrictSelect({ regions, value, onChange, disabled }) {
  const byProvince = new Map();
  for (const r of regions) {
    if (!byProvince.has(r.province)) byProvince.set(r.province, []);
    byProvince.get(r.province).push(r);
  }
  return (
    <div className="sm:w-56">
      <label htmlFor="district-select" className="mb-1.5 block text-xs font-semibold text-gray-600">
        District
      </label>
      <div className="relative">
        <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
        <select
          id="district-select"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none rounded-lg border border-gray-300 bg-gray-50 py-2.5 pl-9 pr-8 text-sm font-medium text-gray-900 shadow-sm transition focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/15 disabled:opacity-50"
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
        <svg className="pointer-events-none absolute right-3 top-1/2 h-3 w-3 -translate-y-1/2 text-gray-400" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

function CategoryFilter({ options, labels, value, onChange, disabled }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-gray-600">Data category</p>
      <div role="group" aria-label="Filter by data category" className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={disabled}
          aria-pressed={value === "all"}
          onClick={() => onChange("all")}
          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-emerald-700/15 disabled:opacity-50 ${
            value === "all"
              ? "border-emerald-700 bg-emerald-700 text-white shadow-sm"
              : "border-gray-300 bg-white text-gray-600 hover:border-emerald-700 hover:text-emerald-700"
          }`}
        >
          All categories
        </button>
        {options.map(([id, count]) => {
          const active = value === id;
          const label = labels.get(id) ?? id.replace(/-/g, " ");
          return (
            <button
              key={id}
              type="button"
              disabled={disabled}
              aria-pressed={active}
              onClick={() => onChange(id)}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-emerald-700/15 disabled:opacity-50 ${
                active
                  ? "border-emerald-700 bg-emerald-700 text-white shadow-sm"
                  : "border-gray-300 bg-white text-gray-600 hover:border-emerald-700 hover:text-emerald-700"
              }`}
            >
              {label}
              <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] ${active ? "bg-white/15 text-white" : "bg-gray-100 text-gray-500"}`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
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
  const hasActive = Boolean(filters.query || filters.categoryId !== "all" || filters.district);
  const time = updatedAt ? updatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";

  return (
    <section aria-label="Filters and search" className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-4 sm:flex-row sm:items-end">
          <SearchField query={filters.query} onQueryChange={(query) => onChange({ ...filters, query })} />
          <DistrictSelect
            regions={regions}
            value={filters.district}
            disabled={!regions.length}
            onChange={(district) => onChange({ ...filters, district })}
          />
        </div>
        <CategoryFilter
          options={options}
          labels={labels}
          value={filters.categoryId}
          disabled={!displayRows.length}
          onChange={(categoryId) => onChange({ ...filters, categoryId })}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-3">
        <p className="flex items-center gap-1.5 text-xs text-gray-500">
          <Table className="h-3.5 w-3.5 text-gray-400" aria-hidden="true" />
          <span>
            Showing <span className="font-semibold text-gray-700">{matchCount}</span> of{" "}
            <span className="font-semibold text-gray-700">{totalCount}</span> data points
            {filters.district ? ` in ${filters.district}` : " across all districts"} · updated {time}
          </span>
        </p>
        <div className="flex items-center gap-2">
          {hasActive && (
            <button
              type="button"
              onClick={() => onChange({ query: "", categoryId: "all", district: "" })}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Reset filters
            </button>
          )}
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-2.5 py-1 text-xs font-semibold text-gray-600 transition hover:bg-gray-50 hover:text-gray-800"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>
    </section>
  );
}
