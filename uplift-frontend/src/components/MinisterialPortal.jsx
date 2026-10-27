import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  DatabaseBackup,
  FileUp,
  KeyRound,
  Loader2,
  LockKeyhole,
  LogOut,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { ApiError, fetchTargets } from "../lib/api";
import { parseMicrodataCsv } from "../lib/microdata";
import { clearSession, getSession, getToken, loginAdmin, postAdminAction, storeSession } from "../lib/auth";
import { useLanguage } from "../lib/i18n";

export function PortalButton({ onOpen, session }) {
  const { t } = useLanguage();
  const active = Boolean(session);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-haspopup="dialog"
      className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-bold shadow-sm ring-1 ring-inset transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 sm:px-3.5 ${
        active
          ? "bg-emerald-500/15 text-emerald-200 ring-emerald-400/40 hover:bg-emerald-500/25"
          : "bg-white/10 text-white ring-white/20 hover:bg-white/15"
      }`}
      title={active ? `${t("portal.session")} · ${session.username}` : t("portal.sessionTitle")}
    >
      {active ? <ShieldCheck className="h-4 w-4" aria-hidden="true" /> : <LockKeyhole className="h-4 w-4" aria-hidden="true" />}
      {active ? t("portal.session") : t("portal.button")}
    </button>
  );
}

const TARGET_TOOL_TIP = "Editable flag-lines only — measured NISR statistics (e.g. 30.0% poverty headcount) are facts, not preferences.";

const TARGET_FIELDS = [
  { key: "poverty_limit", label: "Poverty guardrail" },
  { key: "vulnerability_share_flag", label: "Vulnerability flag" },
  { key: "vulnerability_share_critical", label: "Vulnerability critical" },
  { key: "mobile_money_floor", label: "Mobile-money floor" },
  { key: "mobile_money_critical", label: "Mobile-money critical" },
  { key: "inclusion_attention", label: "Inclusion attention" },
  { key: "inclusion_critical", label: "Inclusion critical" },
  { key: "climate_attention", label: "Climate attention" },
  { key: "climate_critical", label: "Climate critical" },
  { key: "savings_floor", label: "Savings floor" },
  { key: "credit_floor", label: "Credit floor" },
  { key: "sp_floor", label: "Social-protection floor" },
  { key: "extreme_poverty_floor", label: "Extreme-poverty floor" },
];

function expiryMinutes(expiresAt) {
  return Math.max(0, Math.floor((expiresAt - Date.now() / 1000) / 60));
}

export default function MinisterialPortal({ open, onClose, onTargetsChanged, onDataChanged }) {
  const [status, setStatus] = useState(() => ((getSession() && getToken()) ? "console" : "login"));
  const [session, setSession] = useState(() => getSession());
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [seedState, setSeedState] = useState({ touched: false, message: null });
  const [confirmSeed, setConfirmSeed] = useState(false);
  const [notice, setNotice] = useState(null);
  const usernameRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => usernameRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function handleSessionExpired(message) {
    handleLogout();
    setError(message ?? "Session expired. Sign in again to continue.");
  }

  async function handleLogin(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username") ?? "");
    const password = String(form.get("password") ?? "");
    setBusy(true);
    setError(null);
    try {
      const payload = await loginAdmin(username, password);
      storeSession(payload);
      setSession({ username: payload.username, expiresAt: payload.expires_at });
      setStatus("console");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Is the API running?");
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearSession();
    setSession(null);
    setStatus("login");
    setSeedState({ touched: false, message: null });
    setConfirmSeed(false);
    setNotice(null);
  }

  async function handleSeed() {
    if (!confirmSeed) {
      setError("Confirm the destructive reseed checkbox first (it drops + recomputes all tables).");
      return;
    }
    setBusy(true);
    setSeedState({ touched: true, message: null });
    try {
      const result = await postAdminAction("/api/admin/seed?drop_existing=true&include_cfsva=true");
      setSeedState({
        touched: true,
        message: `Dataset regenerated: ${result.seeded?.regions ?? 0} regions · ${result.seeded?.indicators ?? 0} indicators · ${result.seeded?.metric_rows ?? 0} rows${result.cfsva?.seeded ? " + CFSVA layer" : ""}.`,
      });
      onDataChanged?.();
    } catch (err) {
      if (err?.status === 401) {
        handleSessionExpired();
      } else {
        setSeedState({ touched: true, message: err instanceof ApiError ? err.message : "Seeding failed." });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm sm:items-center sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Ministerial Portal"
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-md flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className={`rounded-lg p-2.5 ${status === "console" ? "bg-emerald-50 text-emerald-600" : "bg-sky-50 text-sky-600"}`}>
              {status === "console" ? (
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              ) : (
                <LockKeyhole className="h-5 w-5" aria-hidden="true" />
              )}
            </span>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">NISR · Track 2 · Restricted</p>
              <h2 className="text-sm font-bold text-slate-900">Ministerial Portal</h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Ministerial Portal"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        {status === "console" && session ? (
          <div className="min-h-0 overflow-y-auto px-5 py-5">
            <div className="rounded-xl bg-emerald-50 p-3 text-[11px] font-medium text-emerald-800 ring-1 ring-inset ring-emerald-600/15">
              Signed in as <b>{session.username}</b> · session expires in ~{expiryMinutes(session.expiresAt)} min
            </div>

            {error && (
              <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-[11px] font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/15" role="alert">
                {error}
              </p>
            )}

            <TargetsEditor
              active={busy}
              onTargetsChanged={onTargetsChanged}
              onSessionExpired={handleSessionExpired}
              onNotice={setNotice}
            />
            <MicrodataUploader
              onDataChanged={onDataChanged}
              onSessionExpired={handleSessionExpired}
              onNotice={setNotice}
            />

            <SeedTool
              busy={busy}
              state={seedState}
              confirmSeed={confirmSeed}
              onConfirmSeed={setConfirmSeed}
              onSeed={handleSeed}
            />

            {notice && (
              <p className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-relaxed text-slate-600" role="status">
                {notice}
              </p>
            )}

            <button
              type="button"
              onClick={handleLogout}
              className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white py-2 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 hover:text-slate-800"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" /> End ministerial session
            </button>
          </div>
        ) : (
          <form className="min-h-0 overflow-y-auto px-5 py-5" onSubmit={handleLogin}>
            <div className="mb-3">
              <label htmlFor="portal-username" className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Administrator username
              </label>
              <input
                ref={usernameRef}
                id="portal-username"
                name="username"
                type="text"
                autoComplete="username"
                required
                defaultValue="nisr_admin"
                className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15"
              />
            </div>
            <div className="mb-4">
              <label htmlFor="portal-password" className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Password
              </label>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                <input
                  id="portal-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15"
                />
              </div>
            </div>

            {error && (
              <p className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-[11px] font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/15" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <LockKeyhole className="h-4 w-4" aria-hidden="true" />}
              {busy ? "Signing in…" : "Sign in securely"}
            </button>

            <p className="mt-3 text-center text-[10px] leading-relaxed text-slate-400">
              bcrypt-hashed credentials · short-lived HS256 access token · analytics dashboard stays open to all.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

function ToolFrame({ icon, title, sub, children, tint = "emerald" }) {
  const tints = {
    emerald: "bg-emerald-50 text-emerald-600",
    sky: "bg-sky-50 text-sky-600",
  };
  return (
    <section className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70">
      <header className="flex items-start gap-2.5 border-b border-slate-200/70 px-3 py-2.5">
        <span className={`rounded-md p-1.5 ${tints[tint]}`}>{icon}</span>
        <div className="min-w-0">
          <p className="text-xs font-bold text-slate-800">{title}</p>
          <p className="mt-0.5 text-[10px] leading-relaxed text-slate-500">{sub}</p>
        </div>
      </header>
      <div className="px-3 py-3">{children}</div>
    </section>
  );
}

function TargetsEditor({ onSessionExpired, onNotice, onTargetsChanged }) {
  const [phase, setPhase] = useState("loading");
  const [loadError, setLoadError] = useState(null);
  const [entries, setEntries] = useState(null);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [vErrors, setVErrors] = useState([]);

  async function load({ quiet = false } = {}) {
    setPhase(quiet ? "refreshing" : "loading");
    if (!quiet) setLoadError(null);
    try {
      const payload = await fetchTargets();
      setEntries(payload.entries);
      setValues(Object.fromEntries(payload.entries.map((e) => [e.target_key, String(e.current)])));
      setPhase("ready");
    } catch (err) {
      setPhase("ready");
      setLoadError(err instanceof ApiError ? err.message : "Could not load targets.");
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time fetch for the console (mirrors App's async data layer)
    load();
  }, []);

  const overriddenCount = entries?.filter((e) => e.is_overridden).length ?? 0;

  function onValueChange(key, raw) {
    setValues((v) => ({ ...v, [key]: raw.replace(/[^\d.]/g, "") }));
  }

  async function save(event) {
    event.preventDefault();
    const dirty = {};
    for (const e of entries) {
      const raw = values[e.target_key];
      const parsed = Number.parseFloat(raw);
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
        setVErrors([`"${e.target_key}" must be a number between 0 and 100.`]);
        return;
      }
      if (Math.abs(parsed - e.current) > 1e-9) dirty[e.target_key] = parsed;
    }
    setVErrors([]);
    if (Object.keys(dirty).length === 0) {
      onNotice?.("No changed values to save — adjust a target first.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await postAdminAction("/api/admin/targets", { targets: dirty, reason: "Ministerial console" });
      setMessage(`Applied override for: ${Object.keys(dirty).join(", ")}. Policy verdicts now use these thresholds.`);
      onTargetsChanged?.();
      await load({ quiet: true });
      onNotice?.(null);
    } catch (err) {
      if (err?.status === 401) return onSessionExpired();
      setVErrors(err instanceof ApiError ? (err.extra?.errors ?? [err.message]) : ["Saving failed."]);
    } finally {
      setSaving(false);
    }
  }

  async function resetToOfficial() {
    setSaving(true);
    setMessage(null);
    setVErrors([]);
    try {
      const result = await postAdminAction("/api/admin/targets", { reset_to_official: true });
      setMessage(`Restored official NISR baseline (${result.removed_overrides} override(s) removed).`);
      onTargetsChanged?.();
      await load({ quiet: true });
      onNotice?.(null);
    } catch (err) {
      if (err?.status === 401) return onSessionExpired();
      setVErrors(err instanceof ApiError ? (err.extra?.errors ?? [err.message]) : ["Reset failed."]);
    } finally {
      setSaving(false);
    }
  }

  return (
    <ToolFrame
      icon={<SlidersHorizontal className="h-4 w-4" aria-hidden="true" />}
      title="Ministerial policy targets"
      sub={`JWT POST /api/admin/targets · public GET /api/targets · ${overriddenCount} override(s) active`}
    >
      {phase === "loading" && (
        <p className="flex items-center gap-2 text-[11px] text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> Loading national baseline…
        </p>
      )}

      {phase !== "loading" && loadError && (
        <p className="flex items-start gap-2 text-[11px] font-semibold text-amber-700">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" /> {loadError}
        </p>
      )}

      {phase !== "loading" && !loadError && entries && (
        <div>
          <p className="mb-2 text-[10px] leading-relaxed text-slate-500">{TARGET_TOOL_TIP}</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {entries.map((entry) => (
              <label key={entry.target_key} title={`Official default: ${entry.official_default}`}>
                <span className="mb-1 flex items-baseline gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  {TARGET_FIELDS.find((f) => f.key === entry.target_key)?.label ?? entry.target_key}
                  {entry.is_overridden && <span className="rounded bg-amber-100 px-1 text-[10px] font-black text-amber-700">OVERRIDE</span>}
                </span>
                <input
                  inputMode="decimal"
                  value={values[entry.target_key] ?? ""}
                  onChange={(e) => onValueChange(entry.target_key, e.target.value)}
                  placeholder={String(entry.official_default)}
                  className="h-9 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-sm tabular-nums text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/15"
                />
              </label>
            ))}
          </div>

          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={save}
              disabled={saving || phase !== "ready"}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-2 text-[11px] font-bold text-white shadow-sm transition hover:bg-emerald-800 disabled:opacity-60"
            >
              {saving || phase === "refreshing" ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />}
              Apply overrides
            </button>
            <button
              type="button"
              onClick={resetToOfficial}
              disabled={saving || overriddenCount === 0}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-[11px] font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 hover:text-slate-800 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Official
            </button>
          </div>

          {vErrors.length > 0 && (
            <ul className="mt-2 space-y-1 rounded-lg bg-rose-50 px-3 py-2 text-[11px] font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/15" role="alert">
              {vErrors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {message && (
            <p className="mt-2" role="status">
              <TargetsAudit entries={entries} message={message} />
            </p>
          )}
        </div>
      )}
    </ToolFrame>
  );
}

function TargetsAudit({ entries, message }) {
  const audit = (entries ?? []).filter((e) => e.is_overridden && e.updated_by);
  return (
    <>
      <p className="rounded-lg bg-emerald-50 px-3 py-2 text-[11px] leading-relaxed text-emerald-800">{message}</p>
      {audit.length > 0 && (
        <p className="mt-1 text-[10px] leading-relaxed text-slate-400">
          Audit: {audit.map((e) => `${e.target_key}=${e.current}@${e.updated_by} (${e.updated_at ?? "just now"})`).join(" · ")}
        </p>
      )}
    </>
  );
}

function MicrodataUploader({ onSessionExpired, onNotice, onDataChanged }) {
  const [parsed, setParsed] = useState(null); // { rows, errors, fileName }
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);

  function onPickFile(event) {
    setReport(null);
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const { rows, errors } = parseMicrodataCsv(String(reader.result ?? ""));
        if (rows.length === 0) throw new Error("No complete data rows found under the header line.");
        setParsed({ rows, errors, fileName: file.name });
        onNotice?.(null);
      } catch (err) {
        setParsed(null);
        setReport({ kind: "parse", message: err instanceof Error ? err.message : "Could not parse the CSV." });
      }
      event.target.value = ""; // allow re-picking the same file
    };
    reader.onerror = () => setReport({ kind: "parse", message: `Could not read "${file.name}".` });
    reader.readAsText(file);
  }

  async function upload() {
    if (!parsed) return;
    setBusy(true);
    setReport(null);
    try {
      const result = await postAdminAction("/api/admin/microdata", { rows: parsed.rows });
      setReport({ kind: "upload", result, fileName: parsed.fileName });
      onDataChanged?.();
    } catch (err) {
      if (err?.status === 401) return onSessionExpired();
      setReport({ kind: "upload", error: err instanceof ApiError ? err.message : "Upload failed." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <ToolFrame
      tint="sky"
      icon={<FileUp className="h-4 w-4" aria-hidden="true" />}
      title="Upload survey microdata"
      sub="JWT POST /api/admin/microdata · CSV parsed in-browser, upserted by district + year"
    >
      <label
        htmlFor="microdata-input"
        className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white px-3 py-3 text-[11px] font-semibold text-slate-500 transition hover:border-sky-400 hover:text-sky-700"
      >
        <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
        {parsed ? parsed.fileName : "Choose a CSV…"}
      </label>
      <input
        id="microdata-input"
        type="file"
        accept=".csv,text/csv,text/plain"
        onChange={onPickFile}
        className="hidden"
      />

      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        Header must be <code className="rounded bg-slate-100 px-1 text-[10px]">district, indicator_code, survey_year, value</code> — new
        vintages insert, existing (district, year, indicator) upserts.
      </p>

      {parsed && (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-sky-50 px-3 py-2 text-[11px] text-sky-800 ring-1 ring-inset ring-sky-600/15">
          <span>
            Ready: <b>{parsed.rows.length}</b> row(s)
            {parsed.errors.length > 0 && ` · ${parsed.errors.length} invalid line(s) skipped`}
          </span>
          <button
            type="button"
            onClick={upload}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-2.5 py-1.5 text-[11px] font-bold text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />}
            Upload now
          </button>
        </div>
      )}

      {report?.kind === "parse" && (
        <p className="mt-2 flex items-start gap-2 text-[11px] font-semibold text-amber-700" role="alert">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" /> {report.message}
        </p>
      )}

      {report?.kind === "upload" && report.error && (
        <p className="mt-2 text-[11px] font-semibold text-rose-600" role="alert">
          {report.error}
        </p>
      )}

      {report?.kind === "upload" && report.result && (
        <div className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-relaxed text-slate-600" role="status">
          <b>{report.result.rows_processed}</b> processed · <b>{report.result.inserted}</b> inserted · <b>{report.result.updated}</b> updated · <b>{report.result.rejected}</b> rejected
          {(report.result.errors?.length ?? 0) > 0 && (
            <ul className="mt-1 space-y-0.5 text-[10px] text-rose-600">
              {report.result.errors.slice(0, 5).map((e) => (
                <li key={e.row}>row {e.row}{e.district ? ` · ${e.district}` : ""}{e.indicator_code ? ` · ${e.indicator_code}` : ""} — {e.error}</li>
              ))}
              {report.result.errors.length > 5 && <li className="text-slate-400">…and {report.result.errors.length - 5} more</li>}
            </ul>
          )}
          {(report.result.rejected ?? 0) === 0 && " · dashboard refreshed automatically."}
        </div>
      )}
    </ToolFrame>
  );
}

function SeedTool({ busy, state, confirmSeed, onConfirmSeed, onSeed }) {
  return (
    <section className="mt-4">
      <button
        type="button"
        onClick={onSeed}
        disabled={busy}
        className="flex w-full items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-left transition hover:bg-slate-100 disabled:opacity-60"
      >
        {busy ? (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-slate-400" aria-hidden="true" />
        ) : (
          <DatabaseBackup className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
        )}
        <span>
          <span className="block text-xs font-bold text-slate-800">Regenerate analytics dataset</span>
          <span className="mt-0.5 block text-[11px] leading-relaxed text-slate-500">
            JWT-protected POST /api/admin/seed · rebuilds the calibrated FinScope/EICV7 + CFSVA panel
          </span>
        </span>
      </button>

      {state.touched && (
        <label className="mt-2 flex cursor-pointer items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[11px] leading-relaxed text-amber-800">
          <input
            type="checkbox"
            checked={confirmSeed}
            onChange={(e) => onConfirmSeed(e.target.checked)}
            className="mt-0.5 accent-amber-600"
          />
          I confirm the destructive reseed (drops + recreates analytics tables)
        </label>
      )}

      {state.message && (
        <p className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-relaxed text-slate-600" role="status">
          {state.message}
        </p>
      )}
    </section>
  );
}
