export const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? // production: set on the Vercel dashboard
  import.meta.env.VITE_API_URL ??      // legacy name kept for existing deploys
  "https://uplift-backend-77a1.onrender.com" // deployed FastAPI service (prod fallback)
).replace(/\/+$/, "");

// Catch the most common production misconfiguration early: deploying without
// the required env var, leaving the localhost fallback baked into the bundle.
if (import.meta.env.PROD && /\/\/(localhost|127\.0\.0\.1)/.test(BASE_URL)) {
  console.warn(
    "[uplift-api] PROD build is pointing at a localhost API — set VITE_API_BASE_URL in your hosting dashboard.",
  );
}

export class ApiError extends Error {
  constructor(message, { status, cause, extra } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "ApiError";
    this.status = status;
    this.extra = extra ?? null;
  }
}

export async function fetchMetrics({ signal } = {}) {
  return fetchRows(`${BASE_URL}/api/metrics`, { signal });
}

/** CFSVA 2024 rows from their own table; returns null on any failure (graceful). */
export async function fetchCfsvaMetrics({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/cfsva/metrics`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

/**
 * RDHS 2025 wide district rows (/api/rdhs/districts) for the living-standards
 * view. Returns null on any failure so the third data layer stays optional and
 * the existing FinScope/EICV/CFSVA surfaces are never blocked by it.
 */
export async function fetchRdhsDistricts({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/rdhs/districts`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

/** Internal: standard row-feed contract { status, count, data[] }. */
async function fetchRows(path, { signal } = {}) {
  let res;
  try {
    res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(`API responded with ${res.status}: ${detail}`, { status: res.status });
  }
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.data)) {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload.data;
}

/**
 * Public snapshot of the national policy baseline (defaults + overrides +
 * per-key audit entries). Console tooling uses this to render the editor.
 */
export async function fetchTargets({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/targets`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(`API responded with ${res.status}`, { status: res.status });
  const payload = await res.json();
  if (payload.status !== "success" || typeof payload.targets !== "object") {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload;
}

/**
 * Automated policy-engine verdict from the backend for one district
 * (name or id). Responds with { insights, thresholds, benchmarks, ... }.
 */
export async function fetchDistrictInsights(district, { signal } = {}) {
  if (!district) return null;
  return fetchInsights(`/api/districts/${encodeURIComponent(district)}/insights`, { signal });
}

/**
 * Population-weighted national policy view (same shape, no district block).
 */
export async function fetchNationalInsights({ signal } = {}) {
  return fetchInsights("/api/insights/national", { signal });
}

async function fetchInsights(path, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the policy engine at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    let code = null;
    let hint = null;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
      code = body.code ?? null;
      hint = body.hint ?? null;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, {
      status: res.status,
      cause: code || hint ? { detail, code, hint } : undefined,
    });
  }
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.insights)) {
    throw new ApiError("The policy engine returned an unexpected response shape.");
  }
  return payload;
}

/** District index (ids + province + weights) for lab selectors. */
export async function fetchDistrictList({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/districts`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(`API responded with ${res.status}`, { status: res.status });
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.data)) {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload.data;
}

/**
 * Predictive what-if: POST /api/v1/simulate. Returns model card + trajectories.
 */
export async function runSimulation(payload = {}, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/v1/simulate`, {
      method: "POST",
      signal,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the simulation engine at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, { status: res.status });
  }
  const data = await res.json();
  if (data.status !== "success" || !data.national) {
    throw new ApiError("The simulation engine returned an unexpected response shape.");
  }
  return data;
}

// LFS 2025 labour-market intelligence (Module A) — optional layer.

export async function fetchLabourDistricts({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/labour/districts`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

export async function fetchLabourSummary({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/labour/summary`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return null;
  }
  if (!res.ok) return null;
  const payload = await res.json();
  return payload.status === "success" ? payload : null;
}

export async function fetchLabourDisaggregation(dimension, { signal } = {}) {
  let res;
  try {
    res = await fetch(
      `${BASE_URL}/api/labour/disaggregation?dimension=${encodeURIComponent(dimension)}`,
      { signal, headers: { Accept: "application/json" } },
    );
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return null;
  }
  if (!res.ok) return null;
  const payload = await res.json();
  return payload.status === "success" ? payload : null;
}

// VUP social-protection tracker (Module B) — optional layer.

export async function fetchVupDistricts({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/vup/districts`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

export async function fetchVupSummary({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/vup/summary`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return null;
  }
  if (!res.ok) return null;
  const payload = await res.json();
  return payload.status === "success" ? payload : null;
}

// Financial inclusion + opportunity matchmaker (Module C).

export async function fetchInclusionDistricts({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/inclusion/districts`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

export async function fetchMatchmakerCatalog({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/matchmaker/catalog`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return null;
  }
  if (!res.ok) return null;
  const payload = await res.json();
  return payload.status === "success" ? payload : null;
}

export async function postMatchmakerRecommendations(profile, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/matchmaker/recommendations`, {
      method: "POST",
      signal,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the matchmaker at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    let code = null;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
      code = body.code ?? null;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, { status: res.status, extra: { code } });
  }
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.results)) {
    throw new ApiError("The matchmaker returned an unexpected response shape.");
  }
  return payload;
}

// Executive policy brief (Module D) — direct download URLs.

export function briefDownloadUrl(districtRef, format = "pdf") {
  const ref = districtRef ? encodeURIComponent(districtRef) : "national";
  return `${BASE_URL}/api/brief/${ref}.${format}`;
}

/** Fetch the ReportLab brief as a blob and trigger the browser save dialog.
 *
 * Unlike a plain <a href> navigation (which silently swallows 400/404/503),
 * fetch surfaces the backend's JSON error details through ApiError.
 */
export async function downloadBrief(districtRef, format = "pdf", { signal } = {}) {
  let res;
  try {
    res = await fetch(briefDownloadUrl(districtRef, format), {
      signal,
      headers: { Accept: format === "csv" ? "text/csv" : "application/pdf" },
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the brief generator at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* stream body — keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, { status: res.status });
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `upliftrwanda-brief-${districtRef || "national"}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
