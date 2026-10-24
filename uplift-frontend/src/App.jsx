import { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from "react";
import { FileSearch2, RefreshCw } from "lucide-react";

import Header from "./components/Header";
import Filters from "./components/Filters";
import SummaryCards from "./components/SummaryCards";
import DistrictFocus from "./components/DistrictFocus";
import PolicyInsights from "./components/PolicyInsights";
import MetricsTable from "./components/MetricsTable";
import ScenarioLab from "./components/ScenarioLab";
import CFSVAPanel from "./components/CFSVAPanel";
import MinisterialPortal from "./components/MinisterialPortal";

const DistrictMap = lazy(() => import("./components/DistrictMap"));
const RDHSPanel = lazy(() => import("./components/RDHSPanel"));
const LabourPanel = lazy(() => import("./components/LabourPanel"));
const VupPanel = lazy(() => import("./components/VupPanel"));
const InclusionPanel = lazy(() => import("./components/InclusionPanel"));
const BriefCard = lazy(() => import("./components/BriefCard"));
import { ErrorBanner, ErrorState, Footer, LoadingState } from "./components/Status";
import {
  fetchCfsvaMetrics,
  fetchInclusionDistricts,
  fetchLabourDistricts,
  fetchMetrics,
  fetchRdhsDistricts,
  fetchVupDistricts,
} from "./lib/api";
import { toDisplayRows, filterDisplayRows } from "./lib/filters";
import { buildRegions, computeNationalStats } from "./lib/stats";
import { getSession } from "./lib/auth";

function syncPortalSession() {
  const session = getSession();
  return session?.expiresAt ? { username: session.username, expiresAt: session.expiresAt } : null;
}

/** Synthetic region of national means so insights work in the "All districts" view. */
function buildNationalRegion(stats) {
  if (!stats) return null;
  const metricMap = {};
  for (const defKey of Object.keys(stats.perMetric)) {
    const bucket = stats.perMetric[defKey];
    metricMap[defKey] = {
      value: bucket.mean,
      unit: bucket.values[0]?.unit ?? "",
      indicator_code: defKey,
      indicator_name: `National average · ${bucket.values.length} districts`,
    };
  }
  return {
    district: "National Average",
    province: "Rwanda",
    areaType: "national",
    years: stats.years,
    metrics: Object.values(metricMap),
    metricMap,
  };
}

const TABS = [
  { id: "dashboard", label: "National Intelligence Dashboard" },
  { id: "lab", label: "Policy Scenario Lab" },
  { id: "rdhs", label: "RDHS 2025 Living Standards" },
  { id: "labour", label: "Labour Market LFS 2025" },
  { id: "vup", label: "VUP Social Protection" },
  { id: "inclusion", label: "Inclusion & Matchmaker" },
  { id: "explorer", label: "District Explorer" },
];
const TAB_BY_HASH = {
  "#dashboard": "dashboard",
  "#lab": "lab",
  "#rdhs": "rdhs",
  "#labour": "labour",
  "#vup": "vup",
  "#inclusion": "inclusion",
  "#explorer": "explorer",
};

export default function App() {
  const [status, setStatus] = useState("loading");
  const [rows, setRows] = useState([]);
  const [cfsvaRows, setCfsvaRows] = useState([]); // isolated CFSVA 2024 layer
  const [rdhsRows, setRdhsRows] = useState([]);   // isolated RDHS 2025 layer
  const [rdhsMounted, setRdhsMounted] = useState(
    () => TAB_BY_HASH[window.location.hash] === "rdhs", // deep-link straight into the RDHS tab
  );
  const [labourRows, setLabourRows] = useState([]);
  const [vupRows, setVupRows] = useState([]);
  const [financeRows, setFinanceRows] = useState([]); // inclusion rows for the matchmaker (Module C)
  const [districtNames, setDistrictNames] = useState([]); // brief/district pickers
  const [dataError, setDataError] = useState(null);
  const [refreshError, setRefreshError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [filters, setFilters] = useState({ query: "", categoryId: "all", district: "" });
  const [portalOpen, setPortalOpen] = useState(false);
  const [portalEpoch, setPortalEpoch] = useState(0);
  const [portalSession, setPortalSession] = useState(syncPortalSession);
  const [targetsVersion, setTargetsVersion] = useState(0); // re-key PolicyInsights after ministerial target edits
  const [activeTab, setActiveTab] = useState(() => TAB_BY_HASH[window.location.hash] ?? "dashboard");

  // Hash-synced SPA tabs (no reloads; deep links like #lab / #rdhs / #explorer work).
  const changeTab = (id) => {
    setActiveTab(id);
    if (id === "rdhs") setRdhsMounted(true); // first visit mounts; later visits keep state
    try {
      history.replaceState(null, "", id === "dashboard" ? location.pathname + location.search : `#${id}`);
    } catch {
      /* reserved for non-HTTP embeddings */
    }
  };

  const rowTotalRef = useRef(0);

  const fetchData = useCallback(async (signal) => {
    try {
      const data = await fetchMetrics({ signal });
      rowTotalRef.current = data.length;
      setRows(data);
      setUpdatedAt(new Date());
      setRefreshError(null);
      setStatus("ready");
      return true;
    } catch (error) {
      if (error?.name === "AbortError") return false;
      if (rowTotalRef.current > 0) {
        setRefreshError(error);
      } else {
        setStatus("error");
        setDataError(error);
      }
      return false;
    }
  }, []);

  const fetchCfsva = useCallback(async (signal) => {
    const data = await fetchCfsvaMetrics({ signal });
    if (data) setCfsvaRows(data);
  }, []);

  const fetchRdhs = useCallback(async (signal) => {
    const data = await fetchRdhsDistricts({ signal });
    if (data) setRdhsRows(data);
  }, []);

  const fetchLabour = useCallback(async (signal) => {
    const data = await fetchLabourDistricts({ signal });
    if (data) {
      setLabourRows(data);
      setDistrictNames(data.map((r) => r.district).sort());
    }
  }, []);

  const fetchVup = useCallback(async (signal) => {
    const data = await fetchVupDistricts({ signal });
    if (data) setVupRows(data);
  }, []);

  const fetchFinance = useCallback(async (signal) => {
    const data = await fetchInclusionDistricts({ signal });
    if (data) setFinanceRows(data);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // Optional data layers must never crash the dashboard: swallow AbortError and
    // downgrade any other failure to a console warning.
    const runQuiet = (fetcher) => {
      try {
        Promise.resolve(fetcher()).catch((err) => {
          if (err?.name === "AbortError") return; // unmount/refresh abort — expected
          console.warn("Optional data layer failed to load:", err);
        });
      } catch (err) {
        if (err?.name !== "AbortError") console.warn("Optional data layer failed to load:", err);
      }
    };
    runQuiet(() => fetchData(controller.signal));
    runQuiet(() => fetchCfsva(controller.signal));
    runQuiet(() => fetchRdhs(controller.signal));
    runQuiet(() => fetchLabour(controller.signal));
    runQuiet(() => fetchVup(controller.signal));
    runQuiet(() => fetchFinance(controller.signal));
    return () => controller.abort();
  }, [fetchData, fetchCfsva, fetchRdhs, fetchLabour, fetchVup, fetchFinance]);

  const allRows = useMemo(() => rows.concat(cfsvaRows), [rows, cfsvaRows]);
  const regions = useMemo(() => buildRegions(allRows), [allRows]);
  const stats = useMemo(() => computeNationalStats(regions), [regions]);
  const displayRows = useMemo(() => toDisplayRows(allRows), [allRows]);

  const selectedRegion = useMemo(
    () => (filters.district ? regions.find((r) => r.district === filters.district) ?? null : null),
    [regions, filters.district],
  );
  const nationalRegion = useMemo(() => buildNationalRegion(stats), [stats]);
  const insightRegion = selectedRegion ?? nationalRegion;

  const filteredRows = useMemo(
    () => filterDisplayRows(displayRows, filters),
    [displayRows, filters],
  );

  const hasFilters = Boolean(filters.query || filters.categoryId !== "all" || filters.district);

  const portalProps = {
    onOpenPortal: () => {
      setPortalOpen(true);
      setPortalEpoch((e) => e + 1); // fresh portal state each open
    },
    portalSession,
  };
  const portalModal = (
    <MinisterialPortal
      key={portalEpoch}
      open={portalOpen}
      onClose={() => {
        setPortalOpen(false);
        setPortalSession(syncPortalSession());
      }}
      onTargetsChanged={() => setTargetsVersion((v) => v + 1)}
      onDataChanged={() => {
        fetchData();
        fetchCfsva();
      }}
    />
  );

  if (status === "loading") {
    return (
      <div className="flex min-h-screen flex-col bg-slate-100">
        <Header regionCount={0} stats={null} dataPoints={0} {...portalProps} />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <LoadingState />
        </main>
        {portalModal}
      </div>
    );
  }

  if (status === "error" || regions.length === 0) {
    const noData = status === "ready";
    return (
      <div className="flex min-h-screen flex-col bg-slate-100">
        <Header regionCount={0} stats={null} dataPoints={0} {...portalProps} />
        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-10 sm:px-6 lg:px-8">
          {noData ? (
            <div
              role="status"
              className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white p-16 text-center shadow-sm"
            >
              <FileSearch2 className="h-10 w-10 text-slate-300" aria-hidden="true" />
              <h2 className="text-base font-bold text-slate-800">No usable district data was returned</h2>
              <p className="max-w-md text-sm text-slate-500">
                The API responded, but the dataset contained no district rows. Ministers can regenerate it from the{" "}
                <button
                  type="button"
                  onClick={() => setPortalOpen(true)}
                  className="font-semibold text-emerald-700 underline decoration-emerald-600/40 underline-offset-2 hover:text-emerald-800"
                >
                  Ministerial Portal
                </button>
                , then refresh.
              </p>
              <button
                type="button"
                onClick={() => fetchData()}
                className="mt-1 inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" /> Reload dataset
              </button>
            </div>
          ) : (
            <ErrorState error={dataError} onRetry={() => fetchData()} />
          )}
        </main>
        <Footer stats={null} />
        {portalModal}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      <Header
        regionCount={regions.length}
        stats={stats}
        dataPoints={allRows.length}
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={changeTab}
        {...portalProps}
      />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {refreshError && <ErrorBanner error={refreshError} onDismiss={() => setRefreshError(null)} />}

        {/* Tab 1 — National Intelligence Dashboard (kept mounted: instant tab switches,
            sliders/map state survive, Leaflet only ever initialises once). */}
        <div className={activeTab === "dashboard" ? "space-y-6" : "hidden space-y-6"}>
          <SummaryCards stats={stats} />

          <div className="grid gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] xl:items-start">
            <div className="isolate min-w-0">
              <Suspense
                fallback={
                  <div className="h-96 animate-pulse rounded-xl bg-slate-200/70" role="status"
                    aria-label="Loading district map" />
                }
              >
                <DistrictMap
                  regions={regions}
                  selectedDistrict={filters.district}
                  onSelectDistrict={(name) =>
                    setFilters((f) => ({ ...f, district: f.district === name ? "" : name }))
                  }
                />
              </Suspense>
            </div>

            <div className="min-w-0 space-y-4">
              <CFSVAPanel rows={cfsvaRows} stats={stats} selectedDistrict={filters.district} />
            </div>
          </div>

          <PolicyInsights
            key={`policy-insights-${targetsVersion}`}
            district={filters.district}
            fallbackRegion={insightRegion}
            fallbackStats={stats}
          />

          {/* Module D — one-click executive brief (national or focused district) */}
          <Suspense
            fallback={
              <div className="h-24 animate-pulse rounded-2xl bg-slate-200/70" role="status"
                aria-label="Loading brief card" />
            }
          >
            <BriefCard districts={districtNames} selectedDistrict={filters.district} />
          </Suspense>
        </div>

        {/* Tab 2 — Policy Scenario Lab */}
        <div className={activeTab === "lab" ? "" : "hidden"}>
          <ScenarioLab />
        </div>

        {/* Tab 3 — RDHS 2025 Living Standards (lazy; mounted on first visit) */}
        {rdhsMounted && (
          <div className={activeTab === "rdhs" ? "space-y-6" : "hidden space-y-6"}>
            <Suspense
              fallback={
                <div className="h-96 animate-pulse rounded-2xl bg-slate-200/70" role="status"
                  aria-label="Loading RDHS 2025 panel" />
              }
            >
              <RDHSPanel
                rows={rdhsRows}
                selectedDistrict={filters.district}
                onSelectDistrict={(name) =>
                  setFilters((f) => ({ ...f, district: f.district === name ? "" : name }))
                }
              />
            </Suspense>
          </div>
        )}

        {/* Tab — LFS 2025 Labour Market (Module A; lazy) */}
        <div className={activeTab === "labour" ? "space-y-6" : "hidden space-y-6"}>
          <Suspense
            fallback={
              <div className="h-96 animate-pulse rounded-2xl bg-slate-200/70" role="status"
                aria-label="Loading labour-market panel" />
            }
          >
            <LabourPanel
              rows={labourRows}
              selectedDistrict={filters.district}
              onSelectDistrict={(name) =>
                setFilters((f) => ({ ...f, district: f.district === name ? "" : name }))
              }
            />
          </Suspense>
        </div>

        {/* Tab — VUP Social Protection (Module B; lazy) */}
        <div className={activeTab === "vup" ? "space-y-6" : "hidden space-y-6"}>
          <Suspense
            fallback={
              <div className="h-96 animate-pulse rounded-2xl bg-slate-200/70" role="status"
                aria-label="Loading VUP panel" />
            }
          >
            <VupPanel
              rows={vupRows}
              selectedDistrict={filters.district}
              onSelectDistrict={(name) =>
                setFilters((f) => ({ ...f, district: f.district === name ? "" : name }))
              }
            />
          </Suspense>
        </div>

        {/* Tab — Inclusion & Matchmaker (Module C; lazy) */}
        <div className={activeTab === "inclusion" ? "space-y-6" : "hidden space-y-6"}>
          <Suspense
            fallback={
              <div className="h-96 animate-pulse rounded-2xl bg-slate-200/70" role="status"
                aria-label="Loading inclusion panel" />
            }
          >
            <InclusionPanel rows={financeRows} selectedDistrict={filters.district} />
          </Suspense>
        </div>

        {/* Tab 4 — District Explorer */}
        <div className={activeTab === "explorer" ? "space-y-6" : "hidden space-y-6"}>
          <Filters
            regions={regions}
            displayRows={displayRows}
            filters={filters}
            onChange={setFilters}
            matchCount={filteredRows.length}
            totalCount={displayRows.length}
            updatedAt={updatedAt}
            onRefresh={() => fetchData()}
          />
          {selectedRegion && <DistrictFocus region={selectedRegion} stats={stats} />}
          <MetricsTable
            rows={filteredRows}
            stats={stats}
            hasFilters={hasFilters}
            emptyHint={
              displayRows.length > 0 && filteredRows.length === 0
                ? "No rows match your current filters — try a broader search term or reset the filters."
                : null
            }
          />
        </div>
      </main>

      <Footer stats={stats} />
      {portalModal}
    </div>
  );
}
