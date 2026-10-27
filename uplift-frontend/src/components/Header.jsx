import { ChevronDown, Hexagon, Languages, MapPinned, ScanSearch } from "lucide-react";
import { PortalButton } from "./MinisterialPortal";
import { useLanguage } from "../lib/i18n";

function UpliftLogoNISR() {
  return (
    <div className="flex items-center gap-3 group cursor-default">
      <div className="relative h-9 w-9 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 border border-slate-700/80 flex items-center justify-center shadow-xl shadow-cyan-500/10 group-hover:border-cyan-500/55 transition-all duration-300 sm:h-11 sm:w-11">
        <div className="absolute inset-0 rounded-2xl bg-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        <svg className="h-5 w-5 text-cyan-400 transform group-hover:scale-105 transition-transform duration-300 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13h2l3-6 4 10 3-6 3 2h3" />
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.3" />
        </svg>
      </div>
      <div className="flex min-w-0 flex-col">
        <div className="flex items-center gap-2">
          <span className="truncate text-base font-extrabold tracking-tighter text-white sm:text-lg">
            Uplift<span className="text-cyan-400">Rwanda</span>
          </span>
          <span className="px-2 py-0.5 text-[10px] font-bold tracking-widest bg-cyan-500/10 text-cyan-400 rounded-md border border-cyan-500/20 uppercase shadow-inner">
            NISR
          </span>
        </div>
        <span className="text-[11px] font-medium tracking-wider uppercase text-slate-400 -mt-0.5">
          Track 2 Analytics Core
        </span>
      </div>
    </div>
  );
}

function formatCount(value) {
  return value.toLocaleString("en-US");
}

