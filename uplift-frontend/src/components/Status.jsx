import { Database, MapPin, RefreshCw, Server, TriangleAlert, X } from "lucide-react";
import { BASE_URL } from "../lib/api";

export function LoadingState({ label = "Loading national survey metrics…" }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white p-16 shadow-sm" role="status" aria-live="polite">
      <span className="relative flex h-12 w-12 items-center justify-center">
        <span className="absolute h-full w-full animate-ping rounded-full bg-emerald-400/30" aria-hidden="true" />
        <RefreshCw className="h-6 w-6 animate-spin text-emerald-600" aria-hidden="true" />
      </span>
      <p className="text-sm font-medium text-slate-500">{label}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-8 shadow-sm">
      <div className="mx-auto flex max-w-xl flex-col items-center gap-3 text-center">
        <span className="rounded-xl bg-rose-100 p-3 text-rose-600">
          <TriangleAlert className="h-6 w-6" aria-hidden="true" />
        </span>
        <h2 className="text-base font-bold text-rose-900">We couldn't load the survey data</h2>
        <p className="text-sm text-rose-700">{error?.message ?? "An unexpected error occurred."}</p>
        <ul className="mt-1 space-y-1 text-xs text-rose-600">
          <li className="flex items-center justify-center gap-1.5">
            <Server className="h-3.5 w-3.5" aria-hidden="true" /> Check that the FastAPI service is reachable at <code className="rounded bg-rose-100 px-1 py-0.5 font-mono">{BASE_URL.replace(/^https?:\/\//, "")}</code>
          </li>
          <li className="flex items-center justify-center gap-1.5">
            <Database className="h-3.5 w-3.5" aria-hidden="true" /> Confirm the PostgreSQL <code className="rounded bg-rose-100 px-1 py-0.5 font-mono">uplift_rwanda_db</code> connection
          </li>
        </ul>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;
  return (
    <div role="status" className="flex items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-800">
      <span>
        <strong className="font-semibold">Live refresh failed:</strong> {error?.message ?? "unknown error"} — showing the last successful snapshot.
      </span>
      <div className="flex shrink-0 items-center gap-2">
        <button type="button" onClick={onDismiss} aria-label="Dismiss refresh error" className="rounded-md p-2 text-amber-700 transition hover:bg-amber-100">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export function Footer({ stats }) {
  return (
    <footer className="mt-12 border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-3 py-8 text-center sm:flex-row sm:px-6 sm:text-left lg:px-8">
        <div className="flex items-center gap-2.5 text-xs text-slate-500">
          <MapPin className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          <span>
            UpliftRwanda · NISR 2026 Big Data Hackathon — Track 2: Financial Inclusion &amp; Poverty Reduction.
            Data inspired by EICV 7 / FinScope Rwanda.
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <Database className="h-3.5 w-3.5" aria-hidden="true" />
          PostgreSQL · FastAPI · React
          {stats?.entryCount ? (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-500">{stats.entryCount} records</span>
          ) : null}
        </div>
      </div>
    </footer>
  );
}
