import { Hexagon, MapPinned, ScanSearch } from "lucide-react";

export default function Header({ regionCount, stats }) {
  const year = stats?.years?.length ? stats.years[stats.years.length - 1] : null;
  return (
    <header className="relative overflow-hidden bg-slate-900 text-slate-100">
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-sky-500 via-yellow-400 to-emerald-600"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl"
      />
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300">
              <Hexagon className="h-4 w-4" aria-hidden="true" />
              NISR 2026 Big Data Hackathon · Track 2
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Uplift{" "}
              <span className="bg-gradient-to-r from-sky-300 to-emerald-300 bg-clip-text text-transparent">
                Rwanda
              </span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300 sm:text-base">
              Regional financial inclusion, poverty dynamics and social protection intelligence —
              powering evidence-based decisions aligned with Vision 2050.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1.5 text-sky-200">
              <MapPinned className="h-3.5 w-3.5" aria-hidden="true" />
              {regionCount} districts covered
            </span>
            {year && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-yellow-400/30 bg-yellow-400/10 px-3 py-1.5 text-yellow-200">
                <ScanSearch className="h-3.5 w-3.5" aria-hidden="true" />
                EICV / FinScope · {year}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-emerald-200">
              Postgres · FastAPI · React
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