/** EN/RW switch; choice persists in localStorage. */
function LanguageToggle() {
  const { lang, setLang, t } = useLanguage();
  return (
    <div
      role="group"
      aria-label={t("lang.toggleAria")}
      className="flex items-center gap-0.5 rounded-xl bg-white/10 p-0.5 shadow-sm ring-1 ring-inset ring-white/20"
    >
      <Languages className="ml-1.5 h-3.5 w-3.5 text-slate-300" aria-hidden="true" />
      {[
        { code: "en", label: "EN" },
        { code: "rw", label: "RW" },
      ].map(({ code, label }) => {
        const active = lang === code;
        return (
          <button
            key={code}
            type="button"
            aria-pressed={active}
            title={code === "en" ? "English" : "Kinyarwanda"}
            onClick={() => setLang(code)}
            className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition ${
              active
                ? "bg-slate-100 text-slate-900 shadow"
                : "text-slate-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

function HeroStat({ icon: Icon, label, value, loading, support, supportAccent = false, accent }) {
  return (
    <div className={`relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.05] p-4 ${accent ? `border-l-4 ${accent}` : ""}`}>
      <dt className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">
        <Icon className="h-3 w-3" aria-hidden="true" /> {label}
      </dt>
      <dd className="mt-1.5 text-2xl font-bold tabular-nums text-white">
        {loading ? <span className="inline-block h-7 w-16 animate-pulse-soft rounded bg-white/10" /> : value}
      </dd>
      <p className={`mt-0.5 text-[10px] font-medium ${supportAccent ? "text-emerald-300" : "text-slate-300"}`}>
        {support}
      </p>
    </div>
  );
}

function TabSwitcher({ tabs, activeTab, onChange, className = "" }) {
  const { t } = useLanguage();
  return (
    <div
      role="tablist"
      aria-label={t("header.dashboardViews")}
      className={`scrollbar-none hidden flex-nowrap items-center gap-2 overflow-x-auto whitespace-nowrap rounded-xl border border-white/10 bg-white/[0.06] p-1 sm:flex ${className}`}
    >
      {tabs.map((tab) => {
        const active = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={`shrink-0 rounded-lg px-3 py-2 text-[11px] font-semibold transition sm:text-xs ${
              active
                ? "bg-slate-100 text-slate-900 shadow"
                : "text-slate-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

/** Mobile-only collapsible navigation: a native dropdown that can never clip or overflow. */
function TabSelect({ tabs, activeTab, onChange, className = "" }) {
  const { t } = useLanguage();
  return (
    <div className={className}>
      <label htmlFor="mobile-tab-select" className="sr-only">
        {t("header.dashboardViews")}
      </label>
      <div className="relative flex w-full items-center">
        <select
          id="mobile-tab-select"
          value={activeTab}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none truncate rounded-xl border border-white/10 bg-white/[0.06] py-2 pl-3 pr-9 text-xs font-semibold text-slate-100 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
        >
          {tabs.map((tab) => (
            <option key={tab.id} value={tab.id} className="bg-slate-900 text-slate-100">
              {tab.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-slate-400" aria-hidden="true" />
      </div>
    </div>
  );
}

export default function Header({ regionCount, stats, dataPoints = 0, tabs, activeTab, onTabChange, onOpenPortal, portalSession }) {
  const { t } = useLanguage();
  const yearLabel = stats?.years?.length
    ? stats.years.length > 3 ? `${stats.years[0]}–${stats.years[stats.years.length - 1]}` : stats.years.join(" · ")
    : null;
  return (
    <>
      {/* Mobile: plain relative (non-sticky) header; sticky resumes from sm up for larger screens */}
      <div className="relative w-full max-w-full z-40 overflow-hidden border-b border-slate-800 bg-slate-900 text-slate-100 shadow-lg sm:sticky sm:top-0">
        <div aria-hidden="true" className="h-0.5 bg-gradient-to-r from-sky-500 via-yellow-400 to-emerald-600" />
        <nav
          aria-label="Top navigation"
          className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-3 py-2.5 sm:px-6 lg:px-8"
        >
          <div className="flex min-w-0 items-center gap-3">
            <UpliftLogoNISR />
            <span
              className="ml-1 hidden items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-semibold text-emerald-200 md:inline-flex"
              title={t("header.liveTitle")}
            >
              <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-emerald-400" />
              {t("header.live")}
            </span>
          </div>

          {tabs && tabs.length > 0 && (
            <>
              {/* Mobile: collapsible native dropdown (fits any screen, touch friendly) */}
              <TabSelect
                tabs={tabs}
                activeTab={activeTab}
                onChange={onTabChange}
                className="order-3 flex-none w-full min-w-0 sm:hidden"
              />
              {/* sm and up: auto-scrolling horizontal tab strip */}
              <TabSwitcher
                tabs={tabs}
                activeTab={activeTab}
                onChange={onTabChange}
                className="order-3 w-full min-w-0 sm:order-2 sm:w-auto sm:flex-1"
              />
            </>
          )}

          <div className={`flex shrink-0 items-center gap-3 ${tabs ? "order-2 sm:order-3" : ""}`}>
            <LanguageToggle />
            <PortalButton onOpen={onOpenPortal} session={portalSession} />
          </div>
        </nav>
      </div>

      <div className="relative overflow-hidden border-b border-slate-800 bg-slate-900 text-slate-100">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl"
        />
        <div className="relative mx-auto max-w-7xl px-3 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300">
                <Hexagon className="h-4 w-4" aria-hidden="true" />
                NISR 2026 Big Data Hackathon · Track 2
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
                  Uplift{" "}
                  <span className="bg-gradient-to-r from-sky-300 to-emerald-300 bg-clip-text text-transparent">
                    Rwanda
                  </span>
                </h1>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-[11px] font-semibold text-emerald-200">
                  <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-emerald-400" />
                  {t("header.heroBadge")}
                </span>
              </div>
                <p className="mt-2 max-w-2xl text-sm text-slate-300 sm:text-base">
                  {t("header.heroDescription")}
                </p>
            </div>

            <dl className="grid w-full gap-3 sm:w-auto sm:grid-cols-3">
              <HeroStat
                icon={ScanSearch}
                label={t("header.dataPoints")}
                value={dataPoints > 0 ? formatCount(dataPoints) : null}
                loading={dataPoints === 0}
                support={dataPoints > 0 ? t("header.liveFromDb") : t("header.loading")}
                supportAccent={dataPoints > 0}
                accent="border-l-sky-400"
              />
              <HeroStat
                icon={MapPinned}
                label={t("header.districts")}
                value={regionCount > 0 ? formatCount(regionCount) : null}
                loading={regionCount === 0}
                support={regionCount > 0 ? t("header.allMapped") : t("header.loading")}
                accent="border-l-emerald-400"
              />
              <HeroStat
                icon={Hexagon}
                label={t("header.surveyVintage")}
                value={yearLabel ?? null}
                loading={!yearLabel}
                support="FinScope · EICV7 · CFSVA · LFS"
                accent="border-l-yellow-400"
              />
            </dl>
          </div>
        </div>
      </div>
    </>
  );
}
